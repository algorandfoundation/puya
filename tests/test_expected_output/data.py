import contextlib
import difflib
import tempfile
import typing as t
from collections.abc import Iterator, Sequence
from pathlib import Path

import _pytest._code.code
import attrs
import pytest

from puya.awst.nodes import AWST
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.compile import awst_to_teal
from puya.errors import PuyaError, log_exceptions
from puya.log import Log, LogLevel, logging_context
from puya.utils import coalesce
from puyapy.awst_build.main import transform_ast
from puyapy.options import PuyaPyOptions
from puyapy.parse import parse_python
from puyapy.template import parse_template_key_value
from tests.utils import narrowed_parse_result

THIS_DIR = Path(__file__).parent
REPO_DIR = THIS_DIR.parent.parent
CASE_COMMENT = "##"
CASE_PREFIX = f"{CASE_COMMENT} case:"
PATH_PREFIX = f"{CASE_COMMENT} path:"
TEMPLATE_PREFIX = f"{CASE_COMMENT} template:"
EXPECTED_PREFIX = f"{CASE_COMMENT} expected:"
EXPECTED_OUTPUTS = {"awst"}
LINE_CONTINUATION = "\\"
LineNum: t.TypeAlias = int

PREFIX_TO_LEVEL = {
    "E:": LogLevel.error,
    "W:": LogLevel.warning,
    "N:": LogLevel.info,
}
LEVEL_TO_PREFIX = {v: k for k, v in PREFIX_TO_LEVEL.items()}
MIN_LEVEL_TO_REPORT = min(LEVEL_TO_PREFIX)
OUTPUT_TYPE_PREFIX_LENGTH = len(next(iter(PREFIX_TO_LEVEL)))
assert all(len(k) == OUTPUT_TYPE_PREFIX_LENGTH for k in PREFIX_TO_LEVEL)


@attrs.define(frozen=True)
class TestCaseOutput:
    level: LogLevel
    output: str

    def as_comment(self) -> str:
        try:
            prefix = LEVEL_TO_PREFIX[self.level]
        except KeyError:
            # display missing keys as error, this is so critical errors are displayed nicely
            # while still causing the test case to fail.
            # Critical errors should never be "expected", but can be useful to trigger
            # during development
            prefix = LEVEL_TO_PREFIX[LogLevel.error] + " !!!"
        return f"{prefix} {self.output}"


OutputMapping: t.TypeAlias = dict[LineNum, list[TestCaseOutput]]


class TestCaseOutputDifferenceError(Exception):
    def __init__(
        self,
        *,
        missing_output: dict[Path, OutputMapping] | None = None,
        unexpected_output: dict[Path, OutputMapping] | None = None,
        unexpected_awst: dict[Path, list[str]] | None = None,
    ):
        self.missing_output: dict[Path, OutputMapping] = coalesce(missing_output, {})
        self.unexpected_output: dict[Path, OutputMapping] = coalesce(unexpected_output, {})
        self.unexpected_awst: dict[Path, list[str]] = coalesce(unexpected_awst, {})


@attrs.define
class TestCaseFile:
    path: Path | None = None
    """Path as defined in test data"""
    body: list[str] = attrs.field(factory=list)
    """Contents of file"""
    expected_output: OutputMapping = attrs.field(factory=dict)
    """Expected log output"""
    expected_awst: list[str] | None = None
    """Expected awst output (after being transformed to a text representation)"""

    src_path: Path | None = None
    """Temporary location of where test file is written during compilation,
    used to correlate log items and awst output"""


@attrs.define
class TestCase:
    name: str
    src_line: int
    files: list[TestCaseFile] = attrs.field(factory=list)
    template_vars: dict[str, int | bytes] = attrs.field(factory=dict)
    approved_case_source: list[str] = attrs.field(factory=list)
    """An adjusted test case source that has all the expected output as comments.
    Defaults to original input if test case is not executed"""
    failure: TestCaseOutputDifferenceError | None = None

    def __hash__(self) -> int:
        return hash(self.name)

    def __attrs_post_init__(self) -> None:
        if not self.files:
            self.add_new_file()

    @property
    def current_file(self) -> TestCaseFile:
        return self.files[-1]

    def add_new_file(self) -> None:
        self.files.append(TestCaseFile())


