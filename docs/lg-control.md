# Control flow structures

Control flow in Algorand Python is similar to standard Python control flow, with support for if statements, while loops, for loops, and match statements.

## If statements

If statements work the same as Python. The conditions must be an expression that evaluates to bool, which can include a [String or Uint64](./lg-types.md) among others.

```python
if condition:
    # block of code to execute if condition is True
elif condition2:
    # block of code to execute if condition is False and condition2 is True
else:
    # block of code to execute if condition and condition2 are both False
```

[See full example](https://github.com/algorandfoundation/puya/blob/main/test_cases/simplish/contract.py).

## Ternary conditions

Ternary conditions work the same as Python. The condition must be an expression that evaluates to bool, which can include a [String or Uint64](./lg-types.md) among others.

```python
value1 = UInt64(5)
value2 = String(">6") if value1 > 6 else String("<=6")
```

## While loops

While loops work the same as Python. The condition must be an expression that evaluates to bool, which can include a [String or Uint64](./lg-types.md) among others.

You can use `break` and `continue`.

```python
while condition:
    # block of code to execute if condition is True
```

Note: we don't currently have support for while-else statements.

[See full example](https://github.com/algorandfoundation/puya/blob/main/test_cases/unssa/contract.py#L32-L83).

## For Loops

For loops are used to iterate over sequences, ranges and [ARC-4 arrays](./lg-arc4.md). They work the same as Python.

Algorand Python provides functions like `uenumerate` and `urange` to facilitate creating sequences and ranges; in-built Python `reversed` method works with these.

-   `uenumerate` is similar to Python's built-in enumerate function, but for UInt64 numbers; it allows you to loop over a sequence and have an automatic counter.
-   `urange` is a function that generates a sequence of Uint64 numbers, which you can iterate over.
-   `reversed` returns a reversed iterator of a sequence.

Here is an example of how you can use these functions in a contract:

```python
test_array = arc4.StaticArray(arc4.UInt8(), arc4.UInt8(), arc4.UInt8(), arc4.UInt8())

# urange: reversed items, forward index

for index, item in uenumerate(reversed(urange(4))):
    test_array[index] = arc4.UInt8(item)

assert test_array.bytes == Bytes.from_hex("03020100")
```

Note: we don't currently have support for for-else statements.

[See full](https://github.com/algorandfoundation/puya/blob/main/test_cases/reversed_iteration/contract.py) [examples](https://github.com/algorandfoundation/puya/blob/main/test_cases/nested_loops/contract.py).

## Match Statements

Match statements work the same as Python and work for [...]

```python
match value:
    case pattern1:
        # block of code to execute if pattern1 matches
    case pattern2:
        # block of code to execute if pattern2 matches
    case _:
        # Fallback
```

Note: Captures and patterns are not supported. Currently, there is only support for basic case/switch functionality; pattern matching and guard clauses are not currently supported.

[See full example](https://github.com/algorandfoundation/puya/blob/main/test_cases/match/contract.py).
