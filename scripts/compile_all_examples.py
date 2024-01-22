#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import algokit_utils
import attrs
import prettytable

SCRIPT_DIR = Path(__file__).parent
GIT_ROOT = SCRIPT_DIR.parent
CONTRACT_ROOT_DIRS = [
    GIT_ROOT / "examples",
    GIT_ROOT / "test_cases",
]
SIZE_TALLY_PATH = GIT_ROOT / "examples" / "sizes.txt"
ALGOD_CLIENT = algokit_utils.get_algod_client(algokit_utils.get_default_localnet_config("algod"))
ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}


def get_root_and_relative_path(path: Path) -> tuple[Path, Path]:
    for root in CONTRACT_ROOT_DIRS:
        if path.is_relative_to(root):
            return root, path.relative_to(root)
    raise Exception(f"{path} is not relative to a known example")


def get_unique_name(path: Path) -> str:
    _, rel_path = get_root_and_relative_path(path)
    # strip suffixes
    while rel_path.suffixes:
        rel_path = rel_path.with_suffix("")

    match rel_path.parts:
        case [*other, "out", "contract"]:
            parts = other
        case [*other, "out", contract]:
            parts = [*other, contract]
        case [*all]:
            parts = all
        case _:
            raise Exception("Unexpected directory structure")
    return "/".join(parts)


@attrs.define(str=False)
class ProgramSizes:
    o1_sizes: dict[str, int] = attrs.field(factory=dict)
    o0_sizes: dict[str, int] = attrs.field(factory=dict)
    o2_sizes: dict[str, int] = attrs.field(factory=dict)

    def add(self, teal_programs: list[Path]) -> None:
        for teal in teal_programs:
            name = get_unique_name(teal)
            match teal.suffixes:
                case [".approval_unoptimized", ".teal"]:
                    self.o0_sizes[name] = get_program_size(teal)
                case [".approval", ".teal"]:
                    self.o1_sizes[name] = get_program_size(teal)
                case [".approval_O2", ".teal"]:
                    self.o2_sizes[name] = get_program_size(teal)

    @classmethod
    def read_file(cls, path: Path) -> "ProgramSizes":
        lines = path.read_text("utf-8").splitlines()
        program_sizes = ProgramSizes()
        for line in lines[1:]:
            name, unoptimized, optimized, o2 = line.rsplit(maxsplit=3)
            program_sizes.o0_sizes[name] = int(unoptimized)
            program_sizes.o1_sizes[name] = int(optimized)
            program_sizes.o2_sizes[name] = int(o2)
        return program_sizes

    def update(self, other: "ProgramSizes") -> "ProgramSizes":
        return ProgramSizes(
            o2_sizes={**self.o2_sizes, **other.o2_sizes},
            o1_sizes={**self.o1_sizes, **other.o1_sizes},
            o0_sizes={**self.o0_sizes, **other.o0_sizes},
        )

    def __str__(self) -> str:
        writer = prettytable.PrettyTable(
            field_names=["Name", "O0 size", "O1 size", "O2 size"],
            sortby="Name",
            header=True,
            border=False,
            padding_width=0,
            left_padding_width=0,
            right_padding_width=1,
            align="l",
        )
        for name, optimized in self.o1_sizes.items():
            unoptimized = self.o0_sizes[name]
            o2 = self.o2_sizes[name]
            writer.add_row([name, str(unoptimized), str(optimized), str(o2)])
        return writer.get_string()


@attrs.define
class CompilationResult:
    rel_path: str
    ok: bool
    teal_files: list[Path]
    final_ir_files: list[Path]


def get_program_size(path: Path) -> int:
    try:
        program = algokit_utils.Program(path.read_text("utf-8"), ALGOD_CLIENT)
        return len(program.raw_binary)
    except Exception as e:
        raise Exception(f"Error compiling teal application: {path}") from e


def _stabilise_logs(stdout: str) -> list[str]:
    return [
        line.replace("\\", "/").replace(str(GIT_ROOT).replace("\\", "/"), "<git root>")
        for line in stdout.splitlines()
        if not line.startswith(
            (
                "debug: Skipping puyapy stub ",
                "debug: Skipping typeshed stub ",
                "warning: Skipping stub: ",
                "debug: Skipping stdlib stub ",
                "debug: Building AWST for ",
            )
        )
    ]


