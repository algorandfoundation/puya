"""Example 03: Logic Signature Gate — Deployment & Test Script

Compiles the gate smart signature with template variables,
funds its address, and sends a payment transaction signed by the
logic signature with a valid Ed25519 authority signature.

Prerequisites: LocalNet
"""

import base64
from pathlib import Path
from random import randbytes

import algokit_utils as au
from nacl.signing import SigningKey
from shared import (
    compile_contract,
    print_header,
    print_step,
    print_success,
    shorten_address,
)


def decode_address(addr: str) -> bytes:
    """Decode an Algorand address to its 32-byte public key."""
    padded = addr + "=" * ((8 - len(addr) % 8) % 8)
    return base64.b32decode(padded)[:32]


print_header("Example 03 — Logic Signature Gate")

# Step 1: Compile the contract with TEAL output
print_step(1, "Compiling LogicSig with --output-teal...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir, output_teal=True)
print_success("LogicSig compiled")

# Step 2: Generate an Ed25519 authority keypair for signing
print_step(2, "Generating Ed25519 authority keypair...")
signing_key = SigningKey.generate()
authority_pubkey = bytes(signing_key.verify_key)
print_success(f"Authority public key: {authority_pubkey.hex()[:16]}...")

# Step 3: Read TEAL and substitute template variables
print_step(3, "Substituting template variables in TEAL...")
teal_source = (out_dir / "gate.teal").read_text()

template_values: dict[str, str | int | bytes] = {}
for line in (example_dir / "template.vars").read_text().strip().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    key, value = line.split("=", 1)
    template_values[key.strip()] = int(value.strip())
template_values["AUTHORITY_KEY"] = authority_pubkey
print_success("Template variables substituted")

# Step 4: Connect to LocalNet and compile TEAL to bytecode
print_step(4, "Connecting to LocalNet & compiling TEAL to bytecode...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))

compiled = algorand.app.compile_teal_template(teal_source, template_values)
program_bytes = compiled.compiled_base64_to_bytes
print_success("TEAL compiled to bytecode")

# Step 5: Create and fund deployer account
print_step(5, "Creating deployer account...")
account = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(account)
print_success(f"Deployer funded: {shorten_address(account.addr)}")

# Step 6: Sign receiver address with the authority key
print_step(6, "Signing receiver address with authority key...")
receiver = account.addr
receiver_bytes = decode_address(receiver)
signature = signing_key.sign(receiver_bytes).signature
print_success(f"Signature: {signature.hex()[:16]}...")

# Step 7: Create LogicSig account with the signature as program arg
print_step(7, "Creating LogicSig account...")
lsig = algorand.account.logicsig(program_bytes, args=[signature])
print_success(f"LogicSig address: {shorten_address(lsig.addr)}")

# Step 8: Fund the LogicSig address from the deployer
print_step(8, "Funding LogicSig address...")
algorand.send.payment(
    au.PaymentParams(
        sender=account.addr,
        receiver=lsig.addr,
        amount=au.AlgoAmount(algo=10),
        note=randbytes(8),
    )
)
print_success("LogicSig funded with 10 ALGO")

# Step 9: Send a payment FROM the LogicSig address (the gate approves it)
print_step(9, "Sending payment from LogicSig address...")
result = algorand.send.payment(
    au.PaymentParams(
        sender=lsig.addr,
        receiver=receiver,
        amount=au.AlgoAmount(micro_algo=1_000_000),
        note=randbytes(8),
    )
)
print_success(f"Payment sent — TxID: {result.tx_id}")

print_header("All assertions passed!")
