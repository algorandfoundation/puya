#!/usr/bin/env python3
import contextlib
import enum
import hashlib
import io
import subprocess
import tarfile
import tomllib
import typing
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

import attrs
import cyclopts
import prettytable

_SCRIPTS_DIR = Path(__file__).parent
_ROOT_DIR = _SCRIPTS_DIR.parent
_OPT_LEVELS = {
    "out_unoptimized": 0,
    "out": 1,
    "out_O2": 2,
}

app = cyclopts.App(help_on_error=True)


@app.default
def main(
    *,
    before: typing.Annotated[str, cyclopts.Parameter(alias="-b")] = "origin/main",
    after: typing.Annotated[str, cyclopts.Parameter(alias="-a")] = "HEAD",
    verbose: typing.Annotated[bool, cyclopts.Parameter(alias="-v", negative=())] = False,
) -> None:
    """
    Summarize compiler output differences between branches

    Parameters:
        before: Base git tag to compare
        after: Target git tag to compare (or . for working copy)
        verbose: Show all rows, including unchanged ones
    """
    before_files = _get_git_files(before)
    after_files = _get_git_files(after)

    diffs = _calculate_diffs(before_files, after_files)
    summary = _render_summary(diffs, show_all=verbose)
    print(summary)


@attrs.frozen(order=True)
class TestCase:
    root: str
    name: str


@attrs.frozen(order=True)
class Artifact:
    test_case: TestCase
    name: str


class Status(enum.StrEnum):
    added = "🆕"
    deleted = "🗑️"
    modified = "✏️"
    increase = "🔺"
    decrease = "🟢"
    indeterminate = "🤔"
    error = "💥"
    none = "-"


@attrs.frozen
class Size:
    num_bytes: int = 0
    num_ops: int = 0
    errored: bool = False

    def __add__(self, other: "Size") -> "Size":
        return Size(
            num_bytes=self.num_bytes + other.num_bytes,
            num_ops=self.num_ops + other.num_ops,
            errored=self.errored or other.errored,
        )

    def __mul__(self, factor: int) -> "Size":
        return attrs.evolve(self, num_bytes=self.num_bytes * factor, num_ops=self.num_ops * factor)

    @property
    def changed(self) -> bool:
        return bool(self.errored or self.num_bytes or self.num_ops)


@attrs.define
class ArtifactDiff:
    name: str
    status: Status
    sizes: dict[int, Size] = attrs.field(
        factory=lambda: {opt_level: Size() for opt_level in _OPT_LEVELS.values()}, init=False
    )

    @property
    def changed(self) -> bool:
        return any(opt.changed for opt in self.sizes.values())


@attrs.define
class ArtifactDetails:
    src: str | None = None
    stats: dict[int, Size] = attrs.field(factory=lambda: defaultdict[int, Size](Size))


