# Data structures

In terms of data structures, Algorand Python currently provides support for
[composite](https://en.wikipedia.org/wiki/Composite_data_type) data types and arrays.

In a restricted and costly computing environment such as a blockchain application, making the
correct choice for data structures is crucial.

All ARC-4 data types are supported, and initially were the only choice of data structures in
Algorand Python 1.0, other than statically sized native Python tuples. However, ARC-4 encoding
is not an efficient encoding for mutations, additionally they were restricted in that they could
only contain other ARC-4 types.

As of Algorand Python 2.7, two new array types were introduced [`algopy.Array`](api-algopy.md#algopy.Array), a mutable array type
that supports statically sized native and ARC-4 elements and [`algopy.ImmutableArray`](api-algopy.md#algopy.ImmutableArray) that has
an immutable API and supports dynamically sized native and ARC-4 elements.

## Mutability vs Immutability

A value with an immutable type cannot be modified. Some examples are [`UInt64`](api-algopy.md#algopy.UInt64), [`Bytes`](api-algopy.md#algopy.Bytes), `tuple` and `typing.NamedTuple`.

Aggregate immutable types such as `tuple` or `ImmutableArray` provide a way to produce modified values,
this is done by returning a copy of the original value with the specified changes applied
e.g.

```python
import typing
import algopy

# update a named tuple with _replace
class MyTuple(typing.NamedTuple):
    foo: algopy.UInt64
    bar: algopy.String

tup1 = MyTuple(foo=algopy.UInt64(12), bar=algopy.String("Hello"))
# this does not modify tup1
tup2 = tup1._replace(foo=algopy.UInt64(34))

assert tup1.foo != tup2.foo

# update immutable array by appending and reassigning
arr = algopy.ImmutableArray[MyTuple]()
arr = arr.append(tup1)
arr = arr.append(tup2)
```

Mutable types allow direct modification of a value and all references to this value are able to observe the change
e.g.

```python
import algopy

# both my_arr and my_arr2 both point to the same array
my_arr = algopy.Array[algopy.UInt64]()
my_arr2 = my_arr

my_arr.append(algopy.UInt64(12))
assert my_arr.length == 1
assert my_arr2.length == 1

my_arr2.append(algopy.UInt64(34))
assert my_arr2.length == 2
assert my_arr.length == 2
```

## Static size vs Dynamic size

A static sized type is a type where its total size in memory is determinable at compile time, for example
`UInt64` is always 8 bytes of memory. Aggregate types such as `tuple`, `typing.NamedTuple`,
`arc4.Struct` and `arc4.Tuple` are static size if all their members are also static size
e.g.
`tuple[UInt64, UInt64]` is static size as it contains two static sized members.

Any type where its size is not statically defined is dynamically sized e.g. `Bytes`,
`String`, `tuple[UInt64, String]` and `Array[UInt64]` are all dynamically sized.

## Size constraints

All `bytes` on the AVM stack cannot exceed 4096 bytes in length, this means all arrays and structs cannot exceed this size.
Boxes are an exception to this, the contents of a box can be up to 32k bytes.
However loading this entire box into a variable is not possible as it would exceed the AVM limit of 4096 bytes.
However Puya will support reading and writing parts of a box

```python
import typing
from algopy import Box, FixedArray, Struct, UInt64, arc4, size_of



class BigStruct(Struct):
    count: UInt64 # 8 bytes
    large_array: FixedArray[UInt64, typing.Literal[512]] # 4096 bytes

class Contract(arc4.ARC4Contract):

    def __init__(self) -> None:
        self.box = Box(BigStruct)
        self.box.create()

    @arc4.abimethod()
    def read_box_fails(self) -> UInt64:
        assert size_of(BigStruct) == 4104
        big_struct = self.box.value # this fails to compile because size_of(BigStruct)
        assert big_struct.count > 0, ""

```

## Algorand Python composite types

### `tuple`

This is a regular python tuple

- Immutable
- Members can be of any type
- Most useful as an anonymous type
- Each member is stored on the stack, within a function this makes them quite efficient.
  However when passing to another function they can require a lot of stack manipulations to order all the members
  correctly on the stack

### `typing.NamedTuple`

- Immutable
- Members can be of any type
- Members are described by a field name and type
- Modified copies can be made using `._replace`
- Each member is stored on the stack, within a function this makes them quite efficient.
  However when passing to another function they can require a lot of stack manipulations to order all the members
  correctly on the stack

### `Struct`

- Can contain any type except transactions
- Members are described by a field name and type
- Can be immutable if using the `frozen` class option and all members are also immutable
- Requires [`.copy()`](api-algopy.md#algopy.Struct.copy) when mutable and creating additional references
- Encoded as a single ARC-4 value on the stack

### `arc4.Tuple`

- Can only contain other ARC-4 types
- Can be immutable if all members are also immutable
- Requires [`.copy()`](api-algopy.arc4.md#algopy.arc4.Tuple.copy) when mutable and creating additional references
- Encoded as a single ARC-4 value on the stack

### `arc4.Struct`

- Can only contain other ARC-4 types
- Members are described by a field name and type
- Can be immutable if using the `frozen` class option and all members are also immutable
- Requires [`.copy()`](api-algopy.arc4.md#algopy.arc4.Struct.copy) when mutable and creating additional references
- Encoded as a single ARC-4 value on the stack

## Algorand Python array types

### `algopy.FixedArray`

- Can contain any type except transactions
- Can only contain a fixed number of elements
- Most efficient array type
- Requires [`.copy()`](api-algopy.md#algopy.FixedArray.copy) if making additional references to the array or any mutable elements

### `algopy.Array`

- Can contain any type except transactions
- Dynamically sized, efficient for reading (when assembled off-chain). Inefficient to manipulate on-chain
- Requires [`.copy()`](api-algopy.md#algopy.Array.copy) if making additional references to the array or any mutable elements

### `algopy.ReferenceArray`

- Mutable, all references see modifications
- Only supports static size immutable types.
  Note: Supporting mutable elements would have the potential to quickly exhaust scratch slots in a
  program so for this reason this type is limited to immutable elements only
- May use scratch slots to store the data
- Cannot be put in storage or used in ABI method signatures
- An immutable copy can be made for storage or returning from a contract by using the [`freeze`](api-algopy.md#algopy.ReferenceArray.freeze) method e.g.

```python
import algopy

class SomeContract(algopy.arc4.ARC4Contract):
    @algopy.arc4.abimethod()
    def get_array(self) -> algopy.ImmutableArray[algopy.UInt64]:
        arr = algopy.ReferenceArray[algopy.UInt64]()
        # modify arr as required
        ...

        # return immutable copy
        return arr.freeze()
```

### `algopy.ImmutableArray`

- Immutable version of `algopy.Array`
- Modifications are done by reassigning a modified copy of the original array
- Can only contain immutable types
- Can be put in storage or used in ABI method signatures

### `algopy.arc4.DynamicArray` / `algopy.arc4.StaticArray`

- Only supports ARC-4 elements
- Elements often require conversion to native types, use `algopy.Array` / `algopy.FixedArray` to avoid explict conversions
- Dynamically sized types are efficient for reading, but not writing
- Requires [`.copy()`](api-algopy.arc4.md#algopy.arc4.DynamicArray) if making additional references to the array or mutable elements

## Tips

- Avoid using dynamically sized types as they are less efficient and can obfuscate constraints of the AVM (`algopy.Bytes`, `algopy.String`, `algopy.Array`, `algopy.arc4.DynamicArray`, `algopy.arc4.DynamicBytes` `algopy.arc4.String`)
- Prefer frozen structs where possible to avoid `.copy()` requirements
- If a function needs just a few values of a tuple it is more efficient to just pass those members rather than the whole tuple
- For passing composite values between functions there can be different trade-offs in terms of op budget and program size between a tuple or a struct, if this is a concern then test and confirm which suits your contract the best.
- All array types except `algopy.ReferenceArray` can be used in storage and ABI methods, and will be viewed externally (i.e. in ARC-56 definitions) as the equivalent ARC-4 encoded type
- Use [`algopy.ReferenceArray.freeze`](api-algopy.md#algopy.ReferenceArray.freeze) to convert the array to an `algopy.ImmutableArray` for storage
