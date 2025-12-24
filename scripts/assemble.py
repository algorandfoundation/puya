import argparse
import base64
from pathlib import Path

from algokit_utils import AlgorandClient


def main(path: list[Path]) -> None:
    localnet = AlgorandClient.default_localnet()
    for p in path:
        response = localnet.client.algod.teal_compile(body=p.read_bytes())
        compiled = response.result
        compiled_bytes = base64.b64decode(compiled)
        p.with_suffix(".teal.bin").write_bytes(compiled_bytes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="assemble")
    parser.add_argument("files", type=Path, nargs="+", metavar="FILE")
    args = parser.parse_args()
    main(args.files)
