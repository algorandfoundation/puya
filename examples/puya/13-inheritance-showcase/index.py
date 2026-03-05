from pathlib import Path
from random import randbytes

import algokit_utils as au

from shared import (
    assert_equal,
    compile_contract,
    load_app_spec,
    print_header,
    print_info,
    print_step,
    print_success,
)

print_header("Example 13 — Inheritance Showcase")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app specs
print_step(2, "Loading app specs...")
dog_spec = load_app_spec(out_dir, "Dog")
show_dog_spec = load_app_spec(out_dir, "ShowDog")
print_success("App specs loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
creator = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(creator)
print_success("Connected to LocalNet")

# Step 4: Fund deployer
print_step(4, "Funding deployer account...")
print_success(f"Using dispenser: {creator.addr}")


def deploy(app_spec: object, name: str, legs: int) -> au.AppClient:
    """Deploy a contract and call create(name, legs)."""
    factory = au.AppFactory(
        au.AppFactoryParams(
            algorand=algorand,
            app_spec=app_spec,
            default_sender=creator.addr,
            default_signer=creator.signer,
        )
    )
    client, _ = factory.send.create(
        au.AppFactoryCreateMethodCallParams(
            method="create(string,uint64)void",
            args=[name, legs],
            note=randbytes(8),
        )
    )
    return client


def call(client: au.AppClient, method: str, args: list[object] | None = None) -> au.SendAppTransactionResult:
    return client.send.call(
        au.AppClientMethodCallParams(
            method=method, args=args or [], note=randbytes(8)
        )
    )


# Step 5: Deploy Dog (single-level inheritance)
print_step(5, "Deploying Dog (Dog -> Animal)...")
dog = deploy(dog_spec, "Rex", 4)
print_success(f"Contract deployed — App ID: {dog.app_id}")

# Step 6: Test Dog — inherited and overridden methods
print_step(6, "Testing Dog methods...")

resp = call(dog, "get_name()string")
assert_equal(resp.abi_return, "Rex", "Dog.get_name (inherited)")
print_success("get_name() returned 'Rex' (inherited from Animal)")

resp = call(dog, "get_legs()uint64")
assert_equal(resp.abi_return, 4, "Dog.get_legs (inherited)")
print_success("get_legs() returned 4 (inherited from Animal)")

resp = call(dog, "speak()string")
assert_equal(resp.abi_return, "Rex says Woof!", "Dog.speak (overridden)")
print_success("speak() returned 'Rex says Woof!' (overridden in Dog)")

resp = call(dog, "get_trick()string")
assert_equal(resp.abi_return, "sit", "Dog.get_trick (own method)")
print_success("get_trick() returned 'sit' (Dog's own method)")

call(dog, "set_trick(string)void", ["roll over"])
resp = call(dog, "describe()string")
assert_equal(resp.abi_return, "Rex has 4 legs and knows roll over", "Dog.describe (overridden)")
print_success("describe() returned 'Rex has 4 legs and knows roll over' (overridden)")

resp = call(dog, "species_type()string")
assert_equal(resp.abi_return, "Animal", "Dog.species_type (final, inherited)")
print_success("species_type() returned 'Animal' (final method from Animal)")

# Step 7: Deploy ShowDog (multi-level inheritance)
print_step(7, "Deploying ShowDog (ShowDog -> Dog -> Animal)...")
show_dog = deploy(show_dog_spec, "Bella", 4)
print_success(f"Contract deployed — App ID: {show_dog.app_id}")

# Step 8: Test ShowDog — multi-level inherited and overridden methods
print_step(8, "Testing ShowDog methods...")

resp = call(show_dog, "get_name()string")
assert_equal(resp.abi_return, "Bella", "ShowDog.get_name (from Animal)")
print_success("get_name() returned 'Bella' (inherited from Animal)")

resp = call(show_dog, "speak()string")
assert_equal(resp.abi_return, "Bella says Woof! (Show champion)", "ShowDog.speak")
print_success("speak() returned 'Bella says Woof! (Show champion)' (ShowDog override)")

resp = call(show_dog, "get_trick()string")
assert_equal(resp.abi_return, "sit", "ShowDog.get_trick (from Dog)")
print_success("get_trick() returned 'sit' (inherited from Dog)")

resp = call(show_dog, "win_award()uint64")
assert_equal(resp.abi_return, 1, "first award")
print_success("win_award() returned 1")

resp = call(show_dog, "win_award()uint64")
assert_equal(resp.abi_return, 2, "second award")
print_success("win_award() returned 2")

call(show_dog, "set_trick(string)void", ["dance"])
resp = call(show_dog, "describe()string")
assert_equal(resp.abi_return, "Bella has 4 legs, knows dance, awards: 2", "ShowDog.describe")
print_success("describe() returned 'Bella has 4 legs, knows dance, awards: 2' (ShowDog override)")

resp = call(show_dog, "get_awards()uint64")
assert_equal(resp.abi_return, 2, "ShowDog.get_awards")
print_success("get_awards() returned 2 (ShowDog's own method)")

resp = call(show_dog, "species_type()string")
assert_equal(resp.abi_return, "Animal", "ShowDog.species_type (final from Animal)")
print_success("species_type() returned 'Animal' (final from Animal, 3 levels up)")

print_header("All assertions passed!")
