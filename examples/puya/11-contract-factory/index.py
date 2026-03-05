"""Example 11: Contract Factory — Deployment & Test Script

This script compiles, deploys, and tests the ContractFactory contract on LocalNet.

Features:
- Deploys ContractFactory via app factory
- Tests deploy_child — child deployment via compile_contract() + manual inner txn
- Tests call_child_greet — contract-to-contract ABI call via abi_call()
- Tests delete_child — child deletion via abi_call() with DeleteApplication
- Tests deploy_templated — child deployment via compile_contract() with TemplateVar
- Tests deploy_and_greet — all-in-one deploy, greet, and delete

Prerequisites: LocalNet
"""

from pathlib import Path
from random import randbytes

import algokit_utils as au

from shared import (
    assert_equal,
    assert_greater_than,
    compile_contract,
    load_app_spec,
    print_header,
    print_step,
    print_success,
    shorten_address,
)

print_header("Example 11 — Contract Factory")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "ContractFactory")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Create and fund deployer account
print_step(4, "Creating deployer account...")
creator = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(creator)
print_success(f"Deployer funded: {shorten_address(creator.addr)}")

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
client, _ = factory.send.bare.create(
    au.AppFactoryCreateParams(note=randbytes(8))
)
print_success(f"Contract deployed — App ID: {client.app_id}")

# Step 6: Fund app with 2 ALGO
print_step(6, "Funding app with 2 ALGO...")
algorand.account.ensure_funded(
    account_to_fund=client.app_address,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_algo(2),
)
print_success(f"App funded: {shorten_address(client.app_address)}")

ITXN_FEE = au.AlgoAmount.from_micro_algo(1000)

# Step 7: Call deploy_child — deploys child contract via inner txn
print_step(7, "Calling deploy_child...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="deploy_child(string)uint64",
        args=["hello"],
        extra_fee=ITXN_FEE,
        note=randbytes(8),
    )
)
child_app_id = resp.abi_return
assert isinstance(child_app_id, int)
assert_greater_than(child_app_id, 0, "child_app_id > 0")
print_success(f"deploy_child succeeded — child_app_id: {child_app_id}")

# Step 8: Call call_child_greet — c2c call to child contract
print_step(8, "Calling call_child_greet...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="call_child_greet(uint64,string)string",
        args=[child_app_id, "world"],
        extra_fee=ITXN_FEE,
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, "hello world", "call_child_greet return")
print_success(f"call_child_greet returned: {resp.abi_return}")

# Step 9: Call delete_child — deletes child contract via inner txn
print_step(9, "Calling delete_child...")
client.send.call(
    au.AppClientMethodCallParams(
        method="delete_child(uint64)void",
        args=[child_app_id],
        extra_fee=ITXN_FEE,
        note=randbytes(8),
    )
)
print_success("delete_child succeeded")

# Step 10: Call deploy_templated — deploys child via compile_contract() with TemplateVar
print_step(10, "Calling deploy_templated...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="deploy_templated()uint64",
        args=[],
        extra_fee=ITXN_FEE,
        note=randbytes(8),
    )
)
tmpl_app_id = resp.abi_return
assert isinstance(tmpl_app_id, int)
assert_greater_than(tmpl_app_id, 0, "tmpl_app_id > 0")
print_success(f"deploy_templated succeeded — tmpl_app_id: {tmpl_app_id}")

# Step 11: Call call_child_greet on templated child — greeting should be 'howdy'
print_step(11, "Calling call_child_greet on templated child...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="call_child_greet(uint64,string)string",
        args=[tmpl_app_id, "partner"],
        extra_fee=ITXN_FEE,
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, "howdy partner", "templated child greet return")
print_success(f"call_child_greet returned: {resp.abi_return}")

# Step 12: Call delete_child on templated child
print_step(12, "Calling delete_child on templated child...")
client.send.call(
    au.AppClientMethodCallParams(
        method="delete_child(uint64)void",
        args=[tmpl_app_id],
        extra_fee=ITXN_FEE,
        note=randbytes(8),
    )
)
print_success("delete_child succeeded")

# Step 13: Call deploy_and_greet — all-in-one deploy, greet, and delete
print_step(13, "Calling deploy_and_greet...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="deploy_and_greet(string,string)string",
        args=["hey", "algorand"],
        extra_fee=au.AlgoAmount.from_micro_algo(3000),  # 3 inner txns
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, "hey algorand", "deploy_and_greet return")
print_success(f"deploy_and_greet returned: {resp.abi_return}")

print_header("All assertions passed!")
