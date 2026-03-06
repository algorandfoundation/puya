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

print_header("Example 09 — Token Manager")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "TokenManager")
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
print_success(f"Deployer funded: {creator.addr}")

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


def call(
    method: str,
    args: list[object] | None = None,
    extra_fee: au.AlgoAmount | None = ITXN_FEE,
) -> object:
    resp = client.send.call(
        au.AppClientMethodCallParams(
            method=method, args=args or [], note=randbytes(8), extra_fee=extra_fee
        )
    )
    return resp.abi_return


# Step 6: Fund app account (needed for inner transaction fees and ASA MBR)
print_step(6, "Funding app with 1 ALGO...")
algorand.account.ensure_funded(
    account_to_fund=client.app_address,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_algo(1),
)
print_success("App funded")

# Step 7: Create ASA via inner transaction
print_step(7, "Calling createAsset('TestToken', 'TT', 1000000, 0, false)...")
asset_id = call(
    "create_asset(string,string,uint64,uint64,bool)uint64",
    ["TestToken", "TT", 1_000_000, 0, False],
)
assert isinstance(asset_id, int)
assert asset_id > 0
print_success(f"createAsset returned assetId: {asset_id}")

# Step 8: Opt app into the ASA
print_step(8, "Calling optInToAsset...")
call("opt_in_to_asset(uint64)void", [asset_id])
print_success("optInToAsset succeeded")

# Verify app holds all tokens
app_holding = algorand.asset.get_account_information(client.app_address, asset_id)
assert_equal(app_holding.balance, 1_000_000, "app balance after opt-in")
print_success("App holds all 1,000,000 tokens")

# Step 9: Create receiver and opt them in to the ASA
print_step(9, "Creating receiver account...")
receiver = algorand.account.random()
algorand.account.ensure_funded(
    account_to_fund=receiver.addr,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_algo(1),
)
algorand.account.set_signer_from_account(receiver)
print_success(f"Receiver: {shorten_address(receiver.addr)}")

# Receiver opts in to the ASA (external transaction, not via contract)
algorand.send.asset_opt_in(
    au.AssetOptInParams(sender=receiver.addr, asset_id=asset_id, note=randbytes(8))
)
print_success("Receiver opted in to ASA")

# Step 10: Transfer tokens from app to receiver
print_step(10, "Transferring 500 tokens to receiver...")
call("transfer_asset(uint64,address,uint64)void", [asset_id, receiver.addr, 500])

receiver_holding = algorand.asset.get_account_information(receiver.addr, asset_id)
assert_equal(receiver_holding.balance, 500, "receiver balance after transfer")

app_holding = algorand.asset.get_account_information(client.app_address, asset_id)
assert_equal(app_holding.balance, 999_500, "app balance after transfer")
print_success("Transfer verified: receiver=500, app=999500")

# Step 11: Freeze receiver's account
print_step(11, "Freezing receiver's account...")
call("freeze_account(uint64,address,bool)void", [asset_id, receiver.addr, True])

receiver_holding = algorand.asset.get_account_information(receiver.addr, asset_id)
assert_equal(receiver_holding.frozen, True, "receiver frozen status")
print_success("Receiver account frozen")

# Step 12: Clawback tokens from frozen receiver
print_step(12, "Clawing back 200 tokens from receiver...")
call(
    "clawback_asset(uint64,address,address,uint64)void",
    [asset_id, receiver.addr, client.app_address, 200],
)

receiver_holding = algorand.asset.get_account_information(receiver.addr, asset_id)
assert_equal(receiver_holding.balance, 300, "receiver balance after clawback")

app_holding = algorand.asset.get_account_information(client.app_address, asset_id)
assert_equal(app_holding.balance, 999_700, "app balance after clawback")
print_success("Clawback verified: receiver=300, app=999700")

# Step 13: Unfreeze and clawback remaining tokens before destroy
print_step(13, "Cleaning up: unfreeze and clawback remaining tokens...")
call("freeze_account(uint64,address,bool)void", [asset_id, receiver.addr, False])

receiver_holding = algorand.asset.get_account_information(receiver.addr, asset_id)
assert_equal(receiver_holding.frozen, False, "receiver unfrozen")
print_success("Receiver unfrozen")

# Clawback remaining tokens from receiver
call(
    "clawback_asset(uint64,address,address,uint64)void",
    [asset_id, receiver.addr, client.app_address, 300],
)
print_success("Remaining tokens clawed back")

# Receiver opts out of the ASA
algorand.send.asset_opt_out(
    au.AssetOptOutParams(
        sender=receiver.addr,
        asset_id=asset_id,
        creator=client.app_address,
        note=randbytes(8),
    )
)
print_info("Receiver opted out of ASA")

# Step 14: Destroy the ASA
print_step(14, "Destroying ASA via inner transaction...")
call("destroy_asset(uint64)void", [asset_id])
print_success("ASA destroyed")

print_header("All assertions passed!")