def _get_git_files(tag: str) -> dict[str, str]:
    if tag == ".":
        stash_output = subprocess.run(
            ["git", "stash", "create"], capture_output=True, check=True, cwd=_ROOT_DIR
        )
        # if nothing to stash output will be empty
        tag = stash_output.stdout.decode("utf8").strip() or "HEAD"
    # note: cmd will fail if there is not at least one match for each glob
    cmd_result = subprocess.run(
        [
            "git",
            "archive",
            tag,
            "--",
            ":(glob)examples/*/*.py",
            ":(glob)test_cases*/*/*",  # .py, .awst.json, .awst.json.gz
            ":(glob)examples/**/*.stats.txt",
            ":(glob)test_cases*/**/*.stats.txt",
        ],
        capture_output=True,
        check=False,
        cwd=_ROOT_DIR,
    )
    assert cmd_result.returncode == 0, f"git cmd failed: {cmd_result.stderr.decode('utf8')}"

    result = {}
    with tarfile.open(fileobj=io.BytesIO(cmd_result.stdout)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            file = tar.extractfile(member)
            assert file is not None, f"could not read file: {member.name}"
            content = file.read()
            if member.name.endswith(".gz"):
                # just hash gz files
                result[member.name] = hashlib.sha512(content).hexdigest()
            else:
                with contextlib.suppress(UnicodeDecodeError):
                    # uh oh 🍝
                    result[member.name] = content.decode("utf8")
    return result


def _calculate_diffs(
    before_files: dict[str, str], after_files: dict[str, str]
) -> dict[Artifact, ArtifactDiff]:
    before = _parse_files(before_files)
    after = _parse_files(after_files)
    all_artifacts = sorted({*before, *after})

    artifacts_per_test_case = Counter(a.test_case for a in all_artifacts)

    # build a diff per artifact
    diffs = dict[Artifact, ArtifactDiff]()
    for artifact in all_artifacts:
        artifact_before = before.get(artifact)
        artifact_after = after.get(artifact)

        name = artifact.test_case.name
        if artifacts_per_test_case[artifact.test_case] > 1:
            name += f"/{artifact.name}"

        diff = diffs[artifact] = ArtifactDiff(name=name, status=Status.none)
        # determine if there was a change in the src code, or a compile error
        if artifact_before is None and artifact_after:
            diff.status = Status.added
        elif artifact_before and artifact_after is None:
            diff.status = Status.deleted
        else:
            assert artifact_before
            assert artifact_after
            missing_opt_stats = artifact_before.stats.keys() ^ artifact_after.stats.keys()
            if missing_opt_stats:
                for missing_opt_level in missing_opt_stats:
                    diff.sizes[missing_opt_level] = Size(errored=True)
                diff.status = Status.error
            elif artifact_before.src != artifact_after.src:
                diff.status = Status.modified

        # accumulate sizes
        for artifact_details, sign in ((artifact_before, -1), (artifact_after, 1)):
            if artifact_details:
                for opt_level, opt in artifact_details.stats.items():
                    diff.sizes[opt_level] += opt * sign
    return diffs


def _parse_files(files: dict[str, str]) -> dict[Artifact, ArtifactDetails]:
    result = defaultdict[Artifact, ArtifactDetails](ArtifactDetails)
    test_case_srcs = defaultdict[TestCase, dict[Path, str]](dict)
    for path_str, contents in files.items():
        path = Path(path_str)
        # collect src files by test case
        if path.name.endswith((".py", ".awst.json", ".awst.json.gz")):
            root, test_case_name, _ = path.parts
            test_case = TestCase(root=root, name=test_case_name)
            test_case_srcs[test_case][path] = contents
        # collect and accumulate artifact stats
        elif path.name.endswith(".stats.txt"):
            contract, opt_level = _parse_stat_path(path)
            stats = tomllib.loads(contents)
            details = result[contract]
            details.stats[opt_level] += Size(
                num_bytes=stats["total_bytes"], num_ops=stats["total_ops"]
            )

    # update artifacts with src
    for artifact, details in result.items():
        srcs = test_case_srcs[artifact.test_case]
        if artifact.test_case.root == "test_cases_awst":
            details.src = _find_artifact_awst_src(srcs)
        else:
            details.src = _find_artifact_python_src(srcs, artifact.name)
    return result


def _parse_stat_path(path: Path) -> tuple[Artifact, int]:
    root_dir, test_case_dir, opt_str, stats_file = path.parts
    test_case = TestCase(root_dir, test_case_dir)
    contract_name, *_ = stats_file.split(".")
    return Artifact(test_case, contract_name), _OPT_LEVELS[opt_str]


def _find_artifact_awst_src(
    artifact_srcs: dict[Path, str],
) -> str | None:
    awst_files = [
        contents
        for path, contents in artifact_srcs.items()
        if path.name.endswith((".awst.json", ".awst.json.gz"))
    ]
    match awst_files:
        case []:
            return None
        case [contents]:
            return contents
        case _:
            raise Exception("expected a single AWST file per test case")


def _find_artifact_python_src(artifact_srcs: dict[Path, str], name: str) -> str | None:
    for search in (
        # check for name overrides before class/def incase there is aliasing
        f'name="{name}"',
        f"class {name}",
        f"def {name}",
    ):
        for path, contents in artifact_srcs.items():
            if path.suffix == ".py" and search in contents:
                return contents
    return None


def _render_summary(diffs: dict[Artifact, ArtifactDiff], *, show_all: bool) -> str:
    writer = prettytable.PrettyTable(
        field_names=[
            "Name",
            "Status",
            "O0 bytes",
            "O1 bytes",
            "O2 bytes",
            "O0 ops",
            "O1 ops",
            "O2 ops",
        ],
        header=True,
        align="r",
    )
    writer.set_style(prettytable.TableStyle.MARKDOWN)
    writer.align["Name"] = "l"
    writer.align["|"] = "c"
    total = ArtifactDiff(name="Total", status=Status.none)
    for diff in diffs.values():
        # only include diff in tally if src was not modified and there were no errors
        if diff.status == Status.none:
            for opt_level, opt_diff in diff.sizes.items():
                total.sizes[opt_level] += opt_diff
    for diff in (*diffs.values(), total):
        if not show_all and not diff.changed:
            continue
        status = diff.status
        include_emoji = False
        if status == Status.none:
            # NOTE: emoji's are used to provide a visual hint if there was a change of interest
            #       so only include them if the src was not modified
            #       i.e. the change is strictly due to compiler output changes
            include_emoji = True
            # ignore O0
            optimized = [size for opt, size in diff.sizes.items() if opt]
            all_values = [v for o in optimized for v in (o.num_bytes, o.num_ops)]
            if all(v <= 0 for v in all_values):
                status = Status.decrease
            elif all(v >= 0 for v in all_values):
                status = Status.increase
            else:
                status = Status.indeterminate
        writer.add_row(
            [
                diff.name,
                status,
                *_render_opt_values(
                    [None if o.errored else o.num_bytes for o in diff.sizes.values()],
                    include_emoji=include_emoji,
                ),
                *_render_opt_values(
                    [None if o.errored else o.num_ops for o in diff.sizes.values()],
                    include_emoji=include_emoji,
                ),
            ]
        )
    return writer.get_string()


def _render_opt_values(values: list[int | None], *, include_emoji: bool) -> Iterable[str]:
    last_value = None
    for opt, value in enumerate(values):
        if value is None:
            yield "💥"
        elif value == 0:
            yield "-"
        else:
            if (
                # no emoji at opt 0, or repeated values to reduce visual noise
                not include_emoji or opt == 0 or last_value == value
            ):
                emoji = ""
            elif value < 0:
                emoji = Status.decrease
            else:
                emoji = Status.increase
            yield f"{value:+}{emoji}"
        last_value = value


if __name__ == "__main__":
    app()
