#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import algokit_utils
import attrs
from wyvern.codegen.teal_annotaters import AlignedWriter

SCRIPT_DIR = Path(__file__).parent
GIT_ROOT = SCRIPT_DIR.parent
EXAMPLES_DIR = GIT_ROOT / "examples"
SIZE_TALLY_PATH = EXAMPLES_DIR / "sizes.txt"
ALGOD_CLIENT = algokit_utils.get_algod_client(algokit_utils.get_default_localnet_config("algod"))
ENV_WITH_NO_COLOR = dict(os.environ) | {"NO_COLOR": "1"}


def get_unique_name(path: Path) -> str:
    rel_path = path.relative_to(EXAMPLES_DIR)
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
    sizes: dict[str, int] = attrs.field(factory=dict)
    unoptimized_sizes: dict[str, int] = attrs.field(factory=dict)

    def add(self, teal_programs: list[Path]) -> None:
        for teal in teal_programs:
            name = get_unique_name(teal)
            match teal.suffixes:
                case [".approval", ".teal"]:
                    self.sizes[name] = get_program_size(teal)
                case [".approval_unoptimized", ".teal"]:
                    self.unoptimized_sizes[name] = get_program_size(teal)

    @classmethod
    def read_file(cls, path: Path) -> "ProgramSizes":
        lines = path.read_text("utf-8").splitlines()
        program_sizes = ProgramSizes()
        for line in lines[1:]:
            name, unoptimized, optimized = line.rsplit(maxsplit=3)
            program_sizes.unoptimized_sizes[name] = int(unoptimized)
            program_sizes.sizes[name] = int(optimized)
        return program_sizes

    def update(self, other: "ProgramSizes") -> "ProgramSizes":
        return ProgramSizes(
            sizes={**self.sizes, **other.sizes},
            unoptimized_sizes={**self.unoptimized_sizes, **other.unoptimized_sizes},
        )

    def __str__(self) -> str:
        writer = AlignedWriter()
        writer.add_header("Name")
        writer.add_header("Unoptimized size")
        writer.add_header("Optimized size")
        for name in sorted(self.sizes):
            optimized = self.sizes[name]
            unoptimized = self.unoptimized_sizes[name]
            writer.append(name)
            writer.append(str(unoptimized))
            writer.append(str(optimized))
            writer.new_line()
        return "\n".join(writer.write())


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
                "debug: Skipping algopy stub ",
                "debug: Skipping typeshed stub ",
                "warning: Skipping stub: ",
                "debug: Skipping stdlib stub ",
            )
        )
    ]


def checked_compile(p: Path, flags: list[str], *, write_logs: bool) -> CompilationResult:
    rel_path = str(p.relative_to(EXAMPLES_DIR))

    cmd = [
        "poetry",
        "run",
        "algopy",
        *flags,
        "--out-dir=out",
        "--debug-level=1",
        "--log-level=debug",
        rel_path,
    ]
    result = subprocess.run(
        cmd,
        cwd=EXAMPLES_DIR,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=ENV_WITH_NO_COLOR,
    )
    final_ir_written = re.findall(r"debug: Output IR to (.+\.final\.ir)", result.stdout)
    final_ir_written += re.findall(r"debug: Output IR to (.+\.final_par\.ir)", result.stdout)
    teal_files_written = re.findall(r"info: Writing (.+\.teal)", result.stdout)
    if write_logs:
        if p.is_dir():
            log_path = p / "algopy.log"
        else:
            log_path = p.with_suffix(".algopy.log")

        log_txt = "\n".join(
            [
                ">> " + " ".join(cmd),
                *_stabilise_logs(result.stdout),
                f">> exit code = {result.returncode}",
            ]
        )
        log_path.write_text(log_txt, encoding="utf8")
    return CompilationResult(
        rel_path=rel_path,
        ok=result.returncode == 0,
        teal_files=[EXAMPLES_DIR / p for p in teal_files_written],
        final_ir_files=[EXAMPLES_DIR / p for p in final_ir_written],
    )


def compile_no_optimization(p: Path) -> CompilationResult:
    result = checked_compile(
        p,
        flags=[
            "-O0",
            "--output-awst",
            "--output-final-ir",
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


def compile_with_level1_optimizations(p: Path) -> CompilationResult:
    return checked_compile(
        p,
        flags=[
            "-O1",
            "--output-ssa-ir",
            "--output-optimization-ir",
            "--output-final-ir",
            "--output-cssa-ir",
            "--output-post-ssa-ir",
            "--output-parallel-copies-ir",
        ],
        write_logs=True,
    )


def main(*limit_to: str) -> None:
    to_compile = []
    if limit_to:
        to_compile = [Path(x).resolve() for x in limit_to]
    else:
        for item in EXAMPLES_DIR.iterdir():
            if item.is_dir():
                if any(item.rglob("*.py")):
                    to_compile.append(item)
            elif item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
                to_compile.append(item)
    if not limit_to:
        print("Cleaning up prior runs")
        for ext in (".teal", ".awst", ".ir"):
            for f in EXAMPLES_DIR.rglob(f"**/out/*{ext}"):
                if f.is_file():
                    f.unlink()

    program_sizes = ProgramSizes()
    opt_success = set()
    unopt_success = set()
    with ProcessPoolExecutor() as executor:
        print(" ~~~ RUNNING WITHOUT OPTIMIZATIONS ~~~ ")
        for compilation_result in executor.map(compile_no_optimization, to_compile):
            rel_path = compilation_result.rel_path
            if compilation_result.ok:
                program_sizes.add(compilation_result.teal_files)
                unopt_success.add(rel_path)
                print(f"✅  {rel_path}")
            else:
                print(f"💥 {rel_path}", file=sys.stderr)
        print(" ~~~ RUNNING WITH OPTIMIZATIONS ~~~ ")
        for compilation_result in executor.map(compile_with_level1_optimizations, to_compile):
            rel_path = compilation_result.rel_path
            if compilation_result.ok:
                program_sizes.add(compilation_result.teal_files)
                opt_success.add(rel_path)
                print(f"✅  {rel_path}")
            else:
                print(f"💥 {rel_path}", file=sys.stderr)
    success_differs = opt_success.symmetric_difference(unopt_success)
    if success_differs:
        print("The following had different success outcomes depending on optimization flag: ")
        for name in sorted(success_differs):
            print(" - " + name)
    if limit_to:
        existing = ProgramSizes.read_file(SIZE_TALLY_PATH)
        program_sizes = existing.update(program_sizes)
    SIZE_TALLY_PATH.write_text(str(program_sizes))


if __name__ == "__main__":
    main(*sys.argv[1:])