def get_python_expected_output(line: str) -> tuple[str, list[TestCaseOutput]]:
    [python, *comments] = line.split(f" {CASE_COMMENT} ", maxsplit=1)
    outputs = list[TestCaseOutput]()
    for comment in comments:
        prefix = comment[:OUTPUT_TYPE_PREFIX_LENGTH]
        level = PREFIX_TO_LEVEL.get(prefix)
        if level is not None:
            output = comment[len(prefix) :].rstrip(LINE_CONTINUATION).strip()
            outputs.append(TestCaseOutput(level=level, output=output))
        else:
            python += f" {CASE_COMMENT} {comment}"
    return python.rstrip(), outputs


def line_matches_prefix(line: str, prefix: str) -> str | None:
    if line.startswith(prefix):
        return line[len(prefix) :].strip()
    return None


def get_unique_name(name: str, names: set[str]) -> str:
    check_name = name
    occurrence = 2
    while check_name in names:
        check_name = f"{name}_{occurrence}"
        occurrence += 1
    names.add(check_name)
    return check_name


def parse_file(path: Path) -> tuple[list[str], list[TestCase]]:
    preamble = list[str]()
    cases = list[TestCase]()
    seen_case_names = set[str]()
    lines = path.read_text(encoding="utf8").splitlines()
    current_case: TestCase | None = None
    src_line = 0  # original line number in .test file ignoring continuations
    line_num = 0  # logical line number (does not increment when continuations are present)
    current_line_collector: list[str] = preamble
    while lines:
        src_line += 1
        line_num += 1
        line = lines.pop(0)
        if case_name := line_matches_prefix(line, CASE_PREFIX):
            # new case
            case_name = get_unique_name(case_name, seen_case_names)
            current_case = TestCase(name=case_name, src_line=src_line)
            cases.append(current_case)
            current_line_collector = current_case.current_file.body
        elif case_path := line_matches_prefix(line, PATH_PREFIX):
            if not current_case:
                raise ValueError(f"Path encountered before a case is defined {path}:{line_num}")
            # create a new file if current_file already has content or path is already defined
            if current_case.current_file.body or current_case.current_file.path:
                current_case.add_new_file()
            assert current_case.current_file.path is None
            current_case.current_file.path = Path(case_path)
            current_line_collector = current_case.current_file.body
        elif template := line_matches_prefix(line, TEMPLATE_PREFIX):
            if not current_case:
                raise ValueError(
                    f"Template encountered before a case is defined {path}:{line_num}"
                )
            template_var_name, template_var_value = parse_template_key_value(template)
            current_case.template_vars[template_var_name] = template_var_value
        elif maybe_collecting_output_for := line_matches_prefix(line, EXPECTED_PREFIX):
            if not current_case:
                raise ValueError(
                    f"Expected encountered before a case is defined {path}:{line_num}"
                )
            match maybe_collecting_output_for:
                case "awst":
                    current_line_collector = []
                    current_case.current_file.expected_awst = current_line_collector
                case _:
                    raise ValueError(f"Unrecognized expected type {path}:{line_num}")
        else:
            current_line_collector.append(line)
            if current_case:
                current_file = current_case.current_file
                python, output = get_python_expected_output(line)
                file_line_num = len(current_file.body)
                current_file.expected_output.setdefault(file_line_num, []).extend(output)

                while line.endswith(LINE_CONTINUATION):
                    current_case.approved_case_source.append(line)
                    line = lines.pop(0)
                    python, output = get_python_expected_output(line)

                    if python.strip():
                        raise ValueError(
                            f"Unexpected python `{python}`, continuations only supported "
                            f"for case comment assertions"
                        )
                    current_file.expected_output.setdefault(file_line_num, []).extend(output)

        if current_case:
            current_case.approved_case_source.append(line)
    return preamble, cases


