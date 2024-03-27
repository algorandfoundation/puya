# Error handling and assertions

In Algorand Python, error handling and assertions play a crucial role in ensuring the correctness and robustness of smart contracts.

## Assertions

Assertions allow you to immediately fail a smart contract if a [Boolean statement or value](./lg-types.md#bool) evaluates to `False`. If an assertion fails, it immediately stops the execution of the contract and marks the call as a failure.

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
the [`op.err()`](#algopy.op.err) operation. This operation causes the TEAL program to immediately 
and unconditionally fail.

Alternatively [`op.exit(0)`](#algopy.op.exit) will achieve the same result. A non-zero value will
do the opposite and immediately succeed.

## Exception handling

The AVM doesn't provide error trapping semantics so it's not possible to implement `raise` and `catch`.

For more details see [Unsupported Python features](lg-unsupported-python-features.md#raise-tryexceptfinally).
