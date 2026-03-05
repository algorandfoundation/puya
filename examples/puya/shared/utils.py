import os
import subprocess
import sys
from pathlib import Path

import algokit_utils as au

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def print_header(title: str) -> None:
    width = 50
    print("\n" + "═" * width)
    print(f"  {title}")
    print("═" * width)


def print_step(step: int, description: str) -> None:
    print(f"\n[Step {step}] {description}")


def print_info(message: str) -> None:
    print(f"  ℹ {message}")


def print_success(message: str) -> None:
    print(f"  ✓ {message}")


def print_error(message: str) -> None:
    print(f"  ✗ {message}")


def shorten_address(address: str) -> str:
    if len(address) <= 12:
        return address
    return f"{address[:6]}...{address[-4:]}"


def assert_equal(actual: object, expected: object, label: str = "") -> None:
    if actual != expected:
        msg = f"Assertion failed: {actual!r} != {expected!r}"
        if label:
            msg = f"{label}: {msg}"
        raise AssertionError(msg)


def assert_defined(value: object, label: str = "") -> None:
    if value is None:
        msg = f"Assertion failed: expected defined value, got {value!r}"
        if label:
            msg = f"{label}: {msg}"
        raise AssertionError(msg)


def assert_greater_than(actual: int, threshold: int, label: str = "") -> None:
    if not (actual > threshold):
        msg = f"Assertion failed: expected {actual!r} > {threshold!r}"
        if label:
            msg = f"{label}: {msg}"
        raise AssertionError(msg)


def load_app_spec(out_dir: Path, contract_name: str) -> au.Arc56Contract:
    spec_path = out_dir / f"{contract_name}.arc56.json"
    return au.Arc56Contract.from_json(spec_path.read_text())


def compile_contract(
    example_dir: Path,
    *,
    output_teal: bool = False,
    output_bytecode: bool = False,
) -> Path:
    """Compile an example contract using puyapy from the repo root.

    Returns the output directory path.
    """
    example_dir = example_dir.resolve()
    out_dir = example_dir / "out"
    contract_file = example_dir / "contract.py"
    repo_python = str(REPO_ROOT / ".venv" / "bin" / "python")
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(REPO_ROOT / ".venv")
    cmd = [
        repo_python,
        "-m",
        "puyapy",
        str(contract_file),
        f"--out-dir={out_dir}",
        "--output-arc56",
        "--no-output-arc32",
        "--no-output-source-map",
    ]
    if output_teal:
        cmd.append("--output-teal")
    else:
        cmd.append("--no-output-teal")
    if output_bytecode:
        cmd.append("--output-bytecode")
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        print_error("Compilation failed:")
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    print_success(f"Compiled {example_dir.name}")
    return out_dir
