# Types

Algorand Python exposes a number of types that provide a statically typed representation of the behaviour that is possible on the Algorand Virtual Machine.

```{contents} Types
:local:
:depth: 3
:class: this-will-duplicate-information-and-it-is-still-useful-here
```

## AVM types

The most basic [types on the AVM](https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#stack-types)
are `uint64` and `bytes[]`, representing unsigned 64-bit integers and byte arrays respectively.
These are represented by [`UInt64`](./#uint64) and [`Bytes`](./#bytes) in Algorand Python.

There are further "bounded" types supported by the AVM, which are backed by these two simple primitives.
For example, `bigint` represents a variably sized (up to 512-bits), unsigned integer, but is actually
backed by a `bytes[]`. This is represented by [`BigUInt`](./#biguint) in Algorand Python.

### UInt64

[`algopy.UInt64`](#algopy.UInt64) represents the underlying AVM `uint64` type.

It supports all the same operators as `int`, except for `/`, you must use `//` for truncating
division instead.

```python
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
# derived from that or wrap int literals
num2 = num + 200 // 3
```

[Further examples available here](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/uint64.py).

### Bytes

[`algopy.Bytes`](#algopy.Bytes) represents the underlying AVM `bytes[]` type. It is intended
to represent binary data, for UTF-8 it might be preferable to use [String](#string).

```python
# you can instantiate with a bytes literal
data = algopy.Bytes(b"abc")
# no arguments defaults to an empty value
empty = algopy.Bytes()
# empty is False, non-empty is True
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

### String

[`String`](#algopy.String) is a special Algorand Python type that represents a UTF8 encoded string.
It's backed by `Bytes`, which can be accessed through the `.bytes`.

It works similarly to `Bytes`, except that it works with `str` literals rather than `bytes`
literals. Additionally, due to a lack of AVM support for unicode data, indexing and length
operations are not currently supported (simply getting the length of a UTF8 string is an `O(N)`
operation, which would be quite costly in a smart contract). If you are happy using the length as
the number of bytes, then you can call `.bytes.length`.

```python
# you can instantiate with a string literal
data = algopy.String("abc")
# no arguments defaults to an empty value
empty = algopy.String()
# empty is False, non-empty is True
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

### BigUInt

[`algopy.BigUInt`](#algopy.BigUInt) represents a variable length (max 512-bit) unsigned integer stored
as `bytes[]` in the AVM.

It supports all the same operators as `int`, except for power (`**`), left and right shift (`<<`
and `>>`) and `/` (as with `UInt64`, you must use `//` for truncating division instead).

Note that the op code costs for `bigint` math are an order of magnitude higher than those for
`uint64` math. If you just need to handle overflow, take a look at the wide ops such as `addw`,
`mulw`, etc - all of which are exposed through the [`algopy.op`](#algopy.op) module.

Another contrast between `bigint` and `uint64` math is that `bigint` math ops don't immediately
error on overflow - if the result exceeds 512-bits, then you can still access the value via
`.bytes`, but any further math operations will fail.

```python
# you can instantiate with an integer literal
num = algopy.BigUInt(1)
# no arguments default to the zero value
zero = algopy.BigUInt()
# zero is False, any other value is True
assert not zero
assert num
# Like Python's `int`, `BigUInt` is immutable, so augmented assignment operators return new values
one = num
num += 1
assert one == 1
assert num == UInt64(2)
# note that once you have a variable of type BigUInt, you don't need to type any variables
# derived from that or wrap int literals
num2 = num + 200 // 3
```

[Further examples available here](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/biguint.py).

### bool

The semantics of the AVM `bool` bounded type exactly match the semantics of Python's built-in `bool` type
and thus Algorand Python uses the in-built `bool` type from Python.

Per the behaviour in normal Python, Algorand Python automatically converts various types to `bool` when they
appear in statements that expect a `bool` e.g. `if`/`while`/`assert` statements, appear in Boolean expressions
(e.g. next to `and` or `or` keywords) or are explicitly casted to a bool.

The semantics of `not`, `and` and `or` are special [per how these keywords work in Python](https://docs.python.org/3/reference/expressions.html#boolean-operations)
(e.g. short circuiting).

```python
a = UInt64(1)
b = UInt64(2)

c = a or b
d = b and a

e = self.expensive_op(UInt64(0)) or self.side_effecting_op(UInt64(1))
f = self.expensive_op(UInt64(3)) or self.side_effecting_op(UInt64(42))

g = self.side_effecting_op(UInt64(0)) and self.expensive_op(UInt64(42))
h = self.side_effecting_op(UInt64(2)) and self.expensive_op(UInt64(3))

i = a if b < c else d + e
if a:
    log("a is True")
```

[Further examples available here](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/uint64.py).

### Account

[`Account`](#algopy.Account) represents a logical Account, backed by a `bytes[32]` representing the
bytes of the public key (without the checksum). It has various account related methods that can be called from the type.

Also see [`algopy.arc4.Address`](#algopy.arc4.Address) if needing to represent the address as a distinct type.


### Asset

[`Asset`](#algopy.Asset) represents a logical Asset, backed by a `uint64` ID.
It has various asset related methods that can be called from the type.

### Application

[`Application`](#algopy.Application) represents a logical Application, backed by a `uint64` ID.
It has various application related methods that can be called from the type.

## Python built-in types

Unfortunately, the [AVM types](#avm-types) don't map to standard Python primitives. For instance,
in Python, an `int` is unsigned, and effectively unbounded. A `bytes` similarly is limited only by
the memory available, whereas an AVM `bytes[]` has a maximum length of 4096. In order to both maintain
semantic compatibility and allow for a framework implementation in plain Python that will fail under the
same conditions as when deployed to the AVM, support for Python primitives is limited.

In saying that, there are many places where built-in Python types can be used and over time the places these types can be used are expected to increase.

### bool

[Per above](#bool) Algorand Python has full support for `bool`.

### tuple

Python tuples are supported as arguments to subroutines, local variables, return types.

### typing.NamedTuple

Python named tuples are also supported using [`typing.NamedTuple`](https://docs.python.org/3/library/typing.html#typing.NamedTuple).

```{note}
Default field values and subclassing a NamedTuple are not supported
```

```python
import typing

import algopy


class Pair(typing.NamedTuple):
    foo: algopy.Bytes
    bar: algopy.Bytes
```

### None

`None` is not supported as a value, but is supported as a type annotation to indicate a function or subroutine
returns no value.

### int, str, bytes, float

The `int`, `str` and `bytes` built-in types are currently only supported as [module-level constants](./lg-modules.md) or literals.

They can be passed as arguments to various Algorand Python methods that support them or
when interacting with certain [AVM types](#avm-types) e.g. adding a number to a `UInt64`.

`float` is not supported.

## Template variables

Template variables can be used to represent a placeholder for a deploy-time provided
value. This can be declared using the `TemplateVar[TYPE]` type where `TYPE` is the
Algorand Python type that it will be interpreted as.

```python
from algopy import BigUInt, Bytes, TemplateVar, UInt64, arc4
from algopy.arc4 import UInt512


class TemplateVariablesContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def get_bytes(self) -> Bytes:
        return TemplateVar[Bytes]("SOME_BYTES")

    @arc4.abimethod()
    def get_big_uint(self) -> UInt512:
        x = TemplateVar[BigUInt]("SOME_BIG_UINT")
        return UInt512(x)

    @arc4.baremethod(allow_actions=["UpdateApplication"])
    def on_update(self) -> None:
        assert TemplateVar[bool]("UPDATABLE")

    @arc4.baremethod(allow_actions=["DeleteApplication"])
    def on_delete(self) -> None:
        assert TemplateVar[UInt64]("DELETABLE")
```

The resulting TEAL code that PuyaPy emits has placeholders with `TMPL_{template variable name}`
that expects either an integer value or an encoded bytes value. This behaviour exactly
matches what
[AlgoKit Utils expects](https://github.com/algorandfoundation/algokit-utils-ts/blob/main/docs/capabilities/app-deploy.md#compilation-and-template-substitution).

For more information look at the API reference for [`TemplateVar`](./api-algopy.md#algopy.TemplateVar).

## ARC-4 types

ARC-4 data types are a first class concept in Algorand Python. They can be passed into ARC-4
methods (which will translate to the relevant ARC-4 method signature), passed into subroutines, or
instantiated into local variables. A limited set of operations are exposed on some ARC-4 types, but
often it may make sense to convert the ARC-4 value to a native AVM type, in which case you can use
the `native` property to retrieve the value. Most of the ARC-4 types also allow for mutation e.g.
you can edit values in arrays by index.

Please see the [reference documentation](./api-algopy.arc4.md) for the different classes that can
be used to represent ARC-4 values or the [ARC-4 documentation](./lg-arc4.md) for more information
about ARC-4.
