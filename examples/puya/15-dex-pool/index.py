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

print_header("Example 15 — DEX Pool")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "DexPool")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Fund deployer account
print_step(4, "Funding deployer account...")
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
client, _ = factory.send.bare.create(au.AppFactoryCreateParams(note=randbytes(8)))
print_success(f"Contract deployed — App ID: {client.app_id}")


ITXN_FEE = au.AlgoAmount.from_micro_algo(1000)


# Step 6: Create test assets
print_step(6, "Creating test ASAs...")
result_a = algorand.send.asset_create(
    au.AssetCreateParams(
        sender=creator.addr,
        total=10_000_000,
        decimals=0,
        asset_name="Token A",
        unit_name="TKA",
        note=randbytes(8),
    )
)
asset_a = result_a.asset_id

result_b = algorand.send.asset_create(
    au.AssetCreateParams(
        sender=creator.addr,
        total=10_000_000,
        decimals=0,
        asset_name="Token B",
        unit_name="TKB",
        note=randbytes(8),
    )
)
asset_b = result_b.asset_id
assert asset_a < asset_b, "asset a must have lower id than asset b"
print_success(f"Created ASAs — assetA: {asset_a}, assetB: {asset_b}")

# Step 7: Fund app account
print_step(7, "Funding app account...")
algorand.account.ensure_funded(
    account_to_fund=client.app_address,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_algo(1),
)
print_success(f"Funded app {shorten_address(client.app_address)}")

# Step 8: Bootstrap pool
print_step(8, "Bootstrapping pool...")
seed_txn = algorand.create_transaction.payment(
    au.PaymentParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(300_000),
    )
)
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="bootstrap",
        args=[seed_txn, asset_a, asset_b],
        extra_fee=ITXN_FEE * 3,  # 3 inner txns: create LP + opt-in A + opt-in B
        note=randbytes(8),
    )
)
pool_token = resp.abi_return
assert isinstance(pool_token, int)
print_success(f"Pool bootstrapped — pool token ID: {pool_token}")

# Step 9: Opt deployer into pool token
print_step(9, "Deployer opting into pool token...")
algorand.send.asset_opt_in(
    au.AssetOptInParams(
        sender=creator.addr,
        asset_id=pool_token,
        note=randbytes(8),
    )
)
print_success("Deployer opted into pool token")


def get_balance(addr: str, asset_id: int) -> int:
    info = algorand.asset.get_account_information(addr, asset_id)
    return info.balance


# Step 10: Add initial liquidity
print_step(10, "Adding liquidity (10,000 TKA + 10,000 TKB)...")
a_xfer = algorand.create_transaction.asset_transfer(
    au.AssetTransferParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=10_000,
        asset_id=asset_a,
    )
)
b_xfer = algorand.create_transaction.asset_transfer(
    au.AssetTransferParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=10_000,
        asset_id=asset_b,
    )
)
client.send.call(
    au.AppClientMethodCallParams(
        method="add_liquidity",
        args=[a_xfer, b_xfer],
        extra_fee=ITXN_FEE,  # 1 inner txn: transfer LP tokens
        note=randbytes(8),
    )
)

# Verify: sqrt(10000 * 10000) = 10,000 LP minted
lp_balance = get_balance(creator.addr, pool_token)
assert_equal(lp_balance, 10_000, "LP tokens minted (geometric mean)")
app_a = get_balance(client.app_address, asset_a)
app_b = get_balance(client.app_address, asset_b)
assert_equal(app_a, 10_000, "app TKA balance")
assert_equal(app_b, 10_000, "app TKB balance")
k_initial = app_a * app_b
print_info(f"Initial k = {app_a} * {app_b} = {k_initial}")
print_success("Liquidity added")

# Step 11: Swap 1,000 TKA -> TKB
print_step(11, "Swapping 1,000 TKA -> TKB...")
swap_xfer = algorand.create_transaction.asset_transfer(
    au.AssetTransferParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=1_000,
        asset_id=asset_a,
    )
)
client.send.call(
    au.AppClientMethodCallParams(
        method="swap",
        args=[swap_xfer],
        extra_fee=ITXN_FEE,  # 1 inner txn: transfer TKB out
        note=randbytes(8),
    )
)

app_a = get_balance(client.app_address, asset_a)
app_b = get_balance(client.app_address, asset_b)
# out = 10000 * 1000 * 9970 / (10000 * 10000 + 1000 * 9970) = 906
assert_equal(app_a, 11_000, "app TKA after swap A->B")
assert_equal(app_b, 9_094, "app TKB after swap A->B (sent 906 TKB)")
user_b = get_balance(creator.addr, asset_b)
assert_equal(user_b, 10_000_000 - 10_000 + 906, "user TKB received from swap")
k_after_swap1 = app_a * app_b
print_info(f"After swap: k = {app_a} * {app_b} = {k_after_swap1}")
assert k_after_swap1 > k_initial, "k must increase due to fees"
print_success("Swap complete — k increased (fees earned by pool)")

# Step 12: Swap 500 TKB -> TKA
print_step(12, "Swapping 500 TKB -> TKA...")
swap_xfer = algorand.create_transaction.asset_transfer(
    au.AssetTransferParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=500,
        asset_id=asset_b,
    )
)
client.send.call(
    au.AppClientMethodCallParams(
        method="swap",
        args=[swap_xfer],
        extra_fee=ITXN_FEE,
        note=randbytes(8),
    )
)

app_a = get_balance(client.app_address, asset_a)
app_b = get_balance(client.app_address, asset_b)
# out = 11000 * 500 * 9970 / (9094 * 10000 + 500 * 9970) = 571
assert_equal(app_a, 10_429, "app TKA after swap B->A (sent 571 TKA)")
assert_equal(app_b, 9_594, "app TKB after swap B->A")
k_after_swap2 = app_a * app_b
print_info(f"After swap: k = {app_a} * {app_b} = {k_after_swap2}")
assert k_after_swap2 > k_after_swap1, "k must increase due to fees"
print_success("Constant-product invariant maintained (k only grows with fees)")

# Step 13: Remove liquidity
print_step(13, "Removing liquidity (5,000 LP tokens)...")
pool_xfer = algorand.create_transaction.asset_transfer(
    au.AssetTransferParams(
        sender=creator.addr,
        receiver=client.app_address,
        amount=5_000,
        asset_id=pool_token,
    )
)
client.send.call(
    au.AppClientMethodCallParams(
        method="remove_liquidity",
        args=[pool_xfer],
        extra_fee=ITXN_FEE * 2,  # 2 inner txns: transfer A + transfer B
        note=randbytes(8),
    )
)

# Verify proportional withdrawal: burn 5000 / 10000 circulating = 50%
# a_out = 10429 * 5000 / 10000 = 5214
# b_out = 9594 * 5000 / 10000 = 4797
app_a = get_balance(client.app_address, asset_a)
app_b = get_balance(client.app_address, asset_b)
assert_equal(app_a, 10_429 - 5_214, "app TKA after remove")
assert_equal(app_b, 9_594 - 4_797, "app TKB after remove")

user_lp = get_balance(creator.addr, pool_token)
assert_equal(user_lp, 5_000, "remaining LP tokens")

user_a = get_balance(creator.addr, asset_a)
user_b = get_balance(creator.addr, asset_b)
print_info(f"Received back: {5_214} TKA + {4_797} TKB for 5,000 LP tokens")
print_info(f"Remaining pool: {app_a} TKA + {app_b} TKB")
print_success("Liquidity removed proportionally")

print_header("All assertions passed!")