def get_test_lines_to_match_output(
    test_case: TestCase, test_case_error: TestCaseOutputDifferenceError
) -> list[str]:
    expected = list[str]()
    expected.append(f"{CASE_PREFIX} {test_case.name}")
    for template in test_case.template_vars:
        expected.append(f"{TEMPLATE_PREFIX} {template}")
    for test_file in test_case.files:
        if test_file.path:
            expected.append(f"{PATH_PREFIX} {test_file.path}")
        for line_num, line in enumerate(test_file.body, start=1):
            python, _ = get_python_expected_output(line)
            correct_errors = test_file.expected_output.get(line_num, [])[:]

            if test_file.src_path:
                for missing in test_case_error.missing_output.get(test_file.src_path, {}).get(
                    line_num, []
                ):
                    correct_errors.remove(missing)
                for unexpected in test_case_error.unexpected_output.get(
                    test_file.src_path, {}
                ).get(line_num, []):
                    correct_errors.append(unexpected)

            if correct_errors:
                line_width = len(python) * " "
                line_join = f" {LINE_CONTINUATION}\n{line_width}"

                commented_lines = line_join.join(
                    [f" {CASE_COMMENT} {error.as_comment()}" for error in correct_errors]
                ).splitlines()
                commented_lines[0] = f"{python}{commented_lines[0]}"
                expected.extend(commented_lines)
            else:
                expected.append(python)
        if test_file.expected_awst is not None:
            expected.append(f"{EXPECTED_PREFIX} awst")
            awst = test_file.expected_awst
            if test_case.failure and test_file.src_path:
                received_awst = test_case.failure.unexpected_awst.get(test_file.src_path)
                if received_awst is not None:
                    awst = received_awst
            expected.extend(awst)
    return expected


def compile_and_update_cases(cases: list[TestCase]) -> None:
    with tempfile.TemporaryDirectory() as root_dir_str, logging_context() as awst_log_ctx:
        root_dir = Path(root_dir_str).resolve()
        srcs = list[Path]()
        case_path = dict[TestCase, Path]()
        # prepare temp directory for each case
        for case in cases:
            case_dir = root_dir
            file, *other_files = case.files
            if other_files:
                case_path[case] = case_dir = case_dir / get_python_file_name(case.name)
            else:
                case_path[case] = case_dir / (file.path or f"{get_python_file_name(case.name)}.py")
            case_dir.mkdir(parents=True, exist_ok=True)
            for file in case.files:
                file_name = file.path or f"{get_python_file_name(case.name)}.py"
                tmp_src = (case_dir / file_name).resolve()
                tmp_src.parent.mkdir(parents=True, exist_ok=True)
                tmp_src.write_text("\n".join(file.body), encoding="utf8")
                srcs.append(tmp_src)
                file.src_path = tmp_src
        puyapy_options = PuyaPyOptions(
            paths=srcs,
            output_bytecode=True,
        )
        parse_result = parse_python(puyapy_options.paths)
        # lower each case further if possible and process
        for case in cases:
            # lower awst for each case individually to order to get any output
            # from lower layers
            # this needs a new logging context so AWST errors from other cases
            # are not seen
            case_options = attrs.evolve(
                puyapy_options, cli_template_definitions=case.template_vars
            )
            case_parse_result = narrowed_parse_result(parse_result, case_path[case])
            with (
                contextlib.suppress(SystemExit),
                logging_context() as case_log_ctx,
                log_exceptions(),
            ):
                case_awst, case_compilation_set = transform_ast(case_parse_result, puyapy_options)
                case_log_ctx.logs.extend(filter_logs(awst_log_ctx.logs, case))
                awst_to_teal(
                    case_log_ctx,
                    case_options,
                    {k: Path() for k in case_compilation_set},
                    case_parse_result.sources_by_path,
                    case_awst,
                    write=False,
                )
            process_test_case(case, case_log_ctx.logs, case_awst)