def checked_compile(p: Path, flags: list[str], *, write_logs: bool = False) -> CompilationResult:
    root, rel_path_ = get_root_and_relative_path(p)
    rel_path = str(rel_path_)

    cmd = [
        "poetry",
        "run",
        "puyapy",
        *flags,
        "--out-dir=out",
        "--debug-level=1",
        "--log-level=debug",
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
    final_ir_written = re.findall(r"debug: Output IR to (.+\.destructured\.ir)", result.stdout)
    teal_files_written = re.findall(r"info: Writing (.+\.teal)", result.stdout)
    if write_logs:
        if p.is_dir():
            log_path = p / "puya.log"
        else:
            log_path = p.with_suffix(".puya.log")

        log_txt = "\n".join(_stabilise_logs(result.stdout))
        log_path.write_text(log_txt, encoding="utf8")
    return CompilationResult(
        rel_path=rel_path,
        ok=result.returncode == 0,
        teal_files=[root / p for p in teal_files_written],
        final_ir_files=[root / p for p in final_ir_written],
    )


def compile_no_optimization(p: Path) -> CompilationResult:
    result = checked_compile(
        p,
        flags=[
            "-O0",
            "--output-awst",
            "--output-destructured-ir",
        ],
        write_logs=False,
    )
    moved_teal = list[Path]()
    for teal_path in result.teal_files:
        program, *other_suffixes = teal_path.suffixes
        new_suffix = "".join((f"{program}_unoptimized", *other_suffixes))
        old_suffix = "".join(teal_path.suffixes)
        new_stem = str(teal_path.name)[: -len(old_suffix)]
        move_to = (teal_path.parent / new_stem).with_suffix(new_suffix)
        teal_path.rename(move_to)
        moved_teal.append(move_to)
    moved_ir = list[Path]()
    for final_ir_path in result.final_ir_files:
        suffix_keep, _ = final_ir_path.suffixes
        move_to = final_ir_path.with_suffix("").with_suffix(f"{suffix_keep}_unoptimized.ir")
        final_ir_path.rename(move_to)
        moved_ir.append(move_to)
    return attrs.evolve(result, teal_files=moved_teal, final_ir_files=moved_ir)


def compile_o2(p: Path) -> CompilationResult:
    result = checked_compile(
        p,
        flags=[
            "-O2",
            "--output-destructured-ir",
        ],
    )
    moved_teal = list[Path]()
    for teal_path in result.teal_files:
        program, *other_suffixes = teal_path.suffixes
        new_suffix = "".join((f"{program}_O2", *other_suffixes))
        old_suffix = "".join(teal_path.suffixes)
        new_stem = str(teal_path.name)[: -len(old_suffix)]
        move_to = (teal_path.parent / new_stem).with_suffix(new_suffix)
        teal_path.rename(move_to)
        moved_teal.append(move_to)
    moved_ir = list[Path]()
    for final_ir_path in result.final_ir_files:
        suffix_keep, _ = final_ir_path.suffixes
        move_to = final_ir_path.with_suffix("").with_suffix(f"{suffix_keep}_O2.ir")
        final_ir_path.rename(move_to)
        moved_ir.append(move_to)
    return attrs.evolve(result, teal_files=moved_teal, final_ir_files=moved_ir)


def compile_with_level1_optimizations(p: Path) -> CompilationResult:
    return checked_compile(
        p,
        flags=[
            "-O1",
            "--output-ssa-ir",
            "--output-optimization-ir",
            "--output-destructured-ir",
            "--output-memory-ir",
        ],
        write_logs=True,
    )


@attrs.define(kw_only=True)
class CompileAllOptions:
    limit_to: list[Path] = attrs.field(factory=list)
    update_sizes: bool = True


def main(options: CompileAllOptions) -> None:
    to_compile = []
    limit_to = options.limit_to
    if limit_to:
        to_compile = [Path(x).resolve() for x in limit_to]
    else:
        for root in CONTRACT_ROOT_DIRS:
            for item in root.iterdir():
                if item.is_dir():
                    if any(item.rglob("*.py")):
                        to_compile.append(item)
                elif item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
                    to_compile.append(item)
    if not limit_to:
        print("Cleaning up prior runs")
        for ext in (".teal", ".awst", ".ir"):
            for root in CONTRACT_ROOT_DIRS:
                for f in root.rglob(f"**/out/*{ext}"):
                    if f.is_file():
                        f.unlink()

    program_sizes = ProgramSizes()
    modified_teal = []
    opt_success = set()
    unopt_success = set()
    with ProcessPoolExecutor() as executor:
        print(" ~~~ RUNNING -O0 ~~~ ")
        for compilation_result in executor.map(compile_no_optimization, to_compile):
            rel_path = compilation_result.rel_path
            if compilation_result.ok:
                modified_teal.extend(compilation_result.teal_files)
                unopt_success.add(rel_path)
                print(f"✅  {rel_path}")
            else:
                print(f"💥 {rel_path}", file=sys.stderr)
        print(" ~~~ RUNNING -O2 ~~~ ")
        for compilation_result in executor.map(compile_o2, to_compile):
            rel_path = compilation_result.rel_path
            if compilation_result.ok:
                modified_teal.extend(compilation_result.teal_files)
                unopt_success.add(rel_path)
                print(f"✅  {rel_path}")
            else:
                print(f"💥 {rel_path}", file=sys.stderr)
        print(" ~~~ RUNNING -O1 ~~~ ")
        for compilation_result in executor.map(compile_with_level1_optimizations, to_compile):
            rel_path = compilation_result.rel_path
            if compilation_result.ok:
                modified_teal.extend(compilation_result.teal_files)
                opt_success.add(rel_path)
                print(f"✅  {rel_path}")
            else:
                print(f"💥 {rel_path}", file=sys.stderr)
    success_differs = opt_success.symmetric_difference(unopt_success)
    if success_differs:
        print("The following had different success outcomes depending on optimization flag: ")
        for name in sorted(success_differs):
            print(" - " + name)
    if options.update_sizes:
        print("Updating sizes.txt")
        program_sizes = ProgramSizes()
        program_sizes.add(modified_teal)
        if limit_to:
            existing = ProgramSizes.read_file(SIZE_TALLY_PATH)
            program_sizes = existing.update(program_sizes)
        SIZE_TALLY_PATH.write_text(str(program_sizes))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update-sizes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Update sizes.txt",
    )
    parser.add_argument("limit_to", type=Path, nargs="*", metavar="LIMIT_TO")
    options = CompileAllOptions()
    parser.parse_args(namespace=options)
    main(options)
