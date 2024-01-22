import typing
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

VCS_ROOT = Path(__file__).parent.parent

OUTPUT_BASE_DIRS = ["examples", "test_cases"]

CODE_INDENT = "    "

INTERESTING_OPS = frozenset(
    [
        # pure stack manipulation
        "intc",
        *[f"intc_{i}" for i in range(4)],
        "bytec",
        *[f"bytec_{i}" for i in range(4)],
        "pushbytes",
        "pushbytess",
        "pushint",
        "pushints",
        "frame_dig",
        "frame_bury",
        "bury",
        "cover",
        "dig",
        "dup",
        "dup2",
        "dupn",
        "pop",
        "popn",
        "swap",
        "uncover",
        # constants
        "addr",
        "byte",
        "int",
        "method",
        "txn",
        "txna",
        "gtxn",
        "gtxna",
        "itxn",
        "itxna",
        "global",
        "pushint",
        "pushbytes",
        "gload",
        "gaid",
        # other loads
        "load",
    ]
)


def main() -> None:
    teal_blocks = read_all_blocks()
    single_op_blocks = (block[0] for block in teal_blocks if len(block) == 1)
    print("Single op block counts:")
    for count, op in sorted(
        ((count, op) for op, count in Counter(single_op_blocks).items()), reverse=True
    ):
        print(f"  {count}x {op}")

    window_size = 2
    while True:
        num_printed = 0
        print(f"\nInteresting op sequence of length {window_size} counts:")
        seqs = [
            tuple(seq)
            for block in teal_blocks
            for seq in sliding_window(block, window_size)
            if INTERESTING_OPS.issuperset(seq)
        ]
        for count, ops in sorted(
            ((count, ops) for ops, count in Counter(seqs).items()), reverse=True
        )[:20]:
            if count == 1:
                break
            print(f"  {count}x {'; '.join(ops)}")
            num_printed += 1
        if num_printed == 0:
            break
        window_size += 1


def read_all_blocks(*, include_clear_state: bool = True) -> list[list[str]]:
    teal_files = list[Path]()
    for output_base_dir in OUTPUT_BASE_DIRS:
        output_dir = VCS_ROOT / output_base_dir
        assert output_dir.is_dir()
        teal_files.extend(output_dir.rglob("*/out/*.approval.teal"))
        if include_clear_state:
            teal_files.extend(output_dir.rglob("*/out/*.clear.teal"))

    teal_blocks = list[list[str]]()
    for teal_file in teal_files:
        current_block = list[str]()
        teal = teal_file.read_text("utf8")
        file_lines = teal.splitlines()
        assert file_lines[0].startswith("#pragma")
        for line in file_lines[1:]:
            if not line.startswith(CODE_INDENT):
                # new block / function
                if current_block:
                    teal_blocks.append(current_block)
                current_block = []
            else:
                op, *_ = line.split()
                if op:
                    current_block.append(op)
        if current_block:
            teal_blocks.append(current_block)
    return teal_blocks


T = typing.TypeVar("T")


def sliding_window(seq: list[T], window_size: int) -> Iterator[list[T]]:
    for i in range(len(seq) - window_size + 1):
        yield seq[i : i + window_size]


if __name__ == "__main__":
    main()
