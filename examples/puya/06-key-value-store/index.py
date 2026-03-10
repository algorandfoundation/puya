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

print_header("Example 06 — Key-Value Store")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "KeyValueStore")
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

# Step 6: Fund app for box MBR
print_step(6, "Funding app with 1 ALGO for box MBR...")
algorand.account.ensure_funded(
    account_to_fund=client.app_address,
    dispenser_account=account,
    min_spending_balance=au.AlgoAmount.from_micro_algo(1_000_000),
)
print_success("App funded")


def call(
    method: str,
    args: list[object] | None = None,
    box_references: list[au.BoxReference | au.BoxIdentifier] | None = None,
) -> object:
    resp = client.send.call(
        au.AppClientMethodCallParams(
            method=method,
            args=args or [],
            box_references=box_references,
            note=randbytes(8),
        )
    )
    return resp.abi_return


def map_box_key(key: int) -> bytes:
    """Build full box key for a BoxMap entry: prefix + encoded UInt64."""
    return b"p_" + key.to_bytes(8)


# Step 7: Box CRUD (counter)
print_step(7, "Testing Box CRUD — counter...")
call("set_counter(uint64)void", [10], box_references=["counter"])
assert_equal(call("get_counter()uint64", box_references=["counter"]), 10, "counter = 10")
print_success("set_counter(10) and get_counter() verified")

assert_equal(
    call("increment_counter()uint64", box_references=["counter"]), 11, "counter incremented"
)
print_success("increment_counter() returned 11")

assert_equal(call("counter_exists()bool", box_references=["counter"]), True, "counter exists")
print_success("counter_exists() returned True")

call("delete_counter()void", box_references=["counter"])
assert_equal(call("counter_exists()bool", box_references=["counter"]), False, "counter deleted")
print_success("delete_counter() verified — counter no longer exists")

# Step 8: Box with get/default (label)
print_step(8, "Testing Box with get/default — label...")
assert_equal(
    call("get_label_or_default(string)string", ["(empty)"], box_references=["label"]),
    "(empty)",
    "label default when missing",
)
print_success("get_label_or_default() returned '(empty)' for missing box")

call("set_label(string)void", ["Hello Boxes!"], box_references=["label"])
assert_equal(call("get_label()string", box_references=["label"]), "Hello Boxes!", "label value")
print_success("set_label('Hello Boxes!') and get_label() verified")

call("set_label(string)void", ["Updated!"], box_references=["label"])
assert_equal(call("get_label()string", box_references=["label"]), "Updated!", "label updated")
print_success("Label updated to 'Updated!'")

call("delete_label()void", box_references=["label"])
print_success("Label deleted")

# Step 9: BoxMap CRUD (profiles)
print_step(9, "Testing BoxMap CRUD — profiles...")
call("map_set(uint64,string)void", [1, "Alice"], box_references=[map_box_key(1)])
call("map_set(uint64,string)void", [2, "Bob"], box_references=[map_box_key(2)])
call("map_set(uint64,string)void", [3, "Charlie"], box_references=[map_box_key(3)])
print_success("Set profiles: Alice, Bob, Charlie")

assert_equal(
    call("map_get(uint64)string", [1], box_references=[map_box_key(1)]), "Alice", "profile 1"
)
assert_equal(
    call("map_get(uint64)string", [2], box_references=[map_box_key(2)]), "Bob", "profile 2"
)
print_success("map_get() verified for Alice and Bob")

assert_equal(
    call("map_exists(uint64)bool", [1], box_references=[map_box_key(1)]), True, "profile 1 exists"
)
print_success("map_exists(1) returned True")

assert_equal(
    call(
        "map_get_default(uint64,string)string", [99, "unknown"], box_references=[map_box_key(99)]
    ),
    "unknown",
    "missing profile default",
)
print_success("map_get_default(99) returned 'unknown'")

call("map_delete(uint64)void", [2], box_references=[map_box_key(2)])
assert_equal(
    call("map_exists(uint64)bool", [2], box_references=[map_box_key(2)]),
    False,
    "profile 2 deleted",
)
print_success("map_delete(2) verified — profile no longer exists")

# Clean up remaining map entries
call("map_delete(uint64)void", [1], box_references=[map_box_key(1)])
call("map_delete(uint64)void", [3], box_references=[map_box_key(3)])

# Step 10: BoxRef (Box[Bytes]) CRUD and slicing
print_step(10, "Testing BoxRef (Box[Bytes]) CRUD and slicing...")
call("blob_set(byte[])void", [b"Hello, World!"], box_references=["blob"])
assert_equal(call("blob_length()uint64", box_references=["blob"]), 13, "blob length")
print_success("blob_set('Hello, World!') — length = 13")

assert_equal(
    call("blob_extract(uint64,uint64)byte[]", [0, 5], box_references=["blob"]),
    b"Hello",
    "blob extract",
)
print_success("blob_extract(0, 5) returned 'Hello'")

call("blob_replace(uint64,byte[])void", [7, b"Boxes"], box_references=["blob"])
assert_equal(
    call("blob_extract(uint64,uint64)byte[]", [0, 13], box_references=["blob"]),
    b"Hello, Boxes!",
    "blob after replace",
)
print_success("blob_replace(7, 'Boxes') — now 'Hello, Boxes!'")

assert_equal(
    call("blob_slice(uint64,uint64)byte[]", [7, 12], box_references=["blob"]),
    b"Boxes",
    "blob slice",
)
print_success("blob_slice(7, 12) returned 'Boxes'")

call("blob_delete()void", box_references=["blob"])
print_success("Blob deleted")

# Pre-allocate and partially write
call("blob_create(uint64)void", [32], box_references=["blob"])
assert_equal(call("blob_length()uint64", box_references=["blob"]), 32, "pre-allocated blob")
print_success("blob_create(32) — pre-allocated 32 bytes")

call("blob_replace(uint64,byte[])void", [0, b"DEADBEEF"], box_references=["blob"])
assert_equal(
    call("blob_extract(uint64,uint64)byte[]", [0, 8], box_references=["blob"]),
    b"DEADBEEF",
    "blob partial write",
)
print_success("Partial write verified — 'DEADBEEF' at offset 0")
call("blob_delete()void", box_references=["blob"])

# Step 11: Global state (tracks set_counter + increment_counter + 3x map_set = 5)
print_step(11, "Reading dynamic global state...")
assert_equal(call("get_total_ops()uint64"), 5, "total operations")
print_success("get_total_ops() returned 5")

print_header("All assertions passed!")
