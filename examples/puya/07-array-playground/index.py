from pathlib import Path
from random import randbytes

import algokit_utils as au
from shared import (
    assert_equal,
    compile_contract,
    load_app_spec,
    print_header,
    print_step,
    print_success,
)

print_header("Example 07 — Array Playground")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "ArrayPlayground")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Fund deployer account
print_step(4, "Funding deployer account...")
account = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(account)
print_success(f"Deployer funded: {account.addr}")

# Step 5: Deploy the contract
print_step(5, "Deploying contract...")
factory = au.AppFactory(
    au.AppFactoryParams(
        algorand=algorand,
        app_spec=app_spec,
        default_sender=account.addr,
        default_signer=account.signer,
    )
)
client, result = factory.send.bare.create(au.AppFactoryCreateParams(note=randbytes(8)))
print_success(f"Contract deployed — App ID: {client.app_id}")


def call(method: str, args: list[object] | None = None) -> object:
    resp = client.send.call(
        au.AppClientMethodCallParams(
            method=method,
            args=args or [],
            note=randbytes(8),
        )
    )
    return resp.abi_return


# Step 6: Array (dynamic, mutable, stack-based)
print_step(6, "Calling test_array()...")
result = call("test_array()(uint64,uint64,uint64)")
assert_equal(result, (5, 40, 159), "test_array()")
print_success("test_array() returned (5, 40, 159)")

# Step 7: ReferenceArray (dynamic, mutable, scratch-based)
print_step(7, "Calling test_reference_array()...")
result = call("test_reference_array()(uint64,uint64,uint64)")
assert_equal(result, (5, 15, 4), "test_reference_array()")
print_success("test_reference_array() returned (5, 15, 4)")

# Step 8: ImmutableArray (dynamic, immutable, functional)
print_step(8, "Calling test_immutable_array()...")
result = call("test_immutable_array()(uint64,uint64,uint64)")
assert_equal(result, (4, 99, 3), "test_immutable_array()")
print_success("test_immutable_array() returned (4, 99, 3)")

# Step 9: FixedArray (fixed size, mutable)
print_step(9, "Calling test_fixed_array()...")
result = call("test_fixed_array()(uint64,uint64,uint64)")
assert_equal(result, (4, 18, 100), "test_fixed_array()")
print_success("test_fixed_array() returned (4, 18, 100)")

# Step 10: Freeze (mutable -> immutable conversion)
print_step(10, "Calling test_freeze()...")
result = call("test_freeze()(uint64,uint64)")
assert_equal(result, (5, 15), "test_freeze()")
print_success("test_freeze() returned (5, 15)")

# Step 11: urange sum
print_step(11, "Calling test_urange_sum(10) and test_urange_sum(20)...")
result = call("test_urange_sum(uint64)uint64", [10])
assert_equal(result, 55, "test_urange_sum(10)")
print_success("test_urange_sum(10) returned 55")

result = call("test_urange_sum(uint64)uint64", [20])
assert_equal(result, 210, "test_urange_sum(20)")
print_success("test_urange_sum(20) returned 210")

print_header("All assertions passed!")
