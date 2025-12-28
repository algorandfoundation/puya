import algokit_utils as au
import attrs
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_CONTRACT_PATH = TEST_CASES_DIR / "undefined_phi_args"


@pytest.mark.parametrize(
    ("test_case", "expected_logic_error"),
    [
        (b"uint", "+ arg 0 wanted uint64 but got []byte"),
        (b"bytes", "b+ arg 0 wanted bigint but got uint64"),
        (b"mixed", "itob arg 0 wanted uint64 but got []byte"),
    ],
)
def test_undefined_phi_args(
    deployer_o: Deployer, test_case: bytes, expected_logic_error: str
) -> None:
    deployer_debug1 = attrs.evolve(deployer_o, debug_level=1)
    deployer_debug1.create_bare(_CONTRACT_PATH, args=[test_case])

    deployer_debug2 = attrs.evolve(deployer_o, debug_level=2)
    with pytest.raises(au.LogicError) as ex_info:
        deployer_debug2.create_bare(_CONTRACT_PATH, args=[test_case, b"\x01"])
    ex = ex_info.value
    assert ex.message == expected_logic_error
    assert ex.line_no is not None
    assert "💥" in "".join(ex.lines[ex.line_no - 5 : ex.line_no])
