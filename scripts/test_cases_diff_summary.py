#!/usr/bin/env python3
import argparse
import contextlib
import enum
import io
import subprocess
import tarfile
import tomllib
from collections.abc import Iterable
from pathlib import Path

import attrs
import prettytable

from puya.utils import StableSet

_SCRIPTS_DIR = Path(__file__).parent
_ROOT_DIR = _SCRIPTS_DIR.parent
_OPT_LEVEL = {
    "out_unoptimized": 0,
    "out": 1,
    "out_O2": 2,
}


@attrs.frozen
class TestCase:
    root: str
    name: str


@attrs.frozen
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
    none = "-"


@attrs.define
class ArtifactDiff:
    name: str
    status: Status
    num_bytes: list[int] = attrs.field(factory=lambda: [0] * 3, on_setattr=attrs.setters.frozen)
    num_ops: list[int] = attrs.field(factory=lambda: [0] * 3, on_setattr=attrs.setters.frozen)

    @property
    def changed(self) -> bool:
        return any((*self.num_bytes, *self.num_ops))


def main() -> None:
    options = _get_options()
    sizes = _summarize_sizes(options.before, options.after)
    summary = _render_summary(sizes, show_all=options.verbose)
    print(summary)


def _get_options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize compiler output differences between branches",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-b", "--before", type=str, default="origin/main", help="base git tag to compare"
    )
    parser.add_argument(
        "-a", "--after", type=str, default="HEAD", help="target git tag to compare"
    )
    parser.add_argument("-v", "--verbose", action="store_true", default=False)
    return parser.parse_args()


def _summarize_sizes(before_ref: str, after_ref: str) -> dict[Artifact, ArtifactDiff]:
    before = _get_git_files(before_ref)
    after = _get_git_files(after_ref)

    before_contracts = _group_contracts_by_test_case(before)
    after_contracts = _group_contracts_by_test_case(after)
    before_stats = {Path(p): c for p, c in before.items() if p.endswith(".stats.txt")}
    after_stats = {Path(p): c for p, c in after.items() if p.endswith(".stats.txt")}
    all_stat_paths: list[Path] = sorted({*before_stats, *after_stats})

    summary = _initialize_diffs(all_stat_paths, before_contracts, after_contracts)
    _process_change_set(summary, before_stats, -1)
    _process_change_set(summary, after_stats, 1)
    return summary


def _get_git_files(tag: str) -> dict[str, str]:
    if tag == ".":
        stash_ouput = subprocess.run(
            ["git", "stash", "create"], capture_output=True, check=True, cwd=_ROOT_DIR
        )
        tag = stash_ouput.stdout.decode("utf8").strip()
    cmd_result = subprocess.run(
        [
            "git",
            "archive",
            tag,
            "--",
            ":(glob)examples/*/*.py",
            ":(glob)test_cases/*/*.py",
            "*/*.stats.txt",
        ],
        capture_output=True,
        check=False,
        cwd=_ROOT_DIR,
    )
    if cmd_result.returncode == 128 and cmd_result.stderr.endswith(b"did not match any files\n"):
        return {}
    assert cmd_result.returncode == 0, f"git cmd failed: {cmd_result.stderr.decode('utf8')}"

    result = {}
    with tarfile.open(fileobj=io.BytesIO(cmd_result.stdout)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            file = tar.extractfile(member)
            assert file is not None, f"could not read file: {member.name}"
            content = file.read()
            with contextlib.suppress(UnicodeDecodeError):
                # uh oh 🍝
                result[member.name] = content.decode("utf8")
    return result


def _initialize_diffs(
    stat_paths: list[Path],
    before: dict[TestCase, dict[str, str]],
    after: dict[TestCase, dict[str, str]],
) -> dict[Artifact, ArtifactDiff]:
    # determine unique artifact across before and after
    all_contracts = StableSet[Artifact]()
    test_case_contracts = dict[TestCase, set[str]]()
    for stat_path in stat_paths:
        contract, _ = _get_artifact_opt_from_stat_path(stat_path)
        all_contracts.add(contract)
        test_case_contracts.setdefault(contract.test_case, set()).add(contract.name)

    # initialize a diff for each artifact
    summary = dict[Artifact, ArtifactDiff]()
    for contract in all_contracts:
        before_src = _find_artifact_src(before, contract)
        after_src = _find_artifact_src(after, contract)

        # determine if there was a change in the src code
        status = Status.none
        if before_src is None and after_src:
            status = Status.added
        elif before_src and after_src is None:
            status = Status.deleted
        elif before_src != after_src:
            status = Status.modified
        name = contract.test_case.name
        if len(test_case_contracts[contract.test_case]) > 1:
            name += f"/{contract.name}"
        summary[contract] = ArtifactDiff(name=name, status=status)
    return summary


def _get_artifact_opt_from_stat_path(path: Path) -> tuple[Artifact, int]:
    root_dir, test_case_dir, opt_str, stats_file = path.parts
    test_case = TestCase(root_dir, test_case_dir)
    contract_name, *_ = stats_file.split(".")
    contract = Artifact(test_case, contract_name)
    opt = _OPT_LEVEL[opt_str]
    return contract, opt


def _find_artifact_src(
    artifact_srcs: dict[TestCase, dict[str, str]], artifact: Artifact
) -> str | None:
    artifacts = artifact_srcs.get(artifact.test_case, {})
    name = artifact.name
    for search in (
        # check for name overrides before class/def incase there is aliasing
        f'name="{name}"',
        f"class {name}",
        f"def {name}",
    ):
        for contents in artifacts.values():
            if search in contents:
                return contents
    return None


def _process_change_set(
    diffs: dict[Artifact, ArtifactDiff],
    stats: dict[Path, str],
    modifier: int,
) -> None:
    for stat_path, stat_contents in stats.items():
        contract, opt = _get_artifact_opt_from_stat_path(stat_path)
        tally = diffs[contract]
        program_stats = tomllib.loads(stat_contents)
        tally.num_bytes[opt] += program_stats["total_bytes"] * modifier
        tally.num_ops[opt] += program_stats["total_ops"] * modifier


def _group_contracts_by_test_case(files: dict[str, str]) -> dict[TestCase, dict[str, str]]:
    result = dict[TestCase, dict[str, str]]()
    for path_str, contents in files.items():
        path = Path(path_str)
        if path.suffix != ".py":
            continue
        *test_case_parts, contract = path.parts
        test_case = TestCase(*test_case_parts)
        result.setdefault(test_case, {})[contract] = contents
    return result


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
    total = ArtifactDiff("Total", Status.none)
    for diff in diffs.values():
        # only include diff in tally if src was not modified
        if diff.status == Status.none:
            for i in range(3):
                total.num_bytes[i] += diff.num_bytes[i]
                total.num_ops[i] += diff.num_ops[i]
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
            all_values = [*diff.num_bytes[1:], *diff.num_ops[1:]]
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
                *_render_opt_values(diff.num_bytes, include_emoji=include_emoji),
                *_render_opt_values(diff.num_ops, include_emoji=include_emoji),
            ]
        )
    return writer.get_string()


def _render_opt_values(values: list[int], *, include_emoji: bool) -> Iterable[str]:
    last_value = None
    for opt, value in enumerate(values):
        if value == 0:
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
    main()
