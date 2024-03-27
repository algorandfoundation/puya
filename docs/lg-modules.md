# Module level constructs

## Module constants

Module constants are compile-time constant, and can contain `bool`, `int`, `str` and `bytes` literals.

You can use fstrings in module constants.

Example:

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

## if/else based on compile time constants

## math etc, some strings ops

## type aliases
