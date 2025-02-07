# Data structures
In terms of data structures, Algorand Python currently provides support for 
[composite](https://en.wikipedia.org/wiki/Composite_data_type) data types and arrays.

In a restricted and costly computing environment such as a blockchain application, making the 
correct choice for data structures is crucial.

All ARC-4 data types are supported, and initially were the only choice of data structures in
Algorand Python 1.0, other than statically sized native Python tuples. However, ARC-4 encoding
is not an efficient encoding for mutations, additionally they were restricted in that they could
only contain other ARC-4 types.

As of Algorand Python 2.7, two new array types were introduced [`algopy.Array`](#algopy.Array), a mutable array type
that supports statically sized native and ARC-4 elements and [`algopy.ImmutableArray`](#algopy.ImmutableArray) that has
an immutable API and supports dynamically sized native and ARC-4 elements.

## Mutability vs Immutability
A value with an immutable type cannot be modified. Some examples are [`UInt64`](#algopy.UInt64), [`Bytes`](#algopy.Bytes), `tuple` and `typing.NamedTuple`.

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

## Algorand Python composite types

### `tuple`
This is a regular python tuple
* Immutable 
* Members can be of any type
* Most useful as an anonymous type
* Each member is stored on the stack

### `typing.NamedTuple`
* Immutable
* Members can be of any type
* Members are described by a field name and type
* Modified copies can be made using `._replace`
* Each member is stored on the stack

### `arc4.Tuple`
* Can only contain other ARC-4 types
* Can be immutable if all members are also immutable
* Requires [`.copy()`](#algopy.arc4.Tuple.copy) when mutable and creating additional references
* Encoded as a single ARC-4 value on the stack

### `arc4.Struct`
* Can only contain other ARC-4 types
* Members are described by a field name and type
* Can be immutable if using the `frozen` class option and all members are also immutable
* Requires [`.copy()`](#algopy.arc4.Struct.copy) when mutable and creating additional references
* Encoded as a single ARC-4 value on the stack

## Algorand Python array types

### `algopy.Array`
* Mutable, all references see modifications
* Only supports static size immutable types.
  Note: Supporting mutable elements would have the potential to quickly exhaust scratch slots in a 
  program so for this reason this type is limited to immutable elements only
* May use scratch slots to store the data
* Cannot be put in storage or used in ABI method signatures
* An immutable copy can be made for storage or returning from a contract by using the [`freeze`](#algopy.Array.freeze) method e.g.
```python
import algopy

class SomeContract(algopy.arc4.ARC4Contract):
    @algopy.arc4.abimethod()
    def get_array(self) -> algopy.ImmutableArray[algopy.UInt64]:
        arr = algopy.Array[algopy.UInt64]()
        # modify arr as required
        ...
    
        # return immutable copy
        return arr.freeze()
```

### `algopy.ImmutableArray`
* Immutable
* Modifications are done by reassigning a modified copy of the original array
* Supports all immutable types
* Most efficient with static sized immutable types
* Can be put in storage or used in ABI method signatures
* Can be used to extend an `algopy.Array` to do modifications e.g.
```python
import algopy

class SomeContract(algopy.arc4.ARC4Contract):

    @algopy.arc4.abimethod()
    def modify_array(self, imm_array: algopy.ImmutableArray[algopy.UInt64]) -> None:
        mutable_arr = algopy.Array[algopy.UInt64]()
        mutable_arr.extend(imm_array)
        ...
```


### `algopy.arc4.DynamicArray` / `algopy.arc4.StaticArray`
* Supports only ARC-4 elements
* Elements often require conversion to native types
* Efficient for reading
* Requires [`.copy()`](#algopy.arc4.DynamicArray) if making additional references to the array 

## Recommendations
* Prefer immutable structures such as `tuple` or `typing.NamedTuple` for aggregate types as these support all types and do not require `.copy()`
* If a function needs just a few values on a tuple it is more efficient to just pass those members rather than the whole tuple
* Prefer static sized types rather than dynamically sized types in arrays as they are more efficient in terms of op budgets
* Use `algopy.Array` when doing many mutations e.g. appending in a loop
* Use [`algopy.Array.freeze`](#algopy.Array.freeze) to convert an array to `algopy.ImmutableArray` for storage
* `algopy.ImmutableArray` can be used in storage and ABI methods, and will be viewed externally (i.e. in ARC-56 definitions) as the equivalent ARC-4 encoded type
* `algopy.ImmutableArray` can be converted to `algopy.Array` by extending a new `algopy.Array` with an `algopy.ImmutableArray`
