import os
import shutil

from tests import VCS_ROOT
from tests.utils import (
    OPT_SUFFIXES,
    PuyaTestCase,
    get_puya_options_for_optimization,
)
from tests.utils.compile import compile_from_test_case, log_to_str, normalize_arc56
from tests.utils.git import check_for_diff

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
}


def test_compile(test_case: PuyaTestCase) -> None:
    diff = compile_test_case(test_case)
    # bool conversion here results in a nicer assertion display if there is a diff
    has_diff = bool(diff)
    assert not has_diff, f"Uncommitted changes were found:\n{diff}"


def compile_test_case(test_case: PuyaTestCase) -> str | None:
    _remove_output(test_case)
    for opt_level in (0, 1, 2):
        suffix = OPT_SUFFIXES[opt_level]
        log_path = test_case.path / f"puya{suffix}.log"
        out_dir = test_case.test_case / f"out{suffix}"
        options = get_puya_options_for_optimization(opt_level)
        compile_result = compile_from_test_case(
            test_case,
            out_dir=out_dir,
            **options,
        )
        logs = "\n".join(log_to_str(log_, test_case.root) for log_ in compile_result.logs)
        log_path.write_text(logs, encoding="utf8")
        normalize_arc56(out_dir)
    return check_for_diff(test_case.path, VCS_ROOT)


def _remove_output(test_case: PuyaTestCase) -> None:
    path = test_case.test_case
    for out_suffix in OPT_SUFFIXES.values():
        (path / f"puya{out_suffix}.log").unlink(missing_ok=True)
        out_dir = path / f"out{out_suffix}"
        if not out_dir.exists():
            continue
        for prev_out_file in out_dir.iterdir():
            if prev_out_file.is_dir():
                shutil.rmtree(prev_out_file)
            else:
                prev_out_file.unlink()
