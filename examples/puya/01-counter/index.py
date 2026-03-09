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

print_header("Example 01 — Counter")
example_dir = Path(__file__).parent

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "Counter")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Create and fund deployer account
print_step(4, "Creating deployer account...")
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
        au.AppClientMethodCallParams(method=method, args=args or [], note=randbytes(8))
    )
    return resp.abi_return


# Step 6: Call increment() three times
print_step(6, "Calling increment()...")
assert_equal(call("increment()uint64"), 1, "increment #1")
print_success("increment() returned 1")
assert_equal(call("increment()uint64"), 2, "increment #2")
print_success("increment() returned 2")
assert_equal(call("increment()uint64"), 3, "increment #3")
print_success("increment() returned 3")

# Step 7: Call multiply(3)
print_step(7, "Calling multiply(3)...")
assert_equal(call("multiply(uint64)uint64", [3]), 9, "multiply(3)")
print_success("multiply(3) returned 9")

# Step 8: Call decrement()
print_step(8, "Calling decrement()...")
assert_equal(call("decrement()uint64"), 8, "decrement")
print_success("decrement() returned 8")

# Step 9: Call divide(4)
print_step(9, "Calling divide(4)...")
assert_equal(call("divide(uint64)uint64", [4]), 2, "divide(4)")
print_success("divide(4) returned 2")

print_header("All assertions passed!")
