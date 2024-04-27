import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}


def get_artifact_folders(root_dir: str) -> Iterator[Path]:
    for folder in Path(root_dir).iterdir():
        if folder.is_dir() and (folder / "contract.py").exists():
            yield folder


def compile_contract(folder: Path) -> None:
    contract_path = folder / "contract.py"
    (folder / "data").mkdir(exist_ok=True)
    compile_cmd = [
        "poetry",
        "run",
        "puyapy",
        str(contract_path),
        "--out-dir",
        "data",
    ]
    subprocess.run(
        compile_cmd,  # noqa: S603
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=ENV_WITH_NO_COLOR,
        encoding="utf-8",
    )


def generate_client(folder: Path) -> None:
    avm_dir = folder / "data"
    client_path = folder / "client.py"
    generate_cmd = [
        "algokit",
        "generate",
        "client",
        str(avm_dir),
        "--language",
        "python",
        "--output",
        str(client_path),
    ]
    subprocess.run(
        generate_cmd,  # noqa: S603
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=ENV_WITH_NO_COLOR,
        encoding="utf-8",
    )


def main() -> None:
    artifacts_dir = "tests/artifacts"
    try:
        for folder in get_artifact_folders(artifacts_dir):
            compile_contract(folder)
            generate_client(folder)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
