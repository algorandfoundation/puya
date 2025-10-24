# ARC4 Encoding Vulnerabilities

# Overview

## Definitions

**ABI argument**: An argument passed to an ABI method by an external caller (note: not internal calls to a subroutine)

**ABI return value**: The return value from another app’s ABI method via an inner transaction

**Untrusted source:** Any source of an ABI value from a potentially malicious (or error-prone) implementation. For arguments, this could be a malicious client. For return values, this could be a malicious contract.

**Fixed-Length value:** Any ABI value with a statically known length. This includes static/fixed arrays, static aliases such as `Address`, `Uint<N>`, tuples with all static types (including nested structs and tuples), and structs with all fields being static types (including nested structs and tuples)

**Dynamic array:** Any dynamic array at the top-level value. For example, `Uint<8>[]`

**Dynamic tuple:** Any dynamic ABI type (tuple or struct) that is not a fixed-length value or top-level dynamic array.

## What's the Issue?

Before version 5.3.2, PuyaPy did not validate the encoding of ABI arguments or return values. This could lead to unexpected behavior when attempting to use these types. This behavior can be exploited by malicious actors (or cause errors due to faulty clients). At this point in time, there have not been any known exploits of this vulnerability. The “Am I Vulnerable” section includes an overview of the types of panics with more details and examples in the following sections.

## Affected Languages

