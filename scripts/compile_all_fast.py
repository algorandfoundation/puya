#!/usr/bin/env python3
import multiprocessing
import platform
import shutil
import subprocess
import sys
import typing
from collections.abc import Sequence
from pathlib import Path

import attrs
import cyclopts

from puya import log
from puya.errors import PuyaError
from tests import VCS_ROOT
from tests.test_compile import compile_test_case
from tests.utils import PuyaTestCase, get_test_cases
from tests.utils.compile import get_awst_cache


@attrs.frozen
class CompilationResult:
    id: str
    diff: str | None
    log_only: bool
    errors: Sequence[Exception] | None


app = cyclopts.App(help_on_error=True)


@app.default
def main(
    limit_to: typing.Annotated[
        Sequence[cyclopts.types.ExistingPath], cyclopts.Parameter(name="LIMIT_TO")
    ] = (),
    /,
) -> None:
    """
    Compiles test cases using cached AWST, useful when iterating on a feature

    Parameters:
        limit_to: Paths of test cases to filter to e.g. (test_cases/arc4_types)
    """
    _configure_logging()
    if limit_to:
        to_compile = [PuyaTestCase(path.resolve()) for path in limit_to]
    else:
        to_compile = get_test_cases()

    python_roots = sorted({tc.root for tc in to_compile if not tc.is_awst})
    if python_roots and platform.system() != "Windows":
        # warm AWST cache before forking workers
        print("Building AWST...", end="", flush=True)
        for root_dir in python_roots:
            get_awst_cache(root_dir)
        print(".", flush=True)
    diffs = 0
    failures = list[CompilationResult]()
    # fork workers if possible so they inherit the cached AWST
    try:
        ctx: multiprocessing.context.BaseContext = multiprocessing.get_context("fork")
    except ValueError:
        # fork not available on Windows, so fall back to spawn
        ctx = multiprocessing.get_context()
    statuses = []
    with ctx.Pool() as pool:
        for result in pool.imap_unordered(_compile_test_case, to_compile):
            if result.errors:
                failures.append(result)
                status = "💥"
                diffs += 1
            elif result.diff:
                if result.log_only:
                    status = "L"
                else:
                    status = "M"
                diffs += 1
            else:
                status = "."
            statuses.append(status)
            print(status, end="", flush=True)

    total = len(to_compile)
    success = total - len(failures)
    summary = f" [{success}/{total}] {diffs} changed"
    if diffs and all(status in ("L", ".") for status in statuses):
        summary += " (logs only)"
    print(summary)
    if failures:
        # reconfigure log to output errors
        _configure_logging(log.LogLevel.error)
        logger = log.get_logger("compile_all_fast")
        print(f"{len(failures)} compilation failure(s):", file=sys.stderr)
        for result in sorted(failures, key=lambda r: r.id):
            print(f"💥 {result.id}", file=sys.stderr)

            for error in result.errors or ():
                if isinstance(error, PuyaError):
                    logger.error(error.msg, location=error.location)
                else:
                    logger.exception(error)
        sys.exit(1)


def _compile_test_case(test_case: PuyaTestCase) -> CompilationResult:
    _configure_logging()  # reconfigure logging in case worker was spawned instead of forked

    diff = None
    errors = None
    log_only = False
    try:
        diff = compile_test_case(test_case)
    except* Exception as exs:
        errors = exs.exceptions
    else:
        log_only = _log_only_changes(test_case.test_case, VCS_ROOT)
    return CompilationResult(id=test_case.id, diff=diff, errors=errors, log_only=log_only)


def _log_only_changes(path: Path, cwd: Path) -> bool:
    git = shutil.which("git")
    assert git, "could not find git"
    assert path.is_dir()
    result = subprocess.run(
        [git, "status", "-s", str(path)],
        check=True,
        capture_output=True,
        cwd=cwd,
    )
    return all(
        Path(path.strip().split(" ", maxsplit=1)[1]).suffix == ".log"
        for path in result.stdout.decode("utf8").splitlines()
    )


def _configure_logging(level: log.LogLevel = log.LogLevel.critical) -> None:
    log.configure_logging(
        min_log_level=level,
        cache_logger=False,
        reconfigure_stdio=False,
    )


if __name__ == "__main__":
    app()
