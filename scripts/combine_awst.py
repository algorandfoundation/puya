#!/usr/bin/env python3

import gzip
import json
import sys
from pathlib import Path


def main() -> None:
    try:
        _, src, dest = map(Path, sys.argv)
    except ValueError:
        print("usage: combine_awst.py path/to/awst/folder path/to/output.awst.json.gz")
    else:
        assert src.is_dir(), "expected src dir"
        assert dest.is_file() or not dest.exists(), "expected dest file"
        _combine_awst(src, dest)


def _combine_awst(src: Path, dest: Path) -> None:
    module = []
    for awst_path in src.rglob("*.awst.json"):
        awst = json.loads(awst_path.read_text("utf-8"))
        module.extend(awst)
    compressed = gzip.compress(json.dumps(module).encode("utf-8"))
    dest.write_bytes(compressed)


if __name__ == "__main__":
    main()
