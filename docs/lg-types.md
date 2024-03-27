# Types

Like in any programming language, types and data structures are a crucial programming construct.

Algorand Python lets you create variables in a number of contexts:

-   [Module constants](./lg-modules.md#module-constants) for compile-time constant values
-   Class variables to hold [global and local state](./lg-state.md)
-   [Local variables](#module-constants-and-local-variables) within a subroutine to hold intermediate results
-   [Subroutine parameters](./lg-structure.md#subroutines) to allow values to be passed around between calls

There three sets of datatypes available to assign variables as:

1. **AVM primitive (stack) types** - types that directly align to types that are [available to the Algorand Virtual Machine](https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#stack-types)
2. **ARC-4 types** - types that conform to the [ARC-4 spec](https://github.com/algorandfoundation/ARCs/blob/main/ARCs/arc-0004.md)
3. **Reference types** - types that represent reference types, e.g. accounts, assets, etc.

## AVM primitive types

The primitive types of the AVM, `uint64` and `bytes[]` are represented by `algopy.UInt64` and
`algopy.Bytes` types respectively. Additionally, there are some special types defined in Algorand Python:

-   `algopy.String` - A convenient wrapper over `bytes[]` allow for UTF-8 string representation
-   `algopy.BigUInt` - Allowing AVM supported wide-math (up to 512 bits)

### UInt64

`UInt64` is a type provided to represent unsigned 64-bit integers. This type corresponds to the `uint64` primitive type in the AVM. It can have various operators applied to it (all of them to another `UInt64 or an `int` literal`), including:

-   Equality: `==`, `!=`
-   Comparison: `<`, `<=`, `>`, `>=`
-   Boolean casting: Explicit (`bool(value)`) and implicit (e.g. appearing in control flow statement or subroutine calls) casting to a Boolean
    -   A UInt64 will evaluate to `False` if zero, and `True` otherwise per [Python semantics](https://docs.python.org/3/reference/datamodel.html#emulating-numeric-types)
-   Addition and subtraction: `+`, `-`, `+=`, `-=`
-   Multiplication and division: `*`, `*=`, `//`, `//=`, `%`, `%=`
-   Power: `**`, `**=`
-   Bit shifting: `<<`, `<<=`, `>>`, `>>=`
-   Binary: `&`, `&=`, `^`, `^=`, `|`, `|=`, `~`, `~=`

The behaviour of all of these operations matches the behaviour of the same operation on native Python `int`s.

Here's some examples of how to use `UInt64`:

```python
num = UInt64(100)
num2 = num + 200 // 3
num3 = UInt64(0b11111110)
num4 = UInt64(0x5a)
assert num4 != num3
if (num2 < 300):
    num += 3
```

[See a full example](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/uint64.py).

### bool

### Bytes

`Bytes` is a type provided to represent byte arrays. This type corresponds to the `byte[]` primitive type in the AVM. It can have various operators and methods applied to it, including:

The Bytes type is a powerful tool for manipulating and storing binary data. It provides an interface for dealing with byte sequences in a way that's familiar to users of Python's built-in bytes type, while providing an AVM explicit interface.

-   Equality: `==`, `!=`
-   Concatenation: `+`, `+=`
-   Repetition: `*`, `*=`
-   Indexing: `[]`
-   Slicing: `[:]`
-   Length: `len()`
-   Conversion to `UInt64`: `number.from_bytes()`
-   Conversion from `UInt64`: `bytes.from_uint64()`
-   Creation from base32, base64, hex encoded string: `Bytes.from_base32()`, `Bytes.from_base64()`, `Bytes.from_hex()`
-   Bitwise operations: `&`, `|`, `^`, `~`

The behavior of all these operations matches the behavior of the same operation on native Python `bytes`.

Here are some examples of how to use `Bytes`:

```python
byte_seq = Bytes(b'Hello, World!')
byte_seq2 = byte_seq + b' Nice to meet you.'
byte_seq3 = byte_seq * 2
index = byte_seq[0]
slice = byte_seq[0:5]
length = len(byte_seq)
num = UInt64.from_bytes(byte_seq)
byte_seq4 = Bytes.from_uint64(num)
base32_seq = Bytes.from_base32('74======')
base64_seq = Bytes.from_base64('RkY=')
hex_seq = Bytes.from_hex('FF')
bitwise_and = byte_seq & b'FF'
bitwise_or = byte_seq | b'0F'
bitwise_xor = byte_seq ^ b'0F'
bitwise_not = ~byte_seq
assert byte_seq4 != byte_seq3
```

[See a full example](https://github.com/algorandfoundation/puya/blob/main/test_cases/stubs/bytes.py).

### String

`String` is a type that represents a UTF-8 encoded string. This type does not store the array length prefix, making it more efficient for operations such as concatenation. However, due to the lack of UTF-8 support in the AVM, indexing and length operations are not currently supported.

The String type is a powerful tool for manipulating and storing UTF-8 string data. It provides an interface for dealing with strings in a way that's familiar to users of Python's built-in `str` type, while providing an AVM explicit interface.

`String` supports the following operations and methods:

-   Initialization: A `String` can be initialized with a Python `str` literal or a `str` variable declared at the module level.
-   Concatenation: `+`, `+=`
-   Boolean casting: Explicit (`bool(value)`) and implicit (e.g. appearing in control flow statement or subroutine calls) casting to a Boolean
-   Equality: `==`, `!=`
-   Contains: `in`
-   Startswith: `startswith()`
-   Endswith: `endswith()`
-   Join: `join()`
-   Getting underlying `Bytes`: `myString.bytes`

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

### BigUInt

`BigUInt` is a type that represents a variable length (max 512-bit) unsigned integer stored as `bytes[]` in the AVM.

The BigUInt type is a powerful tool for manipulating and storing large unsigned integers. It provides an interface for dealing with big integers in a way that's a subset of what users of Python's built-in int type would be familiar with and allowing for AVM supported wide math operations.

`BigUInt` supports the following operations and methods:

-   Initialization: A `BigUInt` can be initialized with a `UInt64`, a Python `int` literal or an `int` variable declared at the module level.
-   Equality: `==`, `!=`
-   Comparison: `<=`, `<`, `>=`, `>`
-   Addition: `+`, `+=`
-   Subtraction: `-`, `-=`
-   Multiplication: `*`, `*=`
-   Floor Division: `//`, `//=`
-   Modulo: `%`, `%=`
-   Bitwise operations: `&`, `^`, `|`
-   Getting underlying `Bytes`: `myBigUint.bytes`

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

## Python built-in types

TODO: limited scope, link to modules, also explain use in constructors for algopy types,
special handling of unions in other algopy code (e.g. algopy.op), but can't use type unions in
user subroutines etc

## Reference types

### Account

### Asset

### Application

## None
not supported as a value, only as an indicator of "void" returning function

## tuples

## TemplateVar

## ARC-4 types

ARC-4 data types are a first class concept in Algorand Python. They can be passed into ARC-4 methods (which will translate to the relevant ARC-4 method signature), passed into subroutines, or instantiated into local variables. A limited set of operations are exposed on some ARC-4 types, but often it may make sense to convert the ARC-4 value to a native AVM type, in which case you can use the `native` property to retrieve the value. Most of the ARC-4 types also allow for mutation e.g. you can edit values in arrays by index.

Please see the [reference documentation](./api-algopy.arc4.md) for the different classes that can be used to represent ARC-4 values or the [ARC-4 documentation](./lg-arc4.md) for more information.
