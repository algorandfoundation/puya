import csv
import subprocess
from pathlib import Path

from scripts.compile_all_examples import ProgramSizes

_SCRIPTS_DIR = Path(__file__).parent
_ROOT_DIR = _SCRIPTS_DIR.parent


def main() -> None:
    sizes_path = _ROOT_DIR / "examples" / "sizes.txt"
    curr_text = sizes_path.read_text("utf8")
    prev_text = subprocess.run(
        ["git", "show", "HEAD:examples/sizes.txt"],
        capture_output=True,
        text=True,
        check=True,
        cwd=_ROOT_DIR,
    ).stdout
    if prev_text == curr_text:
        return
    curr_sizes = ProgramSizes.load(curr_text).sizes
    prev_sizes = ProgramSizes.load(prev_text).sizes
    delta = ProgramSizes()
    assert curr_sizes.keys() == prev_sizes.keys(), "can't analyse with different programs"
    for program_name in curr_sizes:
        prev_prog_size = prev_sizes[program_name]
        curr_prog_size = curr_sizes[program_name]
        if prev_prog_size != curr_prog_size:
            for level in range(3):
                delta.sizes[program_name][level] = curr_prog_size[level] - prev_prog_size[level]
    _sizes_to_csv(delta)


def _sizes_to_csv(ps: ProgramSizes) -> None:
    tmp_dir = _ROOT_DIR / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    with (tmp_dir / "sizes_diff.csv").open("w", encoding="utf8") as output:
        writer = csv.writer(output)
        writer.writerow(["Name", "O0", "O1", "O2", "O0#Ops", "O1#Ops", "O2#Ops"])
        # copy sizes and sort by name
        for name, prog_sizes in sorted(ps.sizes.items()):
            o0, o1, o2 = (prog_sizes[i] for i in range(3))
            writer.writerow(
                map(str, (name, o0.bytecode, o1.bytecode, o2.bytecode, o0.ops, o1.ops, o2.ops))
            )


if __name__ == "__main__":
    main()
