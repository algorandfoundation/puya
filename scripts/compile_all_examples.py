#!/usr/bin/env python3
import argparse
import json
import operator
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import attrs

from puya.log import configure_stdio

SCRIPT_DIR = Path(__file__).parent
GIT_ROOT = SCRIPT_DIR.parent
CONTRACT_ROOT_DIRS = [
    GIT_ROOT / "examples",
    GIT_ROOT / "test_cases",
]
ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
}
# iterate optimization levels first and with O1 first and then cases, this is a workaround
# to prevent race conditions that occur when the mypy parsing stage of O0, O2 tries to
# read the client_<contract>.py output from the 01 level before it is finished writing to
# disk
DEFAULT_OPTIMIZATION = (1, 0, 2)


def get_root_and_relative_path(path: Path) -> tuple[Path, Path]:
    for root in CONTRACT_ROOT_DIRS:
        if path.is_relative_to(root):
            return root, path.relative_to(root)
    raise RuntimeError(f"{path} is not relative to a known example")


def get_unique_name(path: Path) -> str:
    _, rel_path = get_root_and_relative_path(path)
    # strip suffixes
    while rel_path.suffixes:
        rel_path = rel_path.with_suffix("")

    use_parts = []
    for part in rel_path.parts:
        if "MyContract" in part:
            use_parts.append("".join(part.split("MyContract")))
        elif "Contract" in part:
            use_parts.append("".join(part.split("Contract")))
        elif part.endswith((f"out{SUFFIX_O0}", f"out{SUFFIX_O1}", f"out{SUFFIX_O2}")):
            pass
        else:
            use_parts.append(part)
    return "/".join(filter(None, use_parts))


@attrs.define
class CompilationResult:
    rel_path: str
    ok: bool
    bin_files: list[Path]
    stdout: str


def _stabilise_logs(stdout: str) -> list[str]:
    return [
        line.replace("\\", "/").replace(str(GIT_ROOT).replace("\\", "/"), "<git root>")
        for line in stdout.splitlines()
        if not line.startswith(
            (
                "debug: Skipping algopy stub ",
                "debug: Skipping typeshed stub ",
                "debug: Skipping stdlib stub ",
                "debug: Building AWST for ",
                "debug: Discovered user module ",
                # ignore platform specific paths
                "debug: Using python executable: ",
                "debug: Using python site-packages: ",
                "debug: Found algopy: ",
            )
        )
    ]


def checked_compile(p: Path, flags: list[str], *, out_suffix: str) -> CompilationResult:
    assert p.is_dir()
    out_dir = (p / f"out{out_suffix}").resolve()
    template_vars_path = p / "template.vars"

    root, rel_path_ = get_root_and_relative_path(p)
    rel_path = str(rel_path_)

    if out_dir.exists():
        for prev_out_file in out_dir.iterdir():
            if prev_out_file.is_dir():
                shutil.rmtree(prev_out_file)
            elif prev_out_file.suffix != ".log":
                prev_out_file.unlink()
    cmd = [
        "uv",
        "run",
        "puyapy",
        *flags,
        f"--out-dir={out_dir}",
        "--output-destructured-ir",
        "--output-bytecode",
        "--log-level=debug",
        "--output-op-statistics",
        *_load_template_vars(template_vars_path),
        rel_path,
    ]
    result = subprocess.run(
        cmd,
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=ENV_WITH_NO_COLOR,
        encoding="utf-8",
    )
    bin_files_written = re.findall(r"info: Writing (.+\.bin)", result.stdout)

    # normalize ARC-56 output
    arc56_files_written = re.findall(r"info: Writing (.+\.arc56\.json)", result.stdout)
    for arc56_file in arc56_files_written:
        _normalize_arc56(root / arc56_file)

    log_path = p / f"puya{out_suffix}.log"
    log_txt = "\n".join(_stabilise_logs(result.stdout))
    log_path.write_text(log_txt, encoding="utf8")

    ok = result.returncode == 0
    return CompilationResult(
        rel_path=rel_path,
        ok=ok,
        bin_files=[root / p for p in bin_files_written],
        stdout=result.stdout if not ok else "",  # don't thunk stdout if no errors
    )


