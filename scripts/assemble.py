import argparse
import base64
from pathlib import Path

from algosdk.v2client.algod import AlgodClient


def main(path: list[Path]) -> None:
    algod_client = AlgodClient(algod_token="a" * 64, algod_address="http://localhost:4001")
    for p in path:
        response = algod_client.compile(p.read_text("utf8"))
        compiled: str = response["result"]
        compiled_bytes = base64.b64decode(compiled)
        p.with_suffix(".teal.bin").write_bytes(compiled_bytes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="assemble")
    parser.add_argument("files", type=Path, nargs="+", metavar="FILE")
    args = parser.parse_args()
    main(args.files)
