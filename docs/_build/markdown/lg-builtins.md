# Python builtins

Some common python builtins have equivalent `algopy` versions, that use an [`UInt64`](api-algopy.md#algopy.UInt64) instead of a native `int`.

## len

The `len()` builtin is not supported. Instead, `algopy` types that have a length have a `.length` property of type [`UInt64`](api-algopy.md#algopy.UInt64). This is primarily
due to `len()` always returning `int` and the CPython implementation enforcing that it returns *exactly* `int`.

## range

The `range()` builtin has an equivalent [`algopy.urange`](api-algopy.md#algopy.urange). This behaves the same as the python builtin except that it returns
an iteration of [`UInt64`](api-algopy.md#algopy.UInt64) values instead of `int`.

## enumerate

The `enumerate()` builtin has an equivalent [`algopy.uenumerate`](api-algopy.md#algopy.uenumerate). This behaves the same as the python builtin except that it returns
an iteration of [`UInt64`](api-algopy.md#algopy.UInt64) index values and the corresponding item.

## reversed

The `reversed()` builtin is supported when iterating within a `for` loop and behaves the same as the python builtin.

## types

See [here](lg-types.md#python-built-in-types)
