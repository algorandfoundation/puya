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
    shorten_address,
)

print_header("Example 10 — Multi-Txn Distributor")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "MultiTxnDistributor")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Create and fund deployer + receiver accounts
print_step(4, "Creating deployer and receiver accounts...")
creator = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(creator)

receivers = []
for i in range(4):
    acc = algorand.account.random()
    algorand.account.ensure_funded(
        account_to_fund=acc.addr,
        dispenser_account=creator,
        min_spending_balance=au.AlgoAmount.from_micro_algo(100_000),
    )
    receivers.append(acc)
    print_info(f"Receiver {i + 1}: {shorten_address(acc.addr)}")
print_success("Accounts created and funded")

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

# Step 6: Fund app account
print_step(6, "Funding app with 5 ALGO...")
algorand.account.ensure_funded(
    account_to_fund=client.app_address,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_algo(5),
)
print_success(f"App funded: {shorten_address(client.app_address)}")


def get_balance(addr: str) -> int:
    return algorand.account.get_information(addr).amount.micro_algo


# Step 7: Test distribute_fixed (submit_txns with 3 payments)
print_step(7, "Calling distribute_fixed...")
DISTRIBUTE_AMOUNT = 900_000  # 0.9 ALGO total, 0.3 ALGO each

balances_before = [get_balance(r.addr) for r in receivers[:3]]

pay = algorand.create_transaction.payment(
    au.PaymentParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(DISTRIBUTE_AMOUNT),
        note=randbytes(8),
    )
)

resp = client.send.call(
    au.AppClientMethodCallParams(
        method="distribute_fixed(pay,address,address,address)(uint64,uint64,uint64)",
        args=[pay, receivers[0].addr, receivers[1].addr, receivers[2].addr],
        extra_fee=au.AlgoAmount.from_micro_algo(3000),  # 3 inner txns
        note=randbytes(8),
    )
)

amounts = resp.abi_return
assert isinstance(amounts, tuple)
expected_share = DISTRIBUTE_AMOUNT // 3
print_info(f"Returned amounts: {amounts}")
assert_equal(amounts, (expected_share, expected_share, expected_share), "distribute_fixed return")

for i in range(3):
    balance_after = get_balance(receivers[i].addr)
    assert_equal(
        balance_after - balances_before[i], expected_share, f"receiver {i + 1} balance increase"
    )

print_success("distribute_fixed succeeded")

# Step 8: Test distribute_dynamic (stage/submit_staged with 4 payments)
print_step(8, "Calling distribute_dynamic...")
DYNAMIC_AMOUNT = 800_000  # 0.8 ALGO total, 0.2 ALGO each

balances_before = [get_balance(r.addr) for r in receivers]

pay = algorand.create_transaction.payment(
    au.PaymentParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(DYNAMIC_AMOUNT),
        note=randbytes(8),
    )
)

receiver_addrs = [r.addr for r in receivers]

resp = client.send.call(
    au.AppClientMethodCallParams(
        method="distribute_dynamic(pay,address[])uint64",
        args=[pay, receiver_addrs],
        extra_fee=au.AlgoAmount.from_micro_algo(4000),  # 4 inner txns
        note=randbytes(8),
    )
)

share = resp.abi_return
expected_share = DYNAMIC_AMOUNT // 4
assert_equal(share, expected_share, "distribute_dynamic return (share)")

for i in range(4):
    balance_after = get_balance(receivers[i].addr)
    assert_equal(
        balance_after - balances_before[i], expected_share, f"receiver {i + 1} balance increase"
    )

print_success("distribute_dynamic succeeded")

print_header("All assertions passed!")