def filter_logs(captured_logs: list[Log], case: TestCase) -> Iterator[Log]:
    for file in case.files:
        path = file.src_path
        assert path is not None
        abs_path = path.resolve()
        yield from (record for record in captured_logs if record.file == abs_path)


def get_python_file_name(name: str) -> str:
    def is_valid(char: str) -> bool:
        return char.isalnum() or char == "_"

    python_name = "".join(filter(is_valid, name.replace(" ", "_")))
    return python_name


def map_error_tuple_to_dict(errors: set[tuple[int, TestCaseOutput]]) -> OutputMapping:
    result: OutputMapping = OutputMapping()
    for line, error in errors:
        result.setdefault(line, []).append(error)
    return result


def process_test_case(case: TestCase, captured_logs: Sequence[Log], awst: AWST) -> None:
    if case.failure:
        return
    missing_output = dict[Path, OutputMapping]()
    unexpected_output = dict[Path, OutputMapping]()
    unexpected_awst = dict[Path, list[str]]()
    for file in case.files:
        path = file.src_path
        assert path is not None
        expected_output = {
            (line, message)
            for line, messages in file.expected_output.items()
            for message in messages
        }
        seen_output = {
            (
                record.line,
                TestCaseOutput(
                    level=record.level,
                    output=record.message.strip(),
                ),
            )
            for record in captured_logs
            if record.line is not None and record.level >= MIN_LEVEL_TO_REPORT
        }
        file_missing_output = expected_output - seen_output
        file_unexpected_output = seen_output - expected_output
        if file_missing_output:
            missing_output[path] = map_error_tuple_to_dict(file_missing_output)
        if file_unexpected_output:
            unexpected_output[path] = map_error_tuple_to_dict(file_unexpected_output)

        if file.expected_awst:
            assert file.src_path is not None
            observed_awst = trim_empty_lines(module_to_awst_repr(awst, file.src_path))
            expected_awst = trim_empty_lines(file.expected_awst)
            if observed_awst != expected_awst:
                unexpected_awst[path] = observed_awst

    if missing_output or unexpected_output or unexpected_awst:
        case.failure = TestCaseOutputDifferenceError(
            missing_output=missing_output,
            unexpected_output=unexpected_output,
            unexpected_awst=unexpected_awst,
        )


def report_test_case_error(
    test_case_src_path: Path, test_case: TestCase, test_case_error: TestCaseOutputDifferenceError
) -> str:
    errors = list[str]()
    max_width = max(len(b) for case_file in test_case.files for b in case_file.body)
    for test_file in test_case.files:
        if test_file.path:
            errors.append(f"## path: {test_file.path}")

        if test_file.src_path:
            file_missing_output = test_case_error.missing_output.get(test_file.src_path, {})
            file_unexpected_output = test_case_error.unexpected_output.get(test_file.src_path, {})
            if file_missing_output or file_unexpected_output:
                for line_num, line in enumerate(test_file.body, start=1):
                    annotated_line: str = line

                    if test_file.src_path:
                        missing_output = file_missing_output.get(line_num, [])
                        unexpected_output = file_unexpected_output.get(line_num, [])

                        if missing_output or unexpected_output:
                            annotated_line = annotated_line.ljust(max_width)
                            if missing_output and unexpected_output:
                                annotated_line += " <----wrong----- " + " / ".join(
                                    e.as_comment() for e in unexpected_output
                                )
                            elif missing_output:
                                annotated_line += " <---missing---- "
                            elif unexpected_output:
                                annotated_line += " <--unexpected-- " + " / ".join(
                                    e.as_comment() for e in unexpected_output
                                )
                            annotated_line += (
                                f" (file://{test_case_src_path}:{test_case.src_line + line_num})"
                            )
                    errors.append(annotated_line)
            if unexpected_awst := test_case_error.unexpected_awst.get(test_file.src_path):
                assert test_file.expected_awst is not None
                errors.extend(
                    [
                        f"test_source: file://{test_case_src_path}:{test_case.src_line}",
                        "AWST Difference:",
                        *difflib.ndiff(test_file.expected_awst, unexpected_awst),
                    ]
                )
    return "\n".join(errors)


