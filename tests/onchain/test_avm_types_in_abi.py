import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_avm_types_in_abi(
    deployer: Deployer,
    account: au.AddressWithSigners,
) -> None:
    example = TEST_CASES_DIR / "avm_types_in_abi" / "contract.py"

    max_biguint = 2**512 - 1

    response = deployer.create(
        example,
        method="create",
        args=[
            True,  # bool_param
            45,  # uint64_param
            b"Hello world!",  # bytes_param
            max_biguint,  # biguint_param
            "Hi again",  # string_param
            (True, 45, b"Hello world!", max_biguint, "Hi again"),  # tuple_param
        ],
    )

    assert response.abi_return == (True, 45, b"Hello world!", max_biguint, "Hi again")

    app_client = response.client
    result2 = app_client.send.call(
        au.AppClientMethodCallParams(
            method="tuple_of_arc4",
            args=[(255, account.addr)],
        )
    )

    assert result2.abi_return == (255, account.addr)
