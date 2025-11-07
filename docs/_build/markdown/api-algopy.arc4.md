# [`algopy.arc4`](#module-algopy.arc4)

## Module Contents

### Classes

| [`ARC4Client`](#algopy.arc4.ARC4Client)     | Used to provide typed method signatures for ARC-4 contracts                                                                                                        |
|---------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`ARC4Contract`](#algopy.arc4.ARC4Contract) | A contract that conforms to the ARC-4 ABI specification, functions decorated with<br/>`@abimethod` or `@baremethod` will form the public interface of the contract |
| [`Address`](#algopy.arc4.Address)           | An alias for an array containing 32 bytes representing an Algorand address                                                                                         |
| [`BigUFixedNxM`](#algopy.arc4.BigUFixedNxM) | An ARC-4 UFixed representing a decimal with the number of bits and precision specified.                                                                            |
| [`BigUIntN`](#algopy.arc4.BigUIntN)         | An ARC-4 UInt consisting of the number of bits specified.                                                                                                          |
| [`Bool`](#algopy.arc4.Bool)                 | An ARC-4 encoded bool                                                                                                                                              |
| [`Byte`](#algopy.arc4.Byte)                 | An ARC-4 alias for a UInt8                                                                                                                                         |
| [`DynamicArray`](#algopy.arc4.DynamicArray) | A dynamically sized ARC-4 Array of the specified type                                                                                                              |
| [`DynamicBytes`](#algopy.arc4.DynamicBytes) | A variable sized array of bytes                                                                                                                                    |
| [`StaticArray`](#algopy.arc4.StaticArray)   | A fixed length ARC-4 Array of the specified type and length                                                                                                        |
| [`String`](#algopy.arc4.String)             | An ARC-4 sequence of bytes containing a UTF8 string                                                                                                                |
| [`Struct`](#algopy.arc4.Struct)             | Base class for ARC-4 Struct types                                                                                                                                  |
| [`Tuple`](#algopy.arc4.Tuple)               | An ARC-4 ABI tuple, containing other ARC-4 ABI types                                                                                                               |
| [`UFixedNxM`](#algopy.arc4.UFixedNxM)       | An ARC-4 UFixed representing a decimal with the number of bits and precision specified.                                                                            |
| [`UIntN`](#algopy.arc4.UIntN)               | An ARC-4 UInt consisting of the number of bits specified.                                                                                                          |

### Functions

| [`abimethod`](#algopy.arc4.abimethod)           | Decorator that indicates a method is an ARC-4 ABI method.                                   |
|-------------------------------------------------|---------------------------------------------------------------------------------------------|
| [`arc4_create`](#algopy.arc4.arc4_create)       | Provides a typesafe and convenient way of creating an ARC4Contract via an inner transaction |
| [`arc4_signature`](#algopy.arc4.arc4_signature) | Returns the ARC-4 encoded method selector for the specified signature or abi method         |
| [`arc4_update`](#algopy.arc4.arc4_update)       | Provides a typesafe and convenient way of updating an ARC4Contract via an inner transaction |
| [`baremethod`](#algopy.arc4.baremethod)         | Decorator that indicates a method is an ARC-4 bare method.                                  |
| [`emit`](#algopy.arc4.emit)                     | Emit an ARC-28 event for the provided event signature or name, and provided args.           |

### Data

| [`UInt128`](#algopy.arc4.UInt128)   | An ARC-4 UInt128                                                          |
|-------------------------------------|---------------------------------------------------------------------------|
| [`UInt16`](#algopy.arc4.UInt16)     | An ARC-4 UInt16                                                           |
| [`UInt256`](#algopy.arc4.UInt256)   | An ARC-4 UInt256                                                          |
| [`UInt32`](#algopy.arc4.UInt32)     | An ARC-4 UInt32                                                           |
| [`UInt512`](#algopy.arc4.UInt512)   | An ARC-4 UInt512                                                          |
| [`UInt64`](#algopy.arc4.UInt64)     | An ARC-4 UInt64                                                           |
| [`UInt8`](#algopy.arc4.UInt8)       | An ARC-4 UInt8                                                            |
| [`abi_call`](#algopy.arc4.abi_call) | Provides a typesafe way of calling ARC-4 methods via an inner transaction |

### API

### *class* algopy.arc4.ARC4Client

Used to provide typed method signatures for ARC-4 contracts

### *class* algopy.arc4.ARC4Contract

A contract that conforms to the ARC-4 ABI specification, functions decorated with
`@abimethod` or `@baremethod` will form the public interface of the contract

The approval_program will be implemented by the compiler, and route application args
according to the ARC-4 ABI specification

The clear_state_program will by default return True, but can be overridden

#### *classmethod* \_\_init_subclass_\_(\*, name: [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., scratch_slots: [algopy.urange](api-algopy.md#algopy.urange) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](api-algopy.md#algopy.urange), ...] | [list](https://docs.python.org/3/library/stdtypes.html#list)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](api-algopy.md#algopy.urange)] = ..., state_totals: [algopy.StateTotals](api-algopy.md#algopy.StateTotals) = ..., avm_version: [int](https://docs.python.org/3/library/functions.html#int) = ...)

When declaring a Contract subclass, options and configuration are passed in
the base class list:

```python
class MyContract(algopy.Contract, name="CustomName"):
    ...
```

* **Parameters:**
  * **name** – 

    Will affect the output TEAL file name if there are multiple non-abstract contracts
    in the same file.

    If the contract is a subclass of algopy.ARC4Contract, `name` will also be used as the
    contract name in the ARC-32 application.json, instead of the class name.
  * **scratch_slots** – 

    Allows you to mark a slot ID or range of slot IDs as “off limits” to Puya.
    These slot ID(s) will never be written to or otherwise manipulating by the compiler itself.
    This is particularly useful in combination with `algopy.op.gload_bytes` / `algopy.op.gload_uint64`
    which lets a contract in a group transaction read from the scratch slots of another contract
    that occurs earlier in the transaction group.

    In the case of inheritance, scratch slots reserved become cumulative. It is not an error
    to have overlapping ranges or values either, so if a base class contract reserves slots
    0-5 inclusive and the derived contract reserves 5-10 inclusive, then within the derived
    contract all slots 0-10 will be marked as reserved.
  * **state_totals** – 

    Allows defining what values should be used for global and local uint and bytes storage
    values when creating a contract. Used when outputting ARC-32 application.json schemas.

    If let unspecified, the totals will be determined by the compiler based on state
    variables assigned to `self`.

    This setting is not inherited, and only applies to the exact `Contract` it is specified
    on. If a base class does specify this setting, and a derived class does not, a warning
    will be emitted for the derived class. To resolve this warning, `state_totals` must be
    specified. Note that it is valid to not provide any arguments to the `StateTotals`
    constructor, like so `state_totals=StateTotals()`, in which case all values will be
    automatically calculated.
  * **avm_version** – Determines which AVM version to use, this affects what operations are supported.
    Defaults to value provided supplied on command line (which defaults to current mainnet version)

#### approval_program() → [bool](https://docs.python.org/3/library/functions.html#bool)

Represents the program called for all transactions
where `OnCompletion` != `ClearState`

#### clear_state_program() → [algopy.UInt64](api-algopy.md#algopy.UInt64) | [bool](https://docs.python.org/3/library/functions.html#bool)

Represents the program called when `OnCompletion` == `ClearState`

### *class* algopy.arc4.Address(value: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [algopy.Bytes](api-algopy.md#algopy.Bytes) = ..., /)

An alias for an array containing 32 bytes representing an Algorand address

### Initialization

If `value` is a string, it should be a 58 character base32 string,
ie a base32 string-encoded 32 bytes public key + 4 bytes checksum.
If `value` is a Bytes, it’s length checked to be 32 bytes - to avoid this
check, use `Address.from_bytes(...)` instead.
Defaults to the zero-address.

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not equal to the zero address

#### \_\_eq_\_(other: [algopy.arc4.Address](#algopy.arc4.Address) | [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Address equality is determined by the address of another
`arc4.Address`, `Account` or `str`

#### \_\_getitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy.arc4._TArrayItem

Gets the item of the array at provided index

#### \_\_iter_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array

#### \_\_ne_\_(other: [algopy.arc4.Address](#algopy.arc4.Address) | [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Address equality is determined by the address of another
`arc4.Address`, `Account` or `str`

#### \_\_reversed_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### \_\_setitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy.arc4._TArrayItem) → algopy.arc4._TArrayItem

Sets the item of the array at specified index to provided value

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* length *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Returns the (compile-time) length of the array

#### *property* native *: [algopy.Account](api-algopy.md#algopy.Account)*

Return the Account representation of the address after ARC-4 decoding

#### to_native(element_type: [type](https://docs.python.org/3/library/functions.html#type)[algopy.arc4._TNativeArrayItem], /) → [algopy.FixedArray](api-algopy.md#algopy.FixedArray)[algopy.arc4._TNativeArrayItem, algopy.arc4._TArrayLength]

Convert to an `algopy.FixedArray` with the specified element type.

Only allowed if the element type is compatible with this arrays element type e.g.
arc4.UInt64 -> UInt64

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.BigUFixedNxM(value: [str](https://docs.python.org/3/library/stdtypes.html#str) = '0.0', /)

An ARC-4 UFixed representing a decimal with the number of bits and precision specified.

Max size: 512 bits

### Initialization

Construct an instance of UFixedNxM where value (v) is determined from the original
decimal value (d) by the formula v = round(d \* (10^M))

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not equal to zero

#### \_\_eq_\_(other: [Self](https://docs.python.org/3/library/typing.html#typing.Self)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Compare for equality, note both operands must be the exact same type

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.BigUIntN(value: [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

An ARC-4 UInt consisting of the number of bits specified.

Max size: 512 bits

### Initialization

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not equal to zero

#### \_\_eq_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self==value.

#### \_\_ge_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self>=value.

#### \_\_gt_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self>value.

#### \_\_le_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self<=value.

#### \_\_lt_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self<value.

#### \_\_ne_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self!=value.

#### as_biguint() → [algopy.BigUInt](api-algopy.md#algopy.BigUInt)

Return the BigUInt representation of the value after ARC-4 decoding

#### as_uint64() → [algopy.UInt64](api-algopy.md#algopy.UInt64)

Return the UInt64 representation of the value after ARC-4 decoding

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* native *: [algopy.BigUInt](api-algopy.md#algopy.BigUInt)*

Return the BigUInt representation of the value after ARC-4 decoding

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.Bool(value: [bool](https://docs.python.org/3/library/functions.html#bool) = False, /)

An ARC-4 encoded bool

### Initialization

#### \_\_eq_\_(other: [algopy.arc4.Bool](#algopy.arc4.Bool) | [bool](https://docs.python.org/3/library/functions.html#bool)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self==value.

#### \_\_ne_\_(other: [algopy.arc4.Bool](#algopy.arc4.Bool) | [bool](https://docs.python.org/3/library/functions.html#bool)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self!=value.

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* native *: [bool](https://docs.python.org/3/library/functions.html#bool)*

Return the bool representation of the value after ARC-4 decoding

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.Byte(value: [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

An ARC-4 alias for a UInt8

### Initialization

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not equal to zero

#### \_\_eq_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self==value.

#### \_\_ge_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self>=value.

#### \_\_gt_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self>value.

#### \_\_le_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self<=value.

#### \_\_lt_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self<value.

#### \_\_ne_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self!=value.

#### as_biguint() → [algopy.BigUInt](api-algopy.md#algopy.BigUInt)

Return the BigUInt representation of the value after ARC-4 decoding

#### as_uint64() → [algopy.UInt64](api-algopy.md#algopy.UInt64)

Return the UInt64 representation of the value after ARC-4 decoding

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* native *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Return the UInt64 representation of the value after ARC-4 decoding

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.DynamicArray(\*items: algopy.arc4._TArrayItem)

A dynamically sized ARC-4 Array of the specified type

### Initialization

Initializes a new array with items provided

#### \_\_add_\_(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy.arc4._TArrayItem]) → [algopy.arc4.DynamicArray](#algopy.arc4.DynamicArray)[algopy.arc4._TArrayItem]

Concat two arrays together, returning a new array

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not an empty array

#### \_\_getitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy.arc4._TArrayItem

Gets the item of the array at provided index

#### \_\_iter_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array

#### \_\_reversed_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### \_\_setitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy.arc4._TArrayItem) → algopy.arc4._TArrayItem

Sets the item of the array at specified index to provided value

#### append(item: algopy.arc4._TArrayItem, /) → [None](https://docs.python.org/3/library/constants.html#None)

Append an item to this array

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### extend(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy.arc4._TArrayItem], /) → [None](https://docs.python.org/3/library/constants.html#None)

Extend this array with the contents of another array

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* length *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Returns the current length of the array

#### pop() → algopy.arc4._TArrayItem

Remove and return the last item of this array

#### to_native(element_type: [type](https://docs.python.org/3/library/functions.html#type)[algopy.arc4._TNativeArrayItem], /) → [algopy.Array](api-algopy.md#algopy.Array)[algopy.arc4._TNativeArrayItem]

Convert to an `algopy.Array` with the specified element type.

Only allowed if the element type is compatible with this arrays element type e.g.
arc4.UInt64 -> UInt64

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.DynamicBytes

A variable sized array of bytes

#### \_\_add_\_(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy.arc4._TArrayItem]) → [algopy.arc4.DynamicArray](#algopy.arc4.DynamicArray)[algopy.arc4._TArrayItem]

Concat two arrays together, returning a new array

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not an empty array

#### \_\_getitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy.arc4._TArrayItem

Gets the item of the array at provided index

#### \_\_iter_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array

#### \_\_reversed_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### \_\_setitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy.arc4._TArrayItem) → algopy.arc4._TArrayItem

Sets the item of the array at specified index to provided value

#### append(item: algopy.arc4._TArrayItem, /) → [None](https://docs.python.org/3/library/constants.html#None)

Append an item to this array

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### extend(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy.arc4._TArrayItem], /) → [None](https://docs.python.org/3/library/constants.html#None)

Extend this array with the contents of another array

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* length *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Returns the current length of the array

#### *property* native *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Return the Bytes representation of the address after ARC-4 decoding

#### pop() → algopy.arc4._TArrayItem

Remove and return the last item of this array

#### to_native(element_type: [type](https://docs.python.org/3/library/functions.html#type)[algopy.arc4._TNativeArrayItem], /) → [algopy.Array](api-algopy.md#algopy.Array)[algopy.arc4._TNativeArrayItem]

Convert to an `algopy.Array` with the specified element type.

Only allowed if the element type is compatible with this arrays element type e.g.
arc4.UInt64 -> UInt64

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.StaticArray

A fixed length ARC-4 Array of the specified type and length

#### \_\_getitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy.arc4._TArrayItem

Gets the item of the array at provided index

#### \_\_iter_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array

#### \_\_reversed_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy.arc4._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### \_\_setitem_\_(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy.arc4._TArrayItem) → algopy.arc4._TArrayItem

Sets the item of the array at specified index to provided value

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* length *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Returns the (compile-time) length of the array

#### to_native(element_type: [type](https://docs.python.org/3/library/functions.html#type)[algopy.arc4._TNativeArrayItem], /) → [algopy.FixedArray](api-algopy.md#algopy.FixedArray)[algopy.arc4._TNativeArrayItem, algopy.arc4._TArrayLength]

Convert to an `algopy.FixedArray` with the specified element type.

Only allowed if the element type is compatible with this arrays element type e.g.
arc4.UInt64 -> UInt64

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.String(value: [algopy.String](api-algopy.md#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str) = '', /)

An ARC-4 sequence of bytes containing a UTF8 string

### Initialization

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if length is not zero

#### \_\_eq_\_(other: [algopy.arc4.String](#algopy.arc4.String) | [algopy.String](api-algopy.md#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self==value.

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* native *: [algopy.String](api-algopy.md#algopy.String)*

Return the String representation of the UTF8 string after ARC-4 decoding

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.Struct

Base class for ARC-4 Struct types

#### \_replace(\*\*kwargs: [Any](https://docs.python.org/3/library/typing.html#typing.Any)) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Return a new instance of the struct replacing specified fields with new values.

Note that any mutable fields must be explicitly copied to avoid aliasing.

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying bytes[]

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this struct

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes[] (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.Tuple(items: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[Unpack](https://docs.python.org/3/library/typing.html#typing.Unpack)[algopy.arc4._TTuple]], /)

An ARC-4 ABI tuple, containing other ARC-4 ABI types

### Initialization

Construct an ARC-4 tuple from a native Python tuple

#### \_\_add_\_()

Return self+value.

#### \_\_contains_\_()

Return bool(key in self).

#### \_\_delattr_\_()

Implement delattr(self, name).

#### \_\_dir_\_()

Default dir() implementation.

#### \_\_eq_\_()

Return self==value.

#### \_\_format_\_()

Default object formatter.

Return str(self) if format_spec is empty. Raise TypeError otherwise.

#### \_\_ge_\_()

Return self>=value.

#### \_\_getattribute_\_()

Return getattr(self, name).

#### \_\_getitem_\_()

Return self[key].

#### \_\_getstate_\_()

Helper for pickle.

#### \_\_gt_\_()

Return self>value.

#### \_\_hash_\_()

Return hash(self).

#### \_\_iter_\_()

Implement iter(self).

#### \_\_le_\_()

Return self<=value.

#### \_\_len_\_()

Return len(self).

#### \_\_lt_\_()

Return self<value.

#### \_\_mul_\_()

Return self\*value.

#### \_\_ne_\_()

Return self!=value.

#### \_\_new_\_()

Create and return a new object.  See help(type) for accurate signature.

#### \_\_reduce_\_()

Helper for pickle.

#### \_\_reduce_ex_\_()

Helper for pickle.

#### \_\_repr_\_()

Return repr(self).

#### \_\_rmul_\_()

Return value\*self.

#### \_\_setattr_\_()

Implement setattr(self, name, value).

#### \_\_sizeof_\_()

Size of object in memory, in bytes.

#### \_\_str_\_()

Return str(self).

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this tuple

#### count()

Return number of occurrences of value.

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### index()

Return first index of value.

Raises ValueError if the value is not present.

#### *property* native *: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[Unpack](https://docs.python.org/3/library/typing.html#typing.Unpack)[algopy.arc4._TTuple]]*

Convert to a native Python tuple - note that the elements of the tuple
should be considered to be copies of the original elements

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.arc4.UFixedNxM(value: [str](https://docs.python.org/3/library/stdtypes.html#str) = '0.0', /)

An ARC-4 UFixed representing a decimal with the number of bits and precision specified.

Max size: 64 bits

### Initialization

Construct an instance of UFixedNxM where value (v) is determined from the original
decimal value (d) by the formula v = round(d \* (10^M))

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not equal to zero

#### \_\_eq_\_(other: [Self](https://docs.python.org/3/library/typing.html#typing.Self)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Compare for equality, note both operands must be the exact same type

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### algopy.arc4.UInt128 *: [TypeAlias](https://docs.python.org/3/library/typing.html#typing.TypeAlias)*

None

An ARC-4 UInt128

### algopy.arc4.UInt16 *: [TypeAlias](https://docs.python.org/3/library/typing.html#typing.TypeAlias)*

None

An ARC-4 UInt16

### algopy.arc4.UInt256 *: [TypeAlias](https://docs.python.org/3/library/typing.html#typing.TypeAlias)*

None

An ARC-4 UInt256

### algopy.arc4.UInt32 *: [TypeAlias](https://docs.python.org/3/library/typing.html#typing.TypeAlias)*

None

An ARC-4 UInt32

### algopy.arc4.UInt512 *: [TypeAlias](https://docs.python.org/3/library/typing.html#typing.TypeAlias)*

None

An ARC-4 UInt512

### algopy.arc4.UInt64 *: [TypeAlias](https://docs.python.org/3/library/typing.html#typing.TypeAlias)*

None

An ARC-4 UInt64

### algopy.arc4.UInt8 *: [TypeAlias](https://docs.python.org/3/library/typing.html#typing.TypeAlias)*

None

An ARC-4 UInt8

### *class* algopy.arc4.UIntN(value: [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

An ARC-4 UInt consisting of the number of bits specified.

Max Size: 64 bits

### Initialization

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not equal to zero

#### \_\_eq_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self==value.

#### \_\_ge_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self>=value.

#### \_\_gt_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self>value.

#### \_\_le_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self<=value.

#### \_\_lt_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self<value.

#### \_\_ne_\_(other: [algopy.arc4.UIntN](#algopy.arc4.UIntN)[algopy.arc4._TBitSize] | [algopy.arc4.BigUIntN](#algopy.arc4.BigUIntN)[algopy.arc4._TBitSize] | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Return self!=value.

#### as_biguint() → [algopy.BigUInt](api-algopy.md#algopy.BigUInt)

Return the BigUInt representation of the value after ARC-4 decoding

#### as_uint64() → [algopy.UInt64](api-algopy.md#algopy.UInt64)

Return the UInt64 representation of the value after ARC-4 decoding

#### *property* bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### *classmethod* from_log(log: [algopy.Bytes](api-algopy.md#algopy.Bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Load an ABI type from application logs, checking for the ABI return prefix `0x151f7c75`

#### *property* native *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Return the UInt64 representation of the value after ARC-4 decoding

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### algopy.arc4.abi_call *: algopy.arc4._ABICallProtocolType*

Ellipsis

Provides a typesafe way of calling ARC-4 methods via an inner transaction

```python
def abi_call(
    self,
    method: Callable[..., _TABIResult_co] | str,
    /,
    *args: object,
    app_id: algopy.Application | algopy.UInt64 | int = ...,
    on_completion: algopy.OnCompleteAction = ...,
    approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
    clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...] = ...,
    global_num_uint: UInt64 | int = ...,
    global_num_bytes: UInt64 | int = ...,
    local_num_uint: UInt64 | int = ...,
    local_num_bytes: UInt64 | int = ...,
    extra_program_pages: UInt64 | int = ...,
    fee: algopy.UInt64 | int = 0,
    sender: algopy.Account | str = ...,
    note: algopy.Bytes | algopy.String | bytes | str = ...,
    rekey_to: algopy.Account | str = ...,
) -> tuple[_TABIResult_co, algopy.itxn.ApplicationCallInnerTransaction]: ...
```

PARAMETERS:

**method:** The name, method selector or Algorand Python method to call<br />
\\\\
**app_id:** Application to call, if 0 or not specified will create a new application<br />
\\\\
**on_completion:** OnCompleteAction value for the transaction. If not specified will be inferred from Algorand Python method where possible<br />
\\\\
**approval_program:** When creating or updating an application, the approval program<br />
\\\\
**clear_state_program:** When creating or updating an application, the clear state program<br />
\\\\
**global_num_uint:** When creating an application the number of global uints<br />
\\\\
**global_num_bytes:** When creating an application the number of global bytes<br />
\\\\
**local_num_uint:** When creating an application the number of local uints<br />
\\\\
**local_num_bytes:** When creating an application the number of local bytes<br />
\\\\
**extra_program_pages:** When creating an application the The number of extra program pages<br />
\\\\
**fee:** The fee to pay for the transaction, defaults to 0<br />
\\\\
**sender:** The sender address for the transaction<br />
\\\\
**note:** Note to include with the transaction<br />
\\\\
**rekey_to:** Account to rekey to

RETURNS:<br />
\\\\
If `method` references an Algorand Contract / Client or the function is indexed with a return type,
then the result is a tuple containing the ABI result and the inner transaction of the call.

If no return type is specified, or the method does not have a return value then the result
is the inner transaction of the call.

Examples:

```default
# can reference another algopy contract method
result, txn = abi_call(HelloWorldContract.hello, arc4.String("World"), app=...)
assert result == "Hello, World"

# can reference a method selector
result, txn = abi_call[arc4.String]("hello(string)string", arc4.String("Algo"), app=...)
assert result == "Hello, Algo"

# can reference a method name, the method selector is inferred from arguments and return type
result, txn = abi_call[arc4.String]("hello", "There", app=...)
assert result == "Hello, There"

# calling a method without a return value
txn = abi_call(HelloWorldContract.no_return, arc4.String("World"), app=...)
```

### algopy.arc4.abimethod(\*, name: [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., create: [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)[allow, require, disallow] = 'disallow', allow_actions: [collections.abc.Sequence](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction) | [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)[NoOp, OptIn, CloseOut, UpdateApplication, DeleteApplication]] = ('NoOp',), resource_encoding: [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)[index, value] = ..., readonly: [bool](https://docs.python.org/3/library/functions.html#bool) = False, default_args: [collections.abc.Mapping](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[str](https://docs.python.org/3/library/stdtypes.html#str), [str](https://docs.python.org/3/library/stdtypes.html#str) | algopy.arc4._ReadOnlyNoArgsMethod | [object](https://docs.python.org/3/library/functions.html#object)] = ..., validate_encoding: [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)[unsafe_disabled, args] = ...) → [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[algopy.arc4._P, algopy.arc4._R]], [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[algopy.arc4._P, algopy.arc4._R]]

Decorator that indicates a method is an ARC-4 ABI method.

* **Parameters:**
  * **name** – Name component of the ABI method selector. Defaults to using the function name.
  * **create** – Controls the validation of the Application ID. “require” means it must be zero,
    “disallow” requires it must be non-zero, and “allow” disables the validation.
  * **allow_actions** – A sequence of allowed On-Completion Actions to validate against.
  * **resource_encoding** – If “index”, then resource types (Application, Asset, Account)
    should be passed as an index into their appropriate foreign array.
    The default option “value”, as of PuyaPy 5.0, is for these values to be
    passed directly.
    This can be overridden at the compiler level with the
    “resource_encoding” CLI flag.
    This option will be reflected in the method signature.
  * **readonly** – If True, then this method can be used via dry-run / simulate.
  * **default_args** – Default argument sources for clients to use. For dynamic defaults, this can
    be the name of, or reference to a method member, or the name of a storage
    member. For static defaults, this can be any expression which evaluates to
    a compile time constant of the exact same type as the parameter.
  * **validate_encoding** – Controls validation behaviour for this method.
    If “args”, then ABI arguments are validated automatically to ensure
    they are encoded correctly.
    If “unsafe_disabled”, then no automatic validation occurs. Arguments
    can instead be validated using the .validate() method.
    The default behaviour of this option can be controlled with the
    –validate-abi-args CLI flag.

### algopy.arc4.arc4_create(method: [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[algopy.arc4._P, algopy.arc4._TABIResult_co], /, \*args: [object](https://docs.python.org/3/library/functions.html#object), compiled: [algopy.CompiledContract](api-algopy.md#algopy.CompiledContract) = ..., on_completion: [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., note: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[algopy.arc4._TABIResult_co, [algopy.itxn.ApplicationCallInnerTransaction](api-algopy.itxn.md#algopy.itxn.ApplicationCallInnerTransaction)]

Provides a typesafe and convenient way of creating an ARC4Contract via an inner transaction

* **Parameters:**
  * **method** – An ARC-4 create method (ABI or bare), or an ARC4Contract with a single create method
  * **args** – ABI args for chosen method
  * **compiled** – If supplied will be used to specify transaction parameters required for creation,
    can be omitted if template variables are not used
  * **on_completion** – OnCompleteAction value for the transaction
    If not specified will be inferred from Algorand Python method where possible
  * **fee** – The fee to pay for the transaction, defaults to 0
  * **sender** – The sender address for the transaction
  * **note** – Note to include with the transaction
  * **rekey_to** – Account to rekey to

### algopy.arc4.arc4_signature(signature: [str](https://docs.python.org/3/library/stdtypes.html#str) | [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[algopy.arc4._P, algopy.arc4._R], /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Returns the ARC-4 encoded method selector for the specified signature or abi method

### algopy.arc4.arc4_update(method: [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[algopy.arc4._P, algopy.arc4._TABIResult_co], /, \*args: [object](https://docs.python.org/3/library/functions.html#object), app_id: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), compiled: [algopy.CompiledContract](api-algopy.md#algopy.CompiledContract) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., note: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., reject_version: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ...) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[algopy.arc4._TABIResult_co, [algopy.itxn.ApplicationCallInnerTransaction](api-algopy.itxn.md#algopy.itxn.ApplicationCallInnerTransaction)]

Provides a typesafe and convenient way of updating an ARC4Contract via an inner transaction

* **Parameters:**
  * **method** – An ARC-4 update method (ABI or bare), or an ARC4Contract with a single update method
  * **args** – ABI args for chosen method
  * **app_id** – Application to update
  * **compiled** – If supplied will be used to specify transaction parameters required for updating,
    can be omitted if template variables are not used
  * **fee** – The fee to pay for the transaction, defaults to 0
  * **sender** – The sender address for the transaction
  * **note** – Note to include with the transaction
  * **rekey_to** – Account to rekey to

### algopy.arc4.baremethod(\*, create: [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)[allow, require, disallow] = 'disallow', allow_actions: [collections.abc.Sequence](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction) | [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)[NoOp, OptIn, CloseOut, UpdateApplication, DeleteApplication]] = ...) → [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[algopy.arc4._TARC4Contract], [None](https://docs.python.org/3/library/constants.html#None)]], [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[algopy.arc4._TARC4Contract], [None](https://docs.python.org/3/library/constants.html#None)]]

Decorator that indicates a method is an ARC-4 bare method.

There can be only one bare method on a contract for each given On-Completion Action.

* **Parameters:**
  * **create** – Controls the validation of the Application ID. “require” means it must be zero,
    “disallow” requires it must be non-zero, and “allow” disables the validation.
  * **allow_actions** – Which On-Completion Action(s) to handle.

### algopy.arc4.emit(event: [str](https://docs.python.org/3/library/stdtypes.html#str) | [algopy.arc4.Struct](#algopy.arc4.Struct), /, \*args: [object](https://docs.python.org/3/library/functions.html#object)) → [None](https://docs.python.org/3/library/constants.html#None)

Emit an ARC-28 event for the provided event signature or name, and provided args.

* **Parameters:**
  * **event** – 

    Either an ARC-4 Struct, an event name, or event signature.
    * If event is an ARC-4 Struct, the event signature will be determined from the Struct name and fields
    * If event is a signature, then the following args will be typed checked to ensure they match.
    * If event is just a name, the event signature will be inferred from the name and following arguments
  * **args** – When event is a signature or name, args will be used as the event data.
    They will all be encoded as single ARC-4 Tuple

Example:

```default
from algopy import ARC4Contract, arc4


class Swapped(arc4.Struct):
    a: arc4.UInt64
    b: arc4.UInt64


class EventEmitter(ARC4Contract):
    @arc4.abimethod
    def emit_swapped(self, a: arc4.UInt64, b: arc4.UInt64) -> None:
        arc4.emit(Swapped(b, a))
        arc4.emit("Swapped(uint64,uint64)", b, a)
        arc4.emit("Swapped", b, a)
```