class TestItem(pytest.Item):
    def __init__(self, *, test_case: TestCase, **kwargs: t.Any):
        super().__init__(**kwargs)
        self.test_case = test_case

    def runtest(self) -> None:
        # test case has already been processed, but indicate failure if it failed
        if self.test_case.failure:
            raise self.test_case.failure

    def repr_failure(
        self,
        excinfo: pytest.ExceptionInfo[BaseException],
        _style: str | None = None,
    ) -> str | _pytest._code.code.TerminalRepr:
        match excinfo.value:
            case TestCaseOutputDifferenceError() as test_case_error:
                assert self.parent is not None
                return report_test_case_error(self.parent.path, self.test_case, test_case_error)
            case _:
                return super().repr_failure(excinfo)

    def reportinfo(self) -> tuple[Path, int | None, str]:
        assert self.parent
        return self.parent.path, self.test_case.src_line, self.name


class TestFile(pytest.File):
    def __init__(self, *args: t.Any, **kwargs: t.Any):
        super().__init__(*args, **kwargs)
        self.cases = list[TestCase]()
        self.preamble = list[str]()
        self.compile_error: PuyaError | None = None
        self.auto_update_output = bool(self.config.getoption("test_auto_update"))
        dist_option = self.config.getoption("dist")
        if self.auto_update_output and dist_option and dist_option != "no":
            # don't allow updating output if tests are being executed in parallel
            self.auto_update_output = False
            # TODO: work out how to inform the user of this
            print(  # noqa: T201
                "`--test-auto-update` ignored due to --dist option. Use `--dist no` to enable"
            )

    def collect(self) -> t.Iterable[pytest.Item | pytest.Collector]:
        self.preamble, self.cases = parse_file(self.path)
        test_items = [
            TestItem.from_parent(self, name=case.name, test_case=case) for case in self.cases
        ]
        return test_items

    def get_expected_output(self) -> list[str]:
        lines = self.preamble[:]
        for case in self.cases:
            expected_output = (
                get_test_lines_to_match_output(case, case.failure)
                if case.failure is not None
                else case.approved_case_source
            )
            lines.extend(expected_output)
        lines.append("")
        return lines

    def setup(self) -> None:
        # TODO: find a better way to improve performance
        # running multiple cases at once is a lot faster due to less mypy overhead
        # however a ParseError in a single case will effect all cases which is not ideal
        try:
            compile_and_update_cases(self.cases)
        except (PuyaError, SystemExit) as ex:
            pytest.fail(f"Unhandled compiler error: {ex}", pytrace=False)
        except BaseException as ex:
            # unexpected error, fail immediately
            pytest.fail(f"Unexpected error: {ex!r}", pytrace=False)

    def teardown(self) -> None:
        if self.auto_update_output:
            approval = self.path
            approval_suffix: str | None = self.config.getoption("test_approval_suffix")
            if approval_suffix is not None:
                if not approval_suffix.startswith("."):
                    approval_suffix = f".{approval_suffix}"
                approval = approval.with_suffix(approval_suffix)
            approval.write_text("\n".join(self.get_expected_output()), encoding="utf8")


def trim_empty_lines(lines: list[str]) -> list[str]:
    start = len(lines)
    end = 0
    for idx, line in enumerate(lines):
        if line:
            start = min(idx, start)
            end = max(idx, end)
    return lines[start : end + 1]


def module_to_awst_repr(awst: AWST, src_path: Path) -> list[str]:
    visitor = ToCodeVisitor()
    filtered_awst = [n for n in awst if n.source_location.file == src_path]
    return visitor.visit_module(filtered_awst).splitlines()
