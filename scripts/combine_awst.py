#!/usr/bin/env python3

import gzip
import json

import cyclopts

app = cyclopts.App(help_on_error=True)


@app.default
def combine_awst(src: cyclopts.types.ExistingDirectory, dest: cyclopts.types.File) -> None:
    """
    Combines multiple .awst.json files into a single gz archive

    Parameters:
        src: Directory containing  .awst.json files
        dest: Output gzipped file
    """
    module = []
    for awst_path in src.rglob("*.awst.json"):
        awst = json.loads(awst_path.read_text("utf-8"))
        module.extend(awst)
    compressed = gzip.compress(json.dumps(module).encode("utf-8"))
    dest.write_bytes(compressed)


if __name__ == "__main__":
    app()