| Language                      | Vulnerable                                      | Notes                                                                                                               |
| :---------------------------- | :---------------------------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| Algorand Python (PuyaPy)      | **Yes** (\< 5.3.2)                              | Fixed in Puya 5.3.2+ and 4.11.0+                                                                                    |
| Algorand TypeScript (Puya-TS) | **Yes** (\<v1.0.0-alpha.90 and \<1.0.0-beta.73) | Uses the same compiler backend \- requires an update to get the fixed compiler backend                              |
| PyTeal                        | Yes                                             | Can be fixed with [manual validation checks](https://pyteal.readthedocs.io/en/stable/abi.html#registering-methods). |
| TEALScript                    | Partially                                       | Validates static method arguments, but not dynamic tuples or ABI return values (see example 2\)                     |
| Tealish                       | Yes                                             | Not fixed \- documented behavior                                                                                    |

## How to Identify Vulnerabilities?

### In a Contract

The following examples show how the vulnerability would appear in a contract. PuyaPy is shown for reference.

#### Fixed-Length Argument Overflow

Your contract is vulnerable to the fixed-length argument overflow if the following is true:

1. You are using Puya or Pyteal (TEALScript is not vulnerable)
2. You accept fixed-size ABI types from untrusted sources and don’t manually check the length:
    1. **Method parameters** (e.g., `@arc4.abimethod` arguments)
    2. **ABI return values** from inner transactions (`arc4.abi_call`)
    3. **Types include**: `StaticArray[Byte, Literal[N]]`, `UIntN` (e.g., `UInt256`, `UInt512`), `Address, or any struct/tuple that is composed of static-length types`
3. You combine that parameter with other values into a new struct, array, or tuple.
4. Other values in the struct/array/tuple are not directly from user input and may be security-critical, such as timestamps, amounts, access flags, etc.

Example 1: Fixed-Length Argument Overflow

```py
from algopy import arc4, UInt64
from typing import Literal

# Type alias for a 32-byte static array
StaticBytes32 = arc4.StaticArray[arc4.Byte, Literal[32]]

SUPER_IMPORTANT_VALUE = 42

class VulnerableContract(arc4.ARC4Contract):
    @arc4.abimethod
    def static_value(self, static_bytes: StaticBytes32) -> arc4.UInt64:
        # ⚠️ VULNERABLE: If static_bytes is more than 32 bytes,
        # it will overflow into SUPER_IMPORTANT_VALUE
        array = arc4.Tuple((static_bytes.copy(), arc4.UInt64(SUPER_IMPORTANT_VALUE)))
        return array[1]
```

**Attack:** Caller sends 40 bytes for `static_bytes` instead of 32\. The extra 8 bytes overwrite `SUPER_IMPORTANT_VALUE`, allowing the attacker to control what should be a constant value.

Example 2: Fixed-Length ABI Return Overflow

```py
from algopy import arc4, UInt64
from typing import Literal

StaticBytes32 = arc4.StaticArray[arc4.Byte, Literal[32]]
SUPER_IMPORTANT_VALUE = 42

class VulnerableContract(arc4.ARC4Contract):
    @arc4.abimethod
    def malicious_contract_return(self, malicious_app_id: UInt64) -> arc4.UInt64:
        # Call external contract that claims to return 32 bytes
        result, _txn = arc4.abi_call[StaticBytes32](
            "returnStaticBytes()",
            app_id=malicious_app_id
        )

        # ⚠️ VULNERABLE: If malicious contract returns 40 bytes instead of 32,
        # it will overflow into SUPER_IMPORTANT_VALUE
        array = arc4.Tuple((result.copy(), arc4.UInt64(SUPER_IMPORTANT_VALUE)))
        return array[1]
```

**Attack:** Malicious contract returns 40 bytes instead of 32\. The extra 8 bytes overwrite `SUPER_IMPORTANT_VALUE`, giving the attacker control over internal contract logic.

#### “Hidden” Dynamic Array Values

Your contract may be vulnerable to “hidden” values in dynamic arrays if the following is true:

1. You are using Puya or Pyteal (TEALScript is not vulnerable)
2. You accept a dynamic array from untrusted sources and don’t manually check the length
3. You use the length of the array explicitly or implicitly:
    1. **Explicitly**: `len()` or `.length` on the array
    2. **Implicitly**: Iteration (i.e, `for in`)
    3. **Pyteal only**: Array comparison

Example “Hidden” Dynamic Array Values

```py
class HiddenValues(ARC4Contract):
    even_numbers: GlobalState[DynamicArray[UInt64]]

    def __init__(self) -> None:
        self.even_numbers = GlobalState(DynamicArray[UInt64])

    @abimethod()
    def store_numbers(self, numbers: DynamicArray[UInt64]) -> None:
        for num in numbers:
            assert num % 2 == 0, "Only even numbers are allowed"
        self.even_numbers.value = numbers.copy()

    @abimethod()
    def get_even_number(self, index: UInt64) -> UInt64:
        return self.even_numbers.value[index]
```

**Attack:** A malicious caller sends an array with a length prefix shorter than the actual number of elements in the array. Any element past the length the attacker specified in the prefix will be “hidden” from the check in `store_numbers`. This would allow the storage of odd numbers and subsequently allow them to access the odd number in `get_even_number`.

#### Unexpected Panics

Your contract may panic at unexpected times if the following is true:

1. You accept any ABI type from untrusted sources
    1. TEALScript users: Dynamic arrays are vulnerable, but not fixed-length types or dynamic arrays
2. You don’t validate the encoding
    1. Fixed-length types: check the length is what the type specifies
    2. Dynamic arrays: check that the length prefix matches the true number of elements
    3. Dynamic tuples: check that all elements can be accessed (and validate all nested elements such as nested dynamic array prefixes or nested tuple elements)
3. You save the value in the contract state and try to use it in a subsequent call.

```py
class InvalidEncoding(ARC4Contract):
    numbers: Box[DynamicArray[UInt64]]
    numbers_sum: Box[UInt64]

    def __init__(self) -> None:
        self.numbers = GlobalState(DynamicArray[UInt64])
        self.numbers_sum = GlobalState(UInt64(0))

    @abimethod()
    def set_numbers(self, nums: DynamicArray[UInt64]) -> None:
        self.numbers.value = nums.copy()

    @abimethod()
    def sum_numbers(self) -> UInt64:
        for num in self.numbers.value:
            self.numbers_sum.value += num

        return self.numbers_sum.value
```

**Attack:** Since \`set_numbers\` just directly stored the array without attempting to use them and without validating the encoding, they may be improperly encoded. If that is the case, then sum_numbers could panic. This means an attacker can make sum_numbers; thus, the setting of numbers_sum is unreachable. If sum_numbers was a critical path for a state transition, the contract is effectively deadlocked.

Some invalid encoding examples (non-exhaustive):

-   A dynamic array ABI length prefix exceeds the actual array length
-   A dynamic tuple head offset exceeds the length of the actual tuple
-   A dynamic tuple head offset is higher than the next element (which would result in an invalid extract)
-   A static value is more or less than the expected value, and attempted to be used elsewhere where that would cause a panic
-   A value claiming to be a uint64 is larger than a uint64 (btoi panic)

### In TEAL

#### Vulnerable TEAL

Missing size validation before using arguments:

```
main_test_arg_route@3:
    txna ApplicationArgs 1  // # Load recipient
    txna ApplicationArgs 2  // # Load chain
    concat                  // # NO SIZE CHECK!
    pushbytes 0x0aeedf46
    swap
    concat
    log
    return
```

#### Fixed TEAL

Includes explicit length assertions:

```
check_static_bytes:
    txna ApplicationArgs 1
    dup
    len                     // # Check length
    pushint 32              // # Expected size
    ==
    assert // invalid number of bytes for uint8[32]  # Validate
    txn Sender
    ==
    return
```

**Key difference:** Look for `len`, `pushint`, `==`, `assert` sequence after loading `ApplicationArgs` but before using the data.

## Action Required

1. **Implement** the fixes from the appropriate language listed below
2. **Recompile** all updated contracts
3. **Redeploy** affected contracts
4. **Test** that oversized inputs are now rejected
