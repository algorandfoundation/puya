import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_dynamic_array_of_string(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_types/dynamic_string_array.py").client

    xyz_result = app_client.send.call(au.AppClientMethodCallParams(method="xyz"))
    assert xyz_result.abi_return == list("XYZ")

    xyz_raw_result = app_client.send.call(au.AppClientMethodCallParams(method="xyz_raw"))
    assert xyz_raw_result.abi_return == list("XYZ")


def test_array_rebinding(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_types/mutable_params2.py").client

    app_client.send.call(au.AppClientMethodCallParams(method="test_array_rebinding"))


def test_abi_reference_types(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "arc4_types" / "reference_types.py")


def test_dynamic_bytes(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "arc4_types" / "dynamic_bytes.py")
