---
title: Error Handling
description: Assertions, explicit failure, and error handling in Algorand Python
---

In Algorand Python, error handling and assertions play a crucial role in ensuring the correctness and robustness of smart contracts.

## Assertions

Assertions allow you to immediately fail a smart contract if a [Boolean statement or value](/puya/language-guide/types/#bool) evaluates to `False`. If an assertion fails, it immediately stops the execution of the contract and marks the call as a failure.

In Algorand Python, you can use the Python built-in `assert` statement to make assertions in your code.

For example:

```python
@subroutine
def set_value(value: UInt64):
    assert value > 4, "Value must be > 4"
```

### Assertion error handling

The (optional) string value provided with an assertion, if provided, will be added as a TEAL comment on the end of the assertion line. This works in concert with default AlgoKit Utils app client behaviour to show a TEAL stack trace of an error and thus show the error message to the caller (when source maps have been loaded).

## Explicit failure

For scenarios where you need to fail a contract explicitly, you can use
the [`op.err()`](/puya/api/algopy/algopyop/#err) operation. This operation causes the TEAL program to immediately
and unconditionally fail.

Alternatively [`op.exit(0)`](/puya/api/algopy/algopyop/#exit) will achieve the same result. A non-zero value will
do the opposite and immediately succeed.

## Logged errors (ARC-65)

For failure strings that live on-chain, Algorand Python provides
[`logged_assert`](/puya/api/algopy/algopy/#logged_assert) and
[`logged_err`](/puya/api/algopy/algopy/#logged_err). Before failing, they emit a log
entry in the [ARC-65](https://github.com/algorandfoundation/ARCs/blob/main/ARCs/arc-0065.md)
format `{prefix}:{error_code}` (or `{prefix}:{error_code}:{error_message}`), which
can be parsed and surfaced to the caller without needing
TEAL source maps.

```python
from algopy import UInt64, logged_assert, logged_err, subroutine

@subroutine
def withdraw(amount: UInt64, balance: UInt64) -> None:
    logged_assert(amount > 0, "AmtZero", "amount must be > 0")
    if amount > balance:
        logged_err("InsufficientFunds")
```

A failure above logs `ERR:AmtZero:amount must be > 0` (or `ERR:InsufficientFunds`)
before the transaction fails.

`logged_err(...)` is equivalent to `logged_assert(False, ...)`, to be used when the
failure is unconditional. Both functions accept the same arguments:

- **`error_code`** *(required)* — an alphanumeric identifier. Must not contain `:`.
- **`error_message`** *(optional)* — human-readable context appended after the code.
  Must not contain `:`.
- **`prefix`** *(optional)*, defaults to `"ERR"` (`"AER"` is reserved for future ARC specific error codes).

Because the prefix, code and message are embedded in the compiled program, keep
them short, as they increase bytecode size compared to a plain `assert` or `op.err`.

## Exception handling

The AVM doesn't provide error trapping semantics so it's not possible to implement `raise` and `catch`.

For more details see [Unsupported Python features](/puya/language-guide/unsupported-python-features/#raise-tryexceptfinally).
