import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_compile(deployer: Deployer) -> None:
    client = deployer.create((TEST_CASES_DIR / "compile", "HelloFactory")).client

    fee = au.AlgoAmount.from_micro_algo(6000)

    call = client.send.call
    call(au.AppClientMethodCallParams(method="test_compile_contract", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_compile_contract_tmpl", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_compile_contract_prfx", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_compile_contract_large", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_arc4_create", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_arc4_create_tmpl", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_arc4_create_prfx", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_arc4_create_large", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_arc4_create_modified_compiled", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_arc4_update", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_other_constants", static_fee=fee))
    call(au.AppClientMethodCallParams(method="test_abi_call_create_params", static_fee=fee))
