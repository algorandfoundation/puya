from pathlib import Path

import pytest

from puya.errors import ErrorExitCode, PuyaExitError
from puyapy.options import PuyaPyOptions
from tests.utils.compile import compile_src_from_options


def _assert_contract_fails_validation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    source: str,
    expected_message: str,
) -> None:
    contract = tmp_path / "contract.py"
    contract.write_text(source.strip(), encoding="utf8")

    with pytest.raises(PuyaExitError) as ex_info:
        compile_src_from_options(PuyaPyOptions(paths=(contract,)))

    assert ex_info.value.exit_code == ErrorExitCode.code
    captured = capsys.readouterr()
    assert expected_message in captured.out


def test_duplicate_global_state_key_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_contract_fails_validation(
        tmp_path,
        capsys,
        """
from algopy import ARC4Contract, GlobalState, UInt64


class Contract(ARC4Contract):
    def __init__(self) -> None:
        self.first = GlobalState(UInt64, key=b\"dup\")
        self.second = GlobalState(UInt64, key=b\"dup\")
""",
        "duplicate global state key b'dup'",
    )


def test_duplicate_local_state_key_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_contract_fails_validation(
        tmp_path,
        capsys,
        """
from algopy import ARC4Contract, LocalState, UInt64


class Contract(ARC4Contract):
    def __init__(self) -> None:
        self.first = LocalState(UInt64, key=b\"dup\")
        self.second = LocalState(UInt64, key=b\"dup\")
""",
        "duplicate local state key b'dup'",
    )


def test_duplicate_box_key_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _assert_contract_fails_validation(
        tmp_path,
        capsys,
        """
from algopy import ARC4Contract, Box, UInt64


class Contract(ARC4Contract):
    def __init__(self) -> None:
        self.first = Box(UInt64, key=b\"dup\")
        self.second = Box(UInt64, key=b\"dup\")
""",
        "duplicate box key or prefix b'dup'",
    )


def test_duplicate_box_prefix_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_contract_fails_validation(
        tmp_path,
        capsys,
        """
from algopy import ARC4Contract, BoxMap, UInt64


class Contract(ARC4Contract):
    def __init__(self) -> None:
        self.first = BoxMap(UInt64, UInt64, key_prefix=b\"dup\")
        self.second = BoxMap(UInt64, UInt64, key_prefix=b\"dup\")
""",
        "duplicate box key or prefix b'dup'",
    )


def test_duplicate_global_state_key_is_rejected_in_inheritance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_contract_fails_validation(
        tmp_path,
        capsys,
        """
from algopy import ARC4Contract, GlobalState, UInt64


class BaseContract(ARC4Contract):
    def __init__(self) -> None:
        self.base_counter = GlobalState(UInt64, key=b\"dup\")


class Contract(BaseContract):
    def __init__(self) -> None:
        super().__init__()
        self.child_counter = GlobalState(UInt64, key=b\"dup\")
""",
        "duplicate global state key b'dup'",
    )
