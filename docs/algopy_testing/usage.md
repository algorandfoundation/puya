# Usage

The Algorand Python Testing framework provides a powerful set of tools for testing your Algorand Python smart contracts within Python interpeter. This section will continue delving into the main features and concepts of the framework.

> Please note that this framework is in preview, detailed documentation is to follow, if you are interested in specific op code or having trouble implementing a test, reach out to us on #algokit channel on official Algorand discord.

## Test Context Manager

The core of the testing framework is the `algopy_testing_context` [context manager](https://docs.python.org/3/library/contextlib.html#contextlib.ContextDecorator). This creates a simulated Algorand environment for your tests that mimics major behaviour of AVM in Python interpreter.

```py
from algopy_testing import algopy_testing_context

def test_my_contract():
    with algopy_testing_context() as ctx:
        # Your test code here
        pass
```

The context manager provides an object of type `AlgopyTestContext`, which gives you access to various methods for interacting with the simulated environment.

## Primitive Types

The framework provide Python implementation for various primitive types that mirror those available in the Algorand Virtual Machine (AVM):

### UInt64

Represents a 64-bit unsigned integer.

```py
import algopy

x = algopy.UInt64(100)

# or

with algopy_testing_context() as ctx:
    x = ctx.any_uint64()
```

### Bytes

Represents a byte string.

```py
import algopy

value = algopy.Bytes(b"Hello, Algorand!")

# or

with algopy_testing_context() as ctx:
    value = ctx.any_bytes()
```

### String

Represents a UTF-8 encoded string.

```py
from algopy import String

value = String("Hello, Algorand!")

# or

with algopy_testing_context() as ctx:
    value = ctx.any_string()
```

### BigUInt

Represents an arbitrary-precision unsigned integer.

```py
from algopy import BigUInt

x = BigUInt(100)

# or

with algopy_testing_context() as ctx:
    x = ctx.any_biguint()
```

## ARC4 Types

Covers types available under `algopy.arc4` namespace. Refer to [ARC4](https://arc.algorand.foundation/ARCs/arc-0004) specification for more details.

```py
from algopy import arc4

uint8_value = arc4.UInt8(255)
uint16_value = arc4.UInt16(65535)
uint32_value = arc4.UInt32(4294967295)
uint64_value = arc4.UInt64(18446744073709551615)
uint128_value = arc4.UInt128(340282366920938463463374607431766945460)
uint256_value = arc4.UInt256(1157920892373161954235408971637716047373)
uint512_value = arc4.UInt512(340282366920938463463374607431766945460)

bool_value = arc4.Bool(True)

bytes_value = arc4.DynamicBytes(b"Hello, Algorand!")

string_value = arc4.String("Hello, Algorand!")

address_value = arc4.Address("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ")

static_array_value = algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]](
            *[algopy.arc4.Byte(0) for _ in range(32)]
        )

... # More types available
```

## AVM abstractions

### Assets

You can create and manage assets in your tests:

```py
asset = ctx.any_asset(name=algopy.Bytes(b"TestCoin"), total=algopy.UInt64(1000000))
```

### Accounts

Create nad manage accounts

```py
account = ctx.any_account(balance=algopy.UInt64(1000000))
```

### Applications

Create applications

```py
app = ctx.any_application(approval_program=algopy.Bytes(b"approval_code"), clear_state_program=algopy.Bytes(b"clear_code"))
```

### Transactions

Supports all available transaction types in AVM.

```py
txn = ctx.any_pay_txn(sender=algopy.Address("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"), receiver=algopy.Address("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"), amount=algopy.UInt64(1000000))

# Asset transfer transaction
asset_transfer_txn = ctx.any_asset_transfer_transaction(
    sender=algopy.Address("SENDER_ADDRESS"),
    receiver=algopy.Address("RECEIVER_ADDRESS"),
    asset=algopy.Asset(1234),
    amount=algopy.UInt64(100)
)

# Asset config transaction
asset_config_txn = ctx.any_asset_config_transaction(
    sender=algopy.Address("SENDER_ADDRESS"),
    total=algopy.UInt64(1000000),
    decimals=algopy.UInt32(6),
    unit_name=algopy.String("COIN"),
    asset_name=algopy.String("My Coin")
)

# Key registration transaction
key_reg_txn = ctx.any_key_registration_transaction(
    sender=algopy.Address("SENDER_ADDRESS"),
    vote_pk=algopy.Bytes(b"vote_public_key"),
    selection_pk=algopy.Bytes(b"selection_public_key")
)

# Application call transaction
app_call_txn = ctx.any_application_call_transaction(
    sender=algopy.Address("SENDER_ADDRESS"),
    app_id=algopy.UInt64(1),
    on_complete=algopy.OnComplete.NoOp,
    app_args=[algopy.Bytes(b"arg1"), algopy.Bytes(b"arg2")]
)

... # More transaction types available
```

### Inner transactions

```py
# Create and submit inner transactions
contract = SomeAlgorandPythonContract()
dummy_asset = ctx.any_asset()
contract.opt_in_dummy_asset(dummy_asset)

# Access all submitted inner transaction groups
all_itxn_groups = ctx.get_all_submitted_itxn_groups()
assert len(all_itxn_groups) == 1

# Access a specific inner transaction group
first_itxn_group = ctx.get_submitted_itxn_group(0)
assert len(first_itxn_group) == 1

# Access the last submitted inner transaction
last_itxn = ctx.last_submitted_itxn.asset_transfer # NOTE: this auto asserts if last submitted itxn group is indeed of type AssetTransfer
assert last_itxn.asset_receiver == ctx.default_application.address

# Clear inner transaction groups
ctx.clear_inner_transaction_groups()
assert len(ctx.get_all_submitted_itxn_groups()) == 0
```

These examples demonstrate how to create inner transactions, access them individually or in groups, make assertions about their properties, and clear the inner transaction groups when needed.

## State Management

### `Global`

Patch `Global` fields that define the global state of the simulated blockchain

```py
ctx.patch_global_fields(latest_timestamp=algopy.UInt64(1000))
```

### Global State

To be documented...

### Local State

To be documented...

### Scratch Space

To be documented...

### Boxes

To be documented...

> NOTE: Higher level Boxes interface introduce in v2.1.0 is not supported yet, however all low level Box 'op' calls are available.

## Smart Signatures

Test logic signatures (also known as smart signatures):

```py
result = ctx.execute_logicsig(my_logic_sig, lsig_args=[algopy.Bytes(b"arg1")])
```

## Operational codes (`op` codes)

### Cryptographic operations

All cryptop ops have matching python implementation available for use and execution within test context.

```py
from algopy import op

# Hashing
sha256_result = op.sha256(algopy.Bytes(b"data"))
keccak256_result = op.keccak256(algopy.Bytes(b"data"))

# Verification
ed25519verify_result = op.ed25519verify(data, signature, public_key)
```

## Property Based Testing

The `any_* ` methods in the context manager can be used with custom [hypothesis](https://hypothesis.readthedocs.io/en/latest/) strategies for property-based testing. This allows you to generate a wide range of test inputs automatically. Notes, requires separate installation of `hypothesis` package.
