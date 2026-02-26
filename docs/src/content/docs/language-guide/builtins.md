---
title: Python Builtins
description: Supported Python builtin functions in Algorand Python
---

Some common python builtins have equivalent `algopy` versions, that use an [`UInt64`](/puya/api/algopy/algopy/#class-uint64) instead of a native `int`.

## len

The `len()` builtin is not supported. Instead, `algopy` types that have a length have a `.length` property of type [`UInt64`](/puya/api/algopy/algopy/#class-uint64). This is primarily
due to `len()` always returning `int` and the CPython implementation enforcing that it returns _exactly_ `int`.

## range

The `range()` builtin has an equivalent [`algopy.urange`](/puya/api/algopy/algopy/#class-urange). This behaves the same as the python builtin except that it returns
an iteration of [`UInt64`](/puya/api/algopy/algopy/#class-uint64) values instead of `int`.

## enumerate

The `enumerate()` builtin has an equivalent [`algopy.uenumerate`](/puya/api/algopy/algopy/#class-uenumerate). This behaves the same as the python builtin except that it returns
an iteration of [`UInt64`](/puya/api/algopy/algopy/#class-uint64) index values and the corresponding item.

## reversed

The `reversed()` builtin is supported when iterating within a `for` loop and behaves the same as the python builtin.

## types

See [here](/puya/language-guide/types/#python-built-in-types)