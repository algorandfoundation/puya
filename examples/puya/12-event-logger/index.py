import hashlib
import struct
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


def event_selector(signature: str) -> bytes:
    """Compute the ARC-28 event selector: first 4 bytes of SHA-512/256(signature)."""
    return hashlib.new("sha512_256", signature.encode()).digest()[:4]


print_header("Example 12 — Event Logger")
example_dir = Path(__file__).parent

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "EventLogger")
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
client, _ = factory.send.bare.create(
    au.AppFactoryCreateParams(note=randbytes(8))
)
print_success(f"Contract deployed — App ID: {client.app_id}")


SWAPPED_SIG = "Swapped(uint64,uint64)"
SWAPPED_NATIVE_SIG = "SwappedNative(uint64,uint64)"
VALUESET_SIG = "ValueSet(uint64)"


def call(method: str, args: list[object]) -> au.SendAppTransactionResult:
    return client.send.call(
        au.AppClientMethodCallParams(
            method=method, args=args, note=randbytes(8)
        )
    )


def decode_uint64_pair(log: bytes) -> tuple[int, int]:
    """Decode an ARC-28 log with two uint64 fields (skip 4-byte selector)."""
    a, b = struct.unpack(">QQ", log[4:20])
    return a, b


def decode_uint64(log: bytes) -> int:
    """Decode an ARC-28 log with one uint64 field (skip 4-byte selector)."""
    return struct.unpack(">Q", log[4:12])[0]


# Step 6: Call emit_arc4_struct(10, 20)
print_step(6, "Calling emit_arc4_struct(10, 20)...")
resp = call("emit_arc4_struct(uint64,uint64)void", [10, 20])
logs = resp.confirmation.logs or []
assert_equal(len(logs), 1, "log count")
log = logs[0]
assert_equal(log[:4], event_selector(SWAPPED_SIG), "event selector")
a, b = decode_uint64_pair(log)
assert_equal((a, b), (20, 10), "swapped values")
print_success(f"emit_arc4_struct succeeded — {SWAPPED_SIG} a={a}, b={b}")

# Step 7: Call emit_native_struct(10, 20)
print_step(7, "Calling emit_native_struct(10, 20)...")
resp = call("emit_native_struct(uint64,uint64)void", [10, 20])
logs = resp.confirmation.logs or []
assert_equal(len(logs), 1, "log count")
log = logs[0]
assert_equal(log[:4], event_selector(SWAPPED_NATIVE_SIG), "event selector")
a, b = decode_uint64_pair(log)
assert_equal((a, b), (20, 10), "swapped values")
print_success(f"emit_native_struct succeeded — {SWAPPED_NATIVE_SIG} a={a}, b={b}")

# Step 8: Call emit_by_name(10, 20)
print_step(8, "Calling emit_by_name(10, 20)...")
resp = call("emit_by_name(uint64,uint64)void", [10, 20])
logs = resp.confirmation.logs or []
assert_equal(len(logs), 1, "log count")
log = logs[0]
assert_equal(log[:4], event_selector(SWAPPED_SIG), "event selector matches arc4.Struct version")
a, b = decode_uint64_pair(log)
assert_equal((a, b), (20, 10), "swapped values")
print_success("emit_by_name succeeded")

# Step 9: Call emit_by_signature(10, 20)
print_step(9, "Calling emit_by_signature(10, 20)...")
resp = call("emit_by_signature(uint64,uint64)void", [10, 20])
logs = resp.confirmation.logs or []
assert_equal(len(logs), 1, "log count")
log = logs[0]
assert_equal(log[:4], event_selector(SWAPPED_SIG), "event selector matches arc4.Struct version")
a, b = decode_uint64_pair(log)
assert_equal((a, b), (20, 10), "swapped values")
print_success("emit_by_signature succeeded")

# Verify all three "Swapped" styles produce identical logs
print_info("All three Swapped styles produce identical event logs")

# Step 10: Call emit_multiple(42)
print_step(10, "Calling emit_multiple(42)...")
resp = call("emit_multiple(uint64)void", [42])
logs = resp.confirmation.logs or []
assert_equal(len(logs), 2, "log count (two events)")
assert_equal(logs[0][:4], event_selector(SWAPPED_SIG), "first event selector")
a, b = decode_uint64_pair(logs[0])
assert_equal((a, b), (42, 42), "Swapped values")
assert_equal(logs[1][:4], event_selector(VALUESET_SIG), "second event selector")
x = decode_uint64(logs[1])
assert_equal(x, 42, "ValueSet value")
print_success(f"emit_multiple succeeded — Swapped({a},{b}) + ValueSet({x})")

# Step 11: Show selector computation
print_step(11, "ARC-28 selector computation...")
for sig in [SWAPPED_SIG, SWAPPED_NATIVE_SIG, VALUESET_SIG]:
    sel = event_selector(sig)
    print_info(f'SHA-512/256("{sig}")[:4] = {sel.hex()}')
print_success("Selector computation verified")

print_header("All assertions passed!")
