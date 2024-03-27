# Python builtins

Some common python builtins have equivalent `algopy` versions, that use an [`UInt64`](#algopy.UInt64) instead of a native `int`.

## len

The `len()` builtin is not supported, instead `algopy` types that have a length have a `.length` property of type [`UInt64`](#algopy.UInt64). This is primarily
due to `len()` always returning `int` and the CPython implementation enforcing that it returns _exactly_ `int`.

## range

The `range()` builtin has an equivalent [`algopy.urange`](#algopy.urange) this behaves the same as the python builtin except that it returns
an iteration of [`UInt64`](#algopy.UInt64) values instead of `int`.

## enumerate

The `enumerate()` builtin has an equivalent [`algopy.uenumerate`](#algopy.uenumerate) this behaves the same as the python builtin except that it returns
an iteration of [`UInt64`](#algopy.UInt64) index values and the corresponding item.

## reversed

The `reversed()` builtin is supported when iterating within a `for` loop and behaves the same as the python builtin.

## types

See [here](./lg-types.md#python-built-in-types)
