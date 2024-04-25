import os
import subprocess
from pathlib import Path
from typing import Iterator


def get_artifact_folders(root_dir: str) -> Iterator[Path]:
    for folder in Path(root_dir).iterdir():
        if folder.is_dir() and (folder / "contract.py").exists():
            yield folder


def compile_contract(folder: Path) -> None:
    contract_path = folder / "contract.py"
    (folder / "data").mkdir(exist_ok=True)
    subprocess.run(
        ["algokit", "compile", "python", str(contract_path), "--out-dir", "data"], check=True
    )


def generate_client(folder: Path) -> None:
    avm_dir = folder / "data"
    client_path = folder / "client.py"
    subprocess.run(
        [
            "algokit",
            "generate",
            "client",
            str(avm_dir),
            "--language",
            "python",
            "--output",
            str(client_path),
        ],
        check=True,
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
