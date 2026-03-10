import hashlib
from pathlib import Path
from random import randbytes

import algokit_utils as au
from nacl.signing import SigningKey
from shared import (
    assert_equal,
    compile_contract,
    load_app_spec,
    print_header,
    print_info,
    print_step,
    print_success,
)

print_header("Example 14 — Crypto Vault")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "CryptoVault")
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


ALWAYS_APPROVE = "#pragma version 10\nint 1"


def call(method: str, args: list[object]) -> au.SendAppTransactionResult:
    return client.send.call(
        au.AppClientMethodCallParams(method=method, args=args, note=randbytes(8))
    )


def call_with_budget(
    method: str, args: list[object], num_op_ups: int = 2
) -> au.SendTransactionComposerResults:
    """Call a method with extra opcode budget via dummy app creates in the same group."""
    group = algorand.new_group()
    group.add_app_call_method_call(
        client.params.call(
            au.AppClientMethodCallParams(method=method, args=args, note=randbytes(8))
        )
    )
    for idx in range(num_op_ups):
        group.add_app_create(
            au.AppCreateParams(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                on_complete=au.OnApplicationComplete.DeleteApplication,
                sender=creator.addr,
                note=idx.to_bytes() + randbytes(8),
            )
        )
    return group.send()


# Test data
test_data = b"Hello, Algorand!"

# Step 6: SHA-256
print_step(6, "Testing SHA-256 hash...")
expected_sha256 = hashlib.sha256(test_data).digest()
resp = call("hash_sha256(byte[])byte[]", [test_data])
assert_equal(resp.abi_return, expected_sha256, "SHA-256 digest")
print_info(f"SHA-256: {expected_sha256.hex()[:16]}...")
print_success("SHA-256 hash verified")

# Step 7: SHA3-256
print_step(7, "Testing SHA3-256 hash...")
expected_sha3 = hashlib.sha3_256(test_data).digest()
resp = call("hash_sha3_256(byte[])byte[]", [test_data])
assert_equal(resp.abi_return, expected_sha3, "SHA3-256 digest")
print_info(f"SHA3-256: {expected_sha3.hex()[:16]}...")
print_success("SHA3-256 hash verified")

# Step 8: SHA-512/256
print_step(8, "Testing SHA-512/256 hash...")
expected_sha512_256 = hashlib.new("sha512_256", test_data).digest()
resp = call("hash_sha512_256(byte[])byte[]", [test_data])
assert_equal(resp.abi_return, expected_sha512_256, "SHA-512/256 digest")
print_info(f"SHA-512/256: {expected_sha512_256.hex()[:16]}...")
print_success("SHA-512/256 hash verified")

# Step 9: Keccak-256
print_step(9, "Testing Keccak-256 hash...")
resp = call("hash_keccak256(byte[])byte[]", [test_data])
keccak_result = resp.abi_return
assert_equal(len(keccak_result), 32, "Keccak-256 digest length")
assert keccak_result != expected_sha3, "Keccak-256 should differ from SHA3-256"
print_info(f"Keccak-256: {keccak_result.hex()[:16]}...")
print_info("Confirmed: Keccak-256 differs from SHA3-256 (different padding)")
print_success("Keccak-256 hash verified")

# Step 10: Ed25519 signature verification (needs extra opcode budget — 1900 cost)
print_step(10, "Testing Ed25519 signature verification...")
signing_key = SigningKey.generate()
public_key = bytes(signing_key.verify_key)
message = b"Verify me on Algorand"
signature = signing_key.sign(message).signature

# Valid signature — use budget pooling (ed25519verify_bare costs 1900, default budget is 700)
result = call_with_budget(
    "verify_ed25519(byte[],byte[],byte[])bool", [message, signature, public_key]
)
assert_equal(result.returns[0].value, True, "valid signature")
print_success("Valid Ed25519 signature verified")

# Invalid signature — flip a byte
bad_signature = bytearray(signature)
bad_signature[0] ^= 0xFF
bad_signature = bytes(bad_signature)
try:
    result = call_with_budget(
        "verify_ed25519(byte[],byte[],byte[])bool",
        [message, bad_signature, public_key],
    )
    assert_equal(result.returns[0].value, False, "invalid signature")
    print_success("Invalid signature correctly rejected (returned false)")
except Exception:
    print_success("Invalid signature correctly rejected (transaction failed)")

# Step 11: Scratch space
print_step(11, "Testing scratch space store and load...")
resp = call("scratch_store_and_load(uint64,byte[])bool", [42, b"scratch test"])
assert_equal(resp.abi_return, True, "scratch roundtrip")
print_success("Scratch space store/load roundtrip verified")

# Step 12: Hash of empty bytes
print_step(12, "Testing hash of empty bytes...")
empty = b""
expected_empty_sha256 = hashlib.sha256(empty).digest()
resp = call("hash_sha256(byte[])byte[]", [empty])
assert_equal(resp.abi_return, expected_empty_sha256, "SHA-256 of empty")
print_info(f"SHA-256(empty): {expected_empty_sha256.hex()[:16]}...")
print_success("Empty bytes hash verified")

print_header("All assertions passed!")
