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

`String` is a type that represents a UTF-8 encoded string. This type does not store the array
length prefix, making it more efficient for operations such as concatenation. However, due to the
lack of UTF-8 support in the AVM, indexing and length operations are not currently supported.

The String type is a powerful tool for manipulating and storing UTF-8 string data. It provides an
interface for dealing with strings in a way that's familiar to users of Python's built-in `str`
type, while providing an AVM explicit interface.

`String` supports the following operations and methods:

- Initialization: A `String` can be initialized with a Python `str` literal or a `str` variable
  declared at the module level.
- Concatenation: `+`, `+=`
- Boolean casting: Explicit (`bool(value)`) and implicit (e.g. appearing in control flow statement
  or subroutine calls) casting to a Boolean
- Equality: `==`, `!=`
- Contains: `in`
- Startswith: `startswith()`
- Endswith: `endswith()`
- Join: `join()`
- Getting underlying `Bytes`: `myString.bytes`

Here are some examples of how to use `String`:

```python
string = String("Hello, World!")
string2 = string + " Nice to meet you."
string3 = string += " How are you?"
assert string2 != string3
if "Hello" in string2:
    op.log("Found greeting")
if string2.startswith("Hello"):
    op.log("Starts with greeting")
if string2.endswith("you."):
    op.log("Ends with you.")
joined_string = String(", ").join((String("Hello"), String("World")))
```

## BigUInt

`BigUInt` is a type that represents a variable length (max 512-bit) unsigned integer stored
as `bytes[]` in the AVM.

The BigUInt type is a powerful tool for manipulating and storing large unsigned integers. It
provides an interface for dealing with big integers in a way that's a subset of what users of
Python's built-in int type would be familiar with and allowing for AVM supported wide math
operations.

`BigUInt` supports the following operations and methods:

- Initialization: A `BigUInt` can be initialized with a `UInt64`, a Python `int` literal or
  an `int` variable declared at the module level.
- Equality: `==`, `!=`
- Comparison: `<=`, `<`, `>=`, `>`
- Addition: `+`, `+=`
- Subtraction: `-`, `-=`
- Multiplication: `*`, `*=`
- Floor Division: `//`, `//=`
- Modulo: `%`, `%=`
- Bitwise operations: `&`, `^`, `|`
- Getting underlying `Bytes`: `myBigUint.bytes`

Here are some examples of how to use `BigUInt`:

```python
big_num = BigUInt(100)
big_num2 = big_num + 200 // 3
big_num3 = BigUInt(0b11111110)
big_num4 = BigUInt(0x5a)
assert big_num4 != big_num3
if (big_num2 < 300):
    big_num += 3
bitwise_and = big_num & 0xFF
bitwise_or = big_num | 0x0F
bitwise_xor = big_num ^ 0x0F
```

## Account

## Asset

## Application

## Python built-in types

### bool

### tuple

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
