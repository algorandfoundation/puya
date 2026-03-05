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

print_header("Example 04 — Type Explorer")
example_dir = Path(__file__).parent

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "TypeExplorer")
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


# Step 6: UInt64 arithmetic
print_step(6, "UInt64 arithmetic...")
assert_equal(call("uint64_add(uint64,uint64)uint64", [10, 20]), 30, "10 + 20")
print_success("uint64_add(10, 20) returned 30")
assert_equal(call("uint64_pow(uint64,uint64)uint64", [2, 10]), 1024, "2 ** 10")
print_success("uint64_pow(2, 10) returned 1024")

# Step 7: BigUInt arithmetic (via arc4.UInt512)
print_step(7, "BigUInt arithmetic via arc4.UInt512...")
big_a = 2**256
big_b = 2**256
big_sum = big_a + big_b
big_prod = big_a * 3
assert_equal(
    call("biguint_add(uint512,uint512)uint512", [big_a, big_b]),
    big_sum,
    f"2^256 + 2^256 = {big_sum}",
)
print_success("biguint_add returned correct sum")
assert_equal(
    call("biguint_mul(uint512,uint512)uint512", [big_a, 3]),
    big_prod,
    f"2^256 * 3 = {big_prod}",
)
print_success("biguint_mul returned correct product")

# Step 8: Bytes operations
print_step(8, "Bytes length...")
assert_equal(call("bytes_len(byte[])uint64", [b"hello"]), 5, "len(b'hello')")
print_success("bytes_len('hello') returned 5")
assert_equal(call("bytes_len(byte[])uint64", [b""]), 0, "len(b'')")
print_success("bytes_len('') returned 0")

# Step 9: Type conversions (itob / btoi)
print_step(9, "Type conversions: itob and btoi...")
itob_result = call("itob_convert(uint64)byte[]", [42])
expected_bytes = (42).to_bytes(8, "big")
assert_equal(itob_result, expected_bytes, "itob(42)")
print_info(f"  itob(42) = {expected_bytes.hex()}")
print_success("itob(42) converted correctly")

btoi_result = call("btoi_convert(byte[])uint64", [expected_bytes])
assert_equal(btoi_result, 42, "btoi(itob(42))")
print_success("btoi round-trip returned 42")

# Step 10: Wide math — addw
print_step(10, "Wide math: addw (128-bit addition)...")
max_u64 = 2**64 - 1
result = call("wide_add(uint64,uint64)(uint64,uint64)", [max_u64, 1])
assert_equal(result, (1, 0), "addw(MAX_UINT64, 1) => carry=1, low=0")
print_success("addw(MAX_UINT64, 1) returned carry=1, low=0")

result = call("wide_add(uint64,uint64)(uint64,uint64)", [100, 200])
assert_equal(result, (0, 300), "addw(100, 200) => carry=0, low=300")
print_success("addw(100, 200) returned carry=0, low=300")

# Step 11: Wide math — mulw
print_step(11, "Wide math: mulw (128-bit multiplication)...")
result = call("wide_multiply(uint64,uint64)(uint64,uint64)", [max_u64, 2])
assert_equal(result, (1, max_u64 - 1), "mulw(MAX_UINT64, 2) => high=1, low=MAX-1")
print_success("mulw(MAX_UINT64, 2) returned high=1, low=MAX-1")

result = call("wide_multiply(uint64,uint64)(uint64,uint64)", [100, 200])
assert_equal(result, (0, 20000), "mulw(100, 200) => high=0, low=20000")
print_success("mulw(100, 200) returned high=0, low=20000")

print_header("All assertions passed!")
