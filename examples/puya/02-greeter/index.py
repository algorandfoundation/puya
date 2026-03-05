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

print_header("Example 02 — Greeter")
example_dir = Path(__file__).parent

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "Greeter")
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
client, result = factory.send.create(
    au.AppFactoryCreateMethodCallParams(method="create()void", note=randbytes(8))
)
print_success(f"Contract deployed — App ID: {client.app_id}")


def call(method: str, args: list[object] | None = None) -> object:
    resp = client.send.call(
        au.AppClientMethodCallParams(
            method=method, args=args or [], note=randbytes(8)
        )
    )
    return resp.abi_return


# Step 6: Call hello('World') → expect 'Hello, World!'
print_step(6, "Calling hello('World')...")
assert_equal(call("hello(string)string", ["World"]), "Hello, World!", "hello('World')")
print_success("hello('World') returned 'Hello, World!'")

# Step 7: Change greeting to 'Howdy'
print_step(7, "Calling set_greeting('Howdy')...")
call("set_greeting(string)void", ["Howdy"])
print_success("Greeting updated to 'Howdy'")

# Step 8: Call hello('Alice') → expect 'Howdy, Alice!'
print_step(8, "Calling hello('Alice') after greeting change...")
assert_equal(call("hello(string)string", ["Alice"]), "Howdy, Alice!", "hello('Alice')")
print_success("hello('Alice') returned 'Howdy, Alice!'")

print_header("All assertions passed!")
