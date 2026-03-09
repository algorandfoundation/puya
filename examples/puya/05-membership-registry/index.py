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
    shorten_address,
)

print_header("Example 05 — Membership Registry")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "MembershipRegistry")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Create and fund deployer and member accounts
print_step(4, "Creating deployer and member accounts...")
creator = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(creator)
alice = algorand.account.random()
bob = algorand.account.random()
algorand.account.ensure_funded(
    account_to_fund=alice.addr,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_algo(1),
)
algorand.account.ensure_funded(
    account_to_fund=bob.addr,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_algo(1),
)
algorand.account.set_signer_from_account(alice)
algorand.account.set_signer_from_account(bob)
print_success(f"Alice funded: {shorten_address(alice.addr)}")
print_success(f"Bob funded: {shorten_address(bob.addr)}")

# Step 5: Deploy the contract
print_step(5, "Deploying contract...")
factory = au.AppFactory(
    au.AppFactoryParams(
        algorand=algorand,
        app_spec=app_spec,
        default_sender=creator.addr,
        default_signer=creator.signer,
    )
)
client, _ = factory.send.bare.create(au.AppFactoryCreateParams(note=randbytes(8)))
print_success(f"Contract deployed — App ID: {client.app_id}")

# Step 6: Opt in Alice and Bob via register
print_step(6, "Opting in Alice and Bob...")
client.send.bare.call(
    au.AppClientBareCallParams(sender=alice.addr, note=randbytes(8)),
    on_complete=au.OnApplicationComplete.OptIn,
)
print_success("Alice opted in")
client.send.bare.call(
    au.AppClientBareCallParams(sender=bob.addr, note=randbytes(8)),
    on_complete=au.OnApplicationComplete.OptIn,
)
print_success("Bob opted in")
count = client.send.call(
    au.AppClientMethodCallParams(method="get_member_count()uint64", note=randbytes(8))
).abi_return
assert_equal(count, 2, "member count after two opt-ins")

# Step 7: Set nicknames
print_step(7, "Setting nicknames...")
client.send.call(
    au.AppClientMethodCallParams(
        method="set_nickname(string)void",
        args=["Alice"],
        sender=alice.addr,
        note=randbytes(8),
    )
)
client.send.call(
    au.AppClientMethodCallParams(
        method="set_nickname(string)void",
        args=["Bob"],
        sender=bob.addr,
        note=randbytes(8),
    )
)
print_success("Nicknames set")

# Step 8: Read local state directly
print_step(8, "Reading local state directly...")
alice_state = client.get_local_state(alice.addr)
assert_equal(alice_state["nickname"].value, "Alice", "Alice nickname via get_local_state")
bob_state = client.get_local_state(bob.addr)
assert_equal(bob_state["nickname"].value, "Bob", "Bob nickname via get_local_state")

# Step 9: Read nicknames via ABI method
print_step(9, "Reading nicknames via ABI method...")
alice_nick = client.send.call(
    au.AppClientMethodCallParams(
        method="get_nickname(address)string",
        args=[alice.addr],
        note=randbytes(8),
    )
).abi_return
assert_equal(alice_nick, "Alice", "Alice nickname via ABI")
bob_nick = client.send.call(
    au.AppClientMethodCallParams(
        method="get_nickname(address)string",
        args=[bob.addr],
        note=randbytes(8),
    )
).abi_return
assert_equal(bob_nick, "Bob", "Bob nickname via ABI")

# Step 10: Close out Bob
print_step(10, "Closing out Bob...")
client.send.bare.call(
    au.AppClientBareCallParams(sender=bob.addr, note=randbytes(8)),
    on_complete=au.OnApplicationComplete.CloseOut,
)
count = client.send.call(
    au.AppClientMethodCallParams(method="get_member_count()uint64", note=randbytes(8))
).abi_return
assert_equal(count, 1, "member count after Bob close-out")
print_success("Bob closed out")

# Step 11: Verify Alice still active
print_step(11, "Verifying Alice still active after Bob's close-out...")
alice_nick = client.send.call(
    au.AppClientMethodCallParams(
        method="get_nickname(address)string",
        args=[alice.addr],
        note=randbytes(8),
    )
).abi_return
assert_equal(alice_nick, "Alice", "Alice nickname still intact")
print_success("Alice still active")

print_header("All assertions passed!")