def _normalize_arc56(path: Path) -> None:
    arc56 = json.loads(path.read_text(encoding="utf8"))
    compiler_version = arc56.get("compilerInfo", {}).get("compilerVersion", {})
    compiler_version["major"] = 99
    compiler_version["minor"] = 99
    compiler_version["patch"] = 99
    path.write_text(json.dumps(arc56, indent=4), encoding="utf8")


def _load_template_vars(path: Path) -> Iterable[str]:
    if path.exists():
        for line in path.read_text("utf8").splitlines():
            if line.startswith("prefix="):
                prefix = line.removeprefix("prefix=")
                yield f"--template-vars-prefix={prefix}"
            else:
                yield f"-T={line}"


SUFFIX_O0 = "_unoptimized"
SUFFIX_O1 = ""
SUFFIX_O2 = "_O2"


def _compile_for_level(arg: tuple[Path, int]) -> tuple[CompilationResult, int]:
    p, optimization_level = arg
    if optimization_level == 0:
        flags = [
            "-O0",
            "--no-output-arc32",
            "--no-output-arc56",
        ]
        out_suffix = SUFFIX_O0
    elif optimization_level == 2:
        flags = [
            "-O2",
            "--no-output-arc32",
            "--no-output-arc56",
            "-g0",
        ]
        out_suffix = SUFFIX_O2
    else:
        assert optimization_level == 1
        flags = [
            "-O1",
            "--output-awst",
            "--output-ssa-ir",
            "--output-optimization-ir",
            "--output-memory-ir",
            "--output-client",
            "--output-source-map",
        ]
        out_suffix = SUFFIX_O1
    result = checked_compile(p, flags=flags, out_suffix=out_suffix)
    return result, optimization_level


@attrs.define(kw_only=True)
class CompileAllOptions:
    limit_to: list[Path] = attrs.field(factory=list)
    optimization_level: list[int] = attrs.field(factory=list)


def _run(options: CompileAllOptions) -> None:
    limit_to = options.limit_to
    if limit_to:
        to_compile = [Path(x).resolve() for x in limit_to]
    else:
        to_compile = [
            item
            for root in CONTRACT_ROOT_DIRS
            for item in root.iterdir()
            if item.is_dir() and any(item.glob("*.py"))
        ]

    failures = list[tuple[str, str]]()
    # use selected opt levels, but retain original order
    opt_levels = [
        o
        for o in DEFAULT_OPTIMIZATION
        if o in (options.optimization_level or DEFAULT_OPTIMIZATION)
    ]
    with ProcessPoolExecutor() as executor:
        args = [(case, level) for level in opt_levels for case in to_compile]
        for compilation_result, level in executor.map(_compile_for_level, args):
            rel_path = compilation_result.rel_path
            case_name = f"{rel_path} -O{level}"
            if compilation_result.ok:
                print(f"✅  {case_name}")
            else:
                print(f"💥 {case_name}", file=sys.stderr)
                failures.append((case_name, compilation_result.stdout))

    if failures:
        print("Compilation failures:")
        for name, stdout in sorted(failures, key=operator.itemgetter(0)):
            print(f" ~~~ {name} ~~~ ")
            print(
                "\n".join(
                    ln
                    for ln in stdout.splitlines()
                    if (ln.startswith("debug: Traceback ") or not ln.startswith("debug: "))
                )
            )
    sys.exit(len(failures))


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("limit_to", type=Path, nargs="*", metavar="LIMIT_TO")
    parser.add_argument(
        "-O",
        "--optimization-level",
        action="extend",
        type=int,
        choices=DEFAULT_OPTIMIZATION,
        nargs="+",
        help="Set optimization level of output TEAL / AVM bytecode",
    )
    options = CompileAllOptions()
    parser.parse_args(namespace=options)
    _run(options)


if __name__ == "__main__":
    main()
