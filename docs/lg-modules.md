# Module level constructs

You can write compile-time constant code at a module level and then use them in place of [Python built-in literal types](./lg-types.md#python-built-in-types).

For a full example of what syntax is currently possible see the [test case example](https://github.com/algorandfoundation/puya/blob/main/test_cases/module_consts/contract.py).

## Module constants

Module constants are compile-time constant, and can contain `bool`, `int`, `str` and `bytes`.

You can use fstrings and other compile-time constant values in module constants too.

For example:

```python
from algopy import UInt64, subroutine

SCALE = 100000
SCALED_PI = 314159

@subroutine
def circle_area(radius: UInt64) -> UInt64:
    scaled_result = SCALED_PI * radius**2
    result = scaled_result // SCALE
    return result

@subroutine
def circle_area_100() -> UInt64:
    return circle_area(UInt64(100))
```

## If statements

You can use if statements with compile-time constants in module constants.

For example:

```python
FOO = 42

if FOO > 12:
    BAR = 123
else:
    BAR = 456
```

## Integer math

Module constants can also be defined using common integer expressions.

For example:

```python
SEVEN = 7
TEN = 7 + 3
FORTY_NINE = 7 ** 2
```

## Strings

Module `str` constants can use f-string formatting and other common string expressions.

For example:

```python
NAME = "There"
MY_FORMATTED_STRING = f"Hello {NAME}" # Hello There
PADDED = f"{123:05}" # "00123"
DUPLICATED = "5" * 3 # "555"
```

## Type aliases

You can create type aliases to make your contract terser and more expressive.

For example:

```python
import typing

from algopy import arc4
VoteIndexArray: typing.TypeAlias = arc4.DynamicArray[arc4.UInt8]

Row: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[3]]
Game: typing.TypeAlias = arc4.StaticArray[Row, typing.Literal[3]]
Move: typing.TypeAlias = tuple[arc4.UInt64, arc4.UInt64]

Bytes32: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[32]]
Proof: typing.TypeAlias = arc4.DynamicArray[Bytes32]
```
