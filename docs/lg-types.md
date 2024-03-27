# Types

## UInt64

[`algopy.UInt64`](#algopy.UInt64) represents the underlying AVM `uint64` type.

It supports all the same operators as `int`, except for `/`, you must use `//` for truncating
division instead.

```python3
# you can instantiate with an integer literal 
num = algopy.UInt64(1)
# no arguments default to the zero value
zero = algopy.UInt64()
# zero is False, any other value is True
assert not zero
assert num
# Like Python's `int`, `UInt64` is immutable, so augmented assignment operators return new values
one = num
num += 1
assert one == 1
assert num == 2
# note that once you have a variable of type UInt64, you don't need to type any variables
# derived from that
num2 = num + 200 // 3
```

[Further examples available here](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/uint64.py).

## Bytes

[`algopy.Bytes`](#algopy.Bytes) represents the underlying AVM `bytes[]` type. It is intended
to represent binary data, for UTF-8 it might be preferable to use [String](#string).

```python3
# you can instantiate with a bytes literal
data = algopy.Bytes(b"abc")
# no arguments defaults to an empty value
empty = algopy.Bytes()
# empty is False, non-empty is Ture
assert data
assert not empty
# Like Python's `bytes`, `Bytes` is immutable, augmented assignment operators return new values
abc = data
data += b"def"
assert abc == b"abc"
assert data == b"abcdef"
# indexing and slicing are supported, and both return a Bytes
assert abc[0] == b"a"
assert data[:3] == abc
# check if a bytes sequence occurs within another
assert abc in data
```
```{hint}
Indexing a `Bytes` returning a `Bytes` differs from the behaviour of Python's bytes type, which 
returns an `int`.
```
```python
# you can iterate 
for i in abc:
    ...
# construct from encoded values
base32_seq = algopy.Bytes.from_base32('74======')
base64_seq = algopy.Bytes.from_base64('RkY=')
hex_seq = algopy.Bytes.from_hex('FF')
# binary manipulations ^, &, |, and ~ are supported
data ^= ~((base32_seq & base64_seq) | hex_seq)
# access the length via the .length property
assert abc.length == 3
```
```{note}
See [Python builtins](lg-builtins.md#len---length) for an explanation of why `len()` isn't supported.
``` 
[See a full example](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/bytes.py).

## String

[`String`](#algopy.String) is a type that represents a UTF8 encoded string. It's backed by
`Bytes`, which can be access through the `.bytes`.

It works similarly to `Bytes`, except that it works with `str` literals rather than `bytes`
literals. Additionally, due to a lack of AVM support for unicode data, indexing and length
operations are not currently supported (simply getting the length of a UTF8 string is an `O(N)` 
operation, which would be quite costly in a smart contract).

```python3
# you can instantiate with a bytes literal
data = algopy.String("abc")
# no arguments defaults to an empty value
empty = algopy.String()
# empty is False, non-empty is Ture
assert data
assert not empty
# Like Python's `str`, `String` is immutable, augmented assignment operators return new values
abc = data
data += "def"
assert abc == "abc"
assert data == "abcdef"
# whilst indexing and slicing are not supported, the following tests are:
assert abc.startswith("ab")
assert abc.endswith("bc")
assert abc in data
# you can also join multiple Strings together with a seperator:
assert algopy.String(", ").join((abc, abc)) == "abc, abc"
# access the underlying bytes
assert abc.bytes == b"abc"
```

[See a full example](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/string.py).

## BigUInt

TODO: follow pattern from UInt64

## Account

[`Account`](#algopy.Account) represents a logical Account, backed by a `bytes[]` representing the
public key.

## Asset

[`Asset`](#algopy.Asset) represents a logical Asset, backed by a `uint64` ID.

## Application

[`Application`](#algopy.Application) represents a logical Application, backed by a `uint64` ID.

## Python built-in types

### bool

todo: note about `and`/`or` with disparate types, might not belong here though?

### tuple
supported as arguments, local variables, return types
nested _not_ supported

### None

`None` is not supported as a value, only as a type annotation to indicate a function returns no
value.

### int, str, bytes

Only as module level constants, or as arguments to compiler functionality.

## TemplateVar

## ARC-4 types

ARC-4 data types are a first class concept in Algorand Python. They can be passed into ARC-4
methods (which will translate to the relevant ARC-4 method signature), passed into subroutines, or
instantiated into local variables. A limited set of operations are exposed on some ARC-4 types, but
often it may make sense to convert the ARC-4 value to a native AVM type, in which case you can use
the `native` property to retrieve the value. Most of the ARC-4 types also allow for mutation e.g.
you can edit values in arrays by index.

Please see the [reference documentation](./api-algopy.arc4.md) for the different classes that can
be used to represent ARC-4 values or the [ARC-4 documentation](./lg-arc4.md) for more information.
