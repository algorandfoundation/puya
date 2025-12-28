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


def test_abi_string(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "arc4_types" / "string.py")


def test_abi_numeric(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "arc4_types" / "numeric.py")


def test_abi_bool(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "arc4_types" / "bool.py")


def test_abi_struct(deployer_o: Deployer) -> None:
    response = deployer_o.create_bare(TEST_CASES_DIR / "arc4_types" / "structs.py")
    x, y, z = response.logs

    assert x == 0x1079F7E42E.to_bytes(8, "big")
    assert y == 0x4607097084.to_bytes(8, "big")
    assert z == 0b10100000.to_bytes()


def test_abi_array(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "arc4_types" / "array.py", num_op_ups=1)


def test_abi_mutations(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "arc4_types" / "mutation.py", num_op_ups=15)


def test_abi_mutable_params(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "arc4_types" / "mutable_params.py", num_op_ups=2)


def test_abi_bool_eval(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "arc4_types" / "bool_eval.py")


def test_abi_tuple(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(
        TEST_CASES_DIR / "arc4_types" / "tuples.py",
        num_op_ups=1 if deployer_o.optimization_level == 0 else 0,
    )
