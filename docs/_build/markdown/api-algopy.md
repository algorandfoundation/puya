# [`algopy`](#module-algopy)

## Package Contents

### Classes

| [`ARC4Contract`](api-algopy.arc4.md#algopy.arc4.ARC4Contract)   | A contract that conforms to the ARC-4 ABI specification, functions decorated with<br/>`@abimethod` or `@baremethod` will form the public interface of the contract                                                                         |
|-----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`Account`](#algopy.Account)                                    | An Account on the Algorand network.                                                                                                                                                                                                        |
| [`Application`](#algopy.Application)                            | An Application on the Algorand network.                                                                                                                                                                                                    |
| [`Array`](#algopy.Array)                                        | A dynamically sized Array of the specified type                                                                                                                                                                                            |
| [`Asset`](#algopy.Asset)                                        | An Asset on the Algorand network.                                                                                                                                                                                                          |
| [`BigUInt`](#algopy.BigUInt)                                    | A variable length (max 512-bit) unsigned integer                                                                                                                                                                                           |
| [`Box`](#algopy.Box)                                            | Box abstracts the reading and writing of a single value to a single box.<br/>The box size will be reconfigured dynamically to fit the size of the value being assigned to<br/>it.                                                          |
| [`BoxMap`](#algopy.BoxMap)                                      | BoxMap abstracts the reading and writing of a set of boxes using a common key and content type.<br/>Each composite key (prefix + key) still needs to be made available to the application via the<br/>`boxes` property of the Transaction. |
| [`BoxRef`](#algopy.BoxRef)                                      | BoxRef abstracts the reading and writing of boxes containing raw binary data. The size is<br/>configured manually, and can be set to values larger than what the AVM can handle in a single<br/>value.                                     |
| [`Bytes`](#algopy.Bytes)                                        | A byte sequence, with a maximum length of 4096 bytes, one of the primary data types on the AVM                                                                                                                                             |
| [`BytesBacked`](#algopy.BytesBacked)                            | Represents a type that is a single bytes value                                                                                                                                                                                             |
| [`CompiledContract`](#algopy.CompiledContract)                  | Provides compiled programs and state allocation values for a Contract.<br/>Create by calling [`compile_contract`](#algopy.compile_contract).                                                                                               |
| [`CompiledLogicSig`](#algopy.CompiledLogicSig)                  | Provides account for a Logic Signature.<br/>Create by calling [`compile_logicsig`](#algopy.compile_logicsig).                                                                                                                              |
| [`Contract`](#algopy.Contract)                                  | Base class for an Algorand Smart Contract                                                                                                                                                                                                  |
| [`FixedArray`](#algopy.FixedArray)                              | A fixed length Array of the specified type and length                                                                                                                                                                                      |
| [`Global`](api-algopy.op.md#algopy.op.Global)                   | Get Global values<br/>Native TEAL op: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)                                                                                                                          |
| [`GlobalState`](#algopy.GlobalState)                            | Global state associated with the application, the key will be the name of the member, this<br/>is assigned to                                                                                                                              |
| [`ImmutableArray`](#algopy.ImmutableArray)                      | An immutable array that supports fixed and dynamically sized immutable elements.<br/>Modifications are done by returning a new copy of the array with the modifications applied.                                                           |
| [`ImmutableFixedArray`](#algopy.ImmutableFixedArray)            | An immutable fixed length Array of the specified type and length                                                                                                                                                                           |
| [`LocalState`](#algopy.LocalState)                              | Local state associated with the application and an account                                                                                                                                                                                 |
| [`LogicSig`](#algopy.LogicSig)                                  | A logic signature                                                                                                                                                                                                                          |
| [`OnCompleteAction`](#algopy.OnCompleteAction)                  | On Completion actions available in an application call transaction                                                                                                                                                                         |
| [`OpUpFeeSource`](#algopy.OpUpFeeSource)                        | Defines the source of fees for the OpUp utility.                                                                                                                                                                                           |
| [`ReferenceArray`](#algopy.ReferenceArray)                      | A mutable array that supports fixed sized immutable elements. All references to this array<br/>will see any updates made to it.                                                                                                            |
| [`StateTotals`](#algopy.StateTotals)                            | Options class to manually define the total amount of global and local state contract will use,<br/>used by [`Contract.__init_subclass__`](#algopy.Contract.__init_subclass__).                                                             |
| [`String`](#algopy.String)                                      | A UTF-8 encoded string.                                                                                                                                                                                                                    |
| [`Struct`](#algopy.Struct)                                      | Base class for Struct types                                                                                                                                                                                                                |
| [`TransactionType`](#algopy.TransactionType)                    | The different transaction types available in a transaction                                                                                                                                                                                 |
| [`Txn`](api-algopy.op.md#algopy.op.Txn)                         | Get values for the current executing transaction<br/>Native TEAL ops: [`txn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txn), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)                     |
| [`UInt64`](#algopy.UInt64)                                      | A 64-bit unsigned integer, one of the primary data types on the AVM                                                                                                                                                                        |
| [`uenumerate`](#algopy.uenumerate)                              | Yields pairs containing a count (from zero) and a value yielded by the iterable argument.                                                                                                                                                  |
| [`urange`](#algopy.urange)                                      | Produces a sequence of UInt64 from start (inclusive) to stop (exclusive) by step.                                                                                                                                                          |

### Functions

| [`compile_contract`](#algopy.compile_contract)   | Returns the compiled data for the specified contract                                                          |
|--------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| [`compile_logicsig`](#algopy.compile_logicsig)   | Returns the Account for the specified logic signature                                                         |
| [`ensure_budget`](#algopy.ensure_budget)         | Ensure the available op code budget is greater than or equal to required_budget                               |
| [`log`](#algopy.log)                             | Concatenates and logs supplied args as a single bytes value.                                                  |
| [`logicsig`](#algopy.logicsig)                   | Decorator to indicate a function is a logic signature                                                         |
| [`size_of`](#algopy.size_of)                     | Returns the number of bytes required to store the provided type object<br/>or the type of provided expression |
| [`subroutine`](#algopy.subroutine)               | Decorator to indicate functions or methods that can be called by a Smart Contract                             |
| [`zero_bytes`](#algopy.zero_bytes)               | Initializes a new value of the specified type, based on it’s zero bytes representation.                       |

### Data

| [`TemplateVar`](#algopy.TemplateVar)   | Template variables can be used to represent a placeholder for a deploy-time provided value.   |
|----------------------------------------|-----------------------------------------------------------------------------------------------|

### API

### *class* algopy.ARC4Contract

A contract that conforms to the ARC-4 ABI specification, functions decorated with
`@abimethod` or `@baremethod` will form the public interface of the contract

The approval_program will be implemented by the compiler, and route application args
according to the ARC-4 ABI specification

The clear_state_program will by default return True, but can be overridden

#### *classmethod* \_\_init_subclass_\_(\*, name: [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., scratch_slots: [algopy.urange](#algopy.urange) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](#algopy.urange), ...] | [list](https://docs.python.org/3/library/stdtypes.html#list)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](#algopy.urange)] = ..., state_totals: [algopy.StateTotals](#algopy.StateTotals) = ..., avm_version: [int](https://docs.python.org/3/library/functions.html#int) = ...)

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

#### clear_state_program() → [algopy.UInt64](#algopy.UInt64) | [bool](https://docs.python.org/3/library/functions.html#bool)

Represents the program called when `OnCompletion` == `ClearState`

### *class* algopy.Account(value: [str](https://docs.python.org/3/library/stdtypes.html#str) | [algopy.Bytes](#algopy.Bytes) = ..., /)

An Account on the Algorand network.

Note: must be an available resource to access properties other than `bytes`

### Initialization

If `value` is a string, it should be a 58 character base32 string,
ie a base32 string-encoded 32 bytes public key + 4 bytes checksum.
If `value` is a Bytes, it’s length checked to be 32 bytes - to avoid this
check, use `Address.from_bytes(...)` instead.
Defaults to the zero-address.

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not equal to the zero-address

#### \_\_eq_\_(other: [algopy.Account](#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Account equality is determined by the address of another `Account` or `str`

#### \_\_ne_\_(other: [algopy.Account](#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Account equality is determined by the address of another `Account` or `str`

#### *property* auth_address *: [algopy.Account](#algopy.Account)*

Address the account is rekeyed to

#### NOTE
Account must be an available resource

#### *property* balance *: [algopy.UInt64](#algopy.UInt64)*

Account balance in microalgos

#### NOTE
Account must be an available resource

#### *property* bytes *: [algopy.Bytes](#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### is_opted_in(asset_or_app: [algopy.Asset](#algopy.Asset) | [algopy.Application](#algopy.Application), /) → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns true if this account is opted in to the specified Asset or Application.

#### NOTE
Account and Asset/Application must be an available resource

#### *property* min_balance *: [algopy.UInt64](#algopy.UInt64)*

Minimum required balance for account, in microalgos

#### NOTE
Account must be an available resource

#### *property* total_apps_created *: [algopy.UInt64](#algopy.UInt64)*

The number of existing apps created by this account.

#### NOTE
Account must be an available resource

#### *property* total_apps_opted_in *: [algopy.UInt64](#algopy.UInt64)*

The number of apps this account is opted into.

#### NOTE
Account must be an available resource

#### *property* total_assets *: [algopy.UInt64](#algopy.UInt64)*

The numbers of ASAs held by this account (including ASAs this account created).

#### NOTE
Account must be an available resource

#### *property* total_assets_created *: [algopy.UInt64](#algopy.UInt64)*

The number of existing ASAs created by this account.

#### NOTE
Account must be an available resource

#### *property* total_box_bytes *: [algopy.UInt64](#algopy.UInt64)*

The total number of bytes used by this account’s app’s box keys and values.

#### NOTE
Account must be an available resource

#### *property* total_boxes *: [algopy.UInt64](#algopy.UInt64)*

The number of existing boxes created by this account’s app.

#### NOTE
Account must be an available resource

#### *property* total_extra_app_pages *: [algopy.UInt64](#algopy.UInt64)*

The number of extra app code pages used by this account.

#### NOTE
Account must be an available resource

#### *property* total_num_byte_slice *: [algopy.UInt64](#algopy.UInt64)*

The total number of byte array values allocated by this account in Global and Local States.

#### NOTE
Account must be an available resource

#### *property* total_num_uint *: [algopy.UInt64](#algopy.UInt64)*

The total number of uint64 values allocated by this account in Global and Local States.

#### NOTE
Account must be an available resource

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.Application(application_id: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

An Application on the Algorand network.

### Initialization

Initialized with the id of an application. Defaults to zero (an invalid ID).

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if `application_id` is not `0`

#### \_\_eq_\_(other: [algopy.Application](#algopy.Application)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Application equality is determined by the equality of an Application’s id

#### \_\_ne_\_(other: [algopy.Application](#algopy.Application)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Application equality is determined by the equality of an Application’s id

#### *property* address *: [algopy.Account](#algopy.Account)*

Address for which this application has authority

#### NOTE
Application must be an available resource

#### *property* approval_program *: [algopy.Bytes](#algopy.Bytes)*

Bytecode of Approval Program

#### NOTE
Application must be an available resource

#### *property* clear_state_program *: [algopy.Bytes](#algopy.Bytes)*

Bytecode of Clear State Program

#### NOTE
Application must be an available resource

#### *property* creator *: [algopy.Account](#algopy.Account)*

Creator address

#### NOTE
Application must be an available resource

#### *property* extra_program_pages *: [algopy.UInt64](#algopy.UInt64)*

Number of Extra Program Pages of code space

#### NOTE
Application must be an available resource

#### *property* global_num_bytes *: [algopy.UInt64](#algopy.UInt64)*

Number of byte array values allowed in Global State

#### NOTE
Application must be an available resource

#### *property* global_num_uint *: [algopy.UInt64](#algopy.UInt64)*

Number of uint64 values allowed in Global State

#### NOTE
Application must be an available resource

#### *property* id *: [algopy.UInt64](#algopy.UInt64)*

Returns the id of the application

#### *property* local_num_bytes *: [algopy.UInt64](#algopy.UInt64)*

Number of byte array values allowed in Local State

#### NOTE
Application must be an available resource

#### *property* local_num_uint *: [algopy.UInt64](#algopy.UInt64)*

Number of uint64 values allowed in Local State

#### NOTE
Application must be an available resource

#### *property* version *: [algopy.UInt64](#algopy.UInt64)*

Version of the app, incremented each time the approval or clear program changes

#### NOTE
Application must be an available resource

### *class* algopy.Array

A dynamically sized Array of the specified type

#### \_\_add_\_(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy._TArrayItem]) → [algopy.Array](#algopy.Array)[algopy._TArrayItem]

Concat two arrays together, returning a new array

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not an empty array

#### \_\_getitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy._TArrayItem

Gets the item of the array at provided index

#### \_\_reversed_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### \_\_setitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy._TArrayItem) → algopy._TArrayItem

Sets the item of the array at specified index to provided value

#### append(item: algopy._TArrayItem, /) → [None](https://docs.python.org/3/library/constants.html#None)

Append an item to this array

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### extend(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy._TArrayItem], /) → [None](https://docs.python.org/3/library/constants.html#None)

Extend this array with the contents of another array

#### freeze() → [algopy.ImmutableArray](#algopy.ImmutableArray)[algopy._TArrayItem]

Returns an immutable copy of this array

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Returns the current length of the array

#### pop() → algopy._TArrayItem

Remove and return the last item of this array

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.Asset(asset_id: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

An Asset on the Algorand network.

### Initialization

Initialized with the id of an asset. Defaults to zero (an invalid ID).

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if `asset_id` is not `0`

#### \_\_eq_\_(other: [algopy.Asset](#algopy.Asset)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Asset equality is determined by the equality of an Asset’s id

#### \_\_ne_\_(other: [algopy.Asset](#algopy.Asset)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Asset equality is determined by the equality of an Asset’s id

#### balance(account: [algopy.Account](#algopy.Account), /) → [algopy.UInt64](#algopy.UInt64)

Amount of the asset unit held by this account. Fails if the account has not
opted in to the asset.

#### NOTE
Asset and supplied Account must be an available resource

#### *property* clawback *: [algopy.Account](#algopy.Account)*

Clawback address

#### NOTE
Asset must be an available resource

#### *property* creator *: [algopy.Account](#algopy.Account)*

Creator address

#### NOTE
Asset must be an available resource

#### *property* decimals *: [algopy.UInt64](#algopy.UInt64)*

See AssetParams.Decimals

#### NOTE
Asset must be an available resource

#### *property* default_frozen *: [bool](https://docs.python.org/3/library/functions.html#bool)*

Frozen by default or not

#### NOTE
Asset must be an available resource

#### *property* freeze *: [algopy.Account](#algopy.Account)*

Freeze address

#### NOTE
Asset must be an available resource

#### frozen(account: [algopy.Account](#algopy.Account), /) → [bool](https://docs.python.org/3/library/functions.html#bool)

Is the asset frozen or not. Fails if the account has not
opted in to the asset.

#### NOTE
Asset and supplied Account must be an available resource

#### *property* id *: [algopy.UInt64](#algopy.UInt64)*

Returns the id of the Asset

#### *property* manager *: [algopy.Account](#algopy.Account)*

Manager address

#### NOTE
Asset must be an available resource

#### *property* metadata_hash *: [algopy.Bytes](#algopy.Bytes)*

Arbitrary commitment

#### NOTE
Asset must be an available resource

#### *property* name *: [algopy.Bytes](#algopy.Bytes)*

Asset name

#### NOTE
Asset must be an available resource

#### *property* reserve *: [algopy.Account](#algopy.Account)*

Reserve address

#### NOTE
Asset must be an available resource

#### *property* total *: [algopy.UInt64](#algopy.UInt64)*

Total number of units of this asset

#### NOTE
Asset must be an available resource

#### *property* unit_name *: [algopy.Bytes](#algopy.Bytes)*

Asset unit name

#### NOTE
Asset must be an available resource

#### *property* url *: [algopy.Bytes](#algopy.Bytes)*

URL with additional info about the asset

#### NOTE
Asset must be an available resource

### *class* algopy.BigUInt(value: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

A variable length (max 512-bit) unsigned integer

### Initialization

A BigUInt can be initialized with a UInt64, a Python int literal, or an int variable
declared at the module level

#### \_\_add_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be added with another BigUInt, UInt64 or int e.g. `BigUInt(4) + 2`.

#### \_\_and_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `BigUInt(4) & 2`

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

A BigUInt will evaluate to `False` if zero, and `True` otherwise

#### \_\_eq_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A BigUInt can use the `==` operator with another BigUInt, UInt64 or int

#### \_\_floordiv_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `BigUInt(4) // 2`.

This will error on divide by zero

#### \_\_ge_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A BigUInt can use the `>=` operator with another BigUInt, UInt64 or int

#### \_\_gt_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A BigUInt can use the `>` operator with another BigUInt, UInt64 or int

#### \_\_iadd_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be incremented with another BigUInt, UInt64 or int e.g. `a += BigUInt(2)`.

#### \_\_iand_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `a &= BigUInt(2)`

#### \_\_ifloordiv_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `a //= BigUInt(2)`.

This will error on divide by zero

#### \_\_imod_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `a %= BigUInt(2)`.

This will error on mod by zero

#### \_\_imul_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `a*= BigUInt(2)`.

#### \_\_ior_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `a |= BigUInt(2)`

#### \_\_isub_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `a -= BigUInt(2)`.

This will error on underflow

#### \_\_ixor_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `a ^= BigUInt(2)`

#### \_\_le_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A BigUInt can use the `<=` operator with another BigUInt, UInt64 or int

#### \_\_lt_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A BigUInt can use the `<` operator with another BigUInt, UInt64 or int

#### \_\_mod_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `BigUInt(4) % 2`.

This will error on mod by zero

#### \_\_mul_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `4 + BigUInt(2)`.

#### \_\_ne_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A BigUInt can use the `!=` operator with another BigUInt, UInt64 or int

#### \_\_or_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `BigUInt(4) | 2`

#### \_\_pos_\_() → [algopy.BigUInt](#algopy.BigUInt)

Supports unary + operator. Redundant given the type is unsigned

#### \_\_radd_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be added with another BigUInt, UInt64 or int e.g. `4 + BigUInt(2)`.

#### \_\_rand_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise and with another BigUInt, UInt64 or int e.g. `4 & BigUInt(2)`

#### \_\_rfloordiv_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be floor divided with another BigUInt, UInt64 or int e.g. `4 // BigUInt(2)`.

This will error on divide by zero

#### \_\_rmod_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be modded with another BigUInt, UInt64 or int e.g. `4 % BigUInt(2)`.

This will error on mod by zero

#### \_\_rmul_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be multiplied with another BigUInt, UInt64 or int e.g. `BigUInt(4) + 2`.

#### \_\_ror_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise or with another BigUInt, UInt64 or int e.g. `4 | BigUInt(2)`

#### \_\_rsub_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `4 - BigUInt(2)`.

This will error on underflow

#### \_\_rxor_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `4 ^ BigUInt(2)`

#### \_\_sub_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can be subtracted with another BigUInt, UInt64 or int e.g. `BigUInt(4) - 2`.

This will error on underflow

#### \_\_xor_\_(other: [algopy.BigUInt](#algopy.BigUInt) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.BigUInt](#algopy.BigUInt)

A BigUInt can bitwise xor with another BigUInt, UInt64 or int e.g. `BigUInt(4) ^ 2`

#### *property* bytes *: [algopy.Bytes](#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

### *class* algopy.Box(type_: [type](https://docs.python.org/3/library/functions.html#type)[algopy._TValue], /, \*, key: [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [algopy.Bytes](#algopy.Bytes) | [algopy.String](#algopy.String) = ...)

Box abstracts the reading and writing of a single value to a single box.
The box size will be reconfigured dynamically to fit the size of the value being assigned to
it.

### Initialization

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns True if the box exists, regardless of the truthiness of the contents
of the box

#### create(\*, size: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ...) → [bool](https://docs.python.org/3/library/functions.html#bool)

Creates the box with the specified size setting all bits to zero.
If size is not specified and the type is a fixed size, then the storage size of the type
will be used.
Fails if the box already exists with a different size.
Fails if the specified size is greater than the max box size (32,768)
Fails if size is omitted and the type is not fixed size.

Returns True if the box was created, False if the box already existed

#### extract(start_index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), length: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.Bytes](#algopy.Bytes)

Extract a slice of bytes from the box.

Fails if the box does not exist, or if `start_index + length > len(box)`

* **Parameters:**
  * **start_index** – The offset to start extracting bytes from
  * **length** – The number of bytes to extract

#### get(\*, default: algopy._TValue) → algopy._TValue

Retrieve the contents of the box, or return the default value if the box has not been
created.

* **Parameters:**
  **default** – The default value to return if the box has not been created

#### *property* key *: [algopy.Bytes](#algopy.Bytes)*

Provides access to the raw storage key

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Get the length of this Box. Fails if the box does not exist

#### maybe() → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[algopy._TValue, [bool](https://docs.python.org/3/library/functions.html#bool)]

Retrieve the contents of the box if it exists, and return a boolean indicating if the box
exists.

#### *property* ref *: [algopy.BoxRef](#algopy.BoxRef)*

Provides a BoxRef for this box

#### replace(start_index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [None](https://docs.python.org/3/library/constants.html#None)

Write `value` to the box starting at `start_index`. Fails if the box does not exist,
or if `start_index + len(value) > len(box)`

* **Parameters:**
  * **start_index** – The offset to start writing bytes from
  * **value** – The bytes to be written

#### resize(new_size: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [None](https://docs.python.org/3/library/constants.html#None)

Resizes the box the specified `new_size`. Truncating existing data if the new value is
shorter or padding with zero bytes if it is longer.

* **Parameters:**
  **new_size** – The new size of the box

#### splice(start_index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), length: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [None](https://docs.python.org/3/library/constants.html#None)

set box to contain its previous bytes up to index `start_index`, followed by `bytes`,
followed by the original bytes of the box that began at index `start_index + length`

**Important: This op does not resize the box**
If the new value is longer than the box size, it will be truncated.
If the new value is shorter than the box size, it will be padded with zero bytes

* **Parameters:**
  * **start_index** – The index to start inserting `value`
  * **length** – The number of bytes after `start_index` to omit from the new value
  * **value** – The `value` to be inserted.

#### *property* value *: algopy._TValue*

Retrieve the contents of the box. Fails if the box has not been created.

### *class* algopy.BoxMap(key_type: [type](https://docs.python.org/3/library/functions.html#type)[algopy._TKey], value_type: [type](https://docs.python.org/3/library/functions.html#type)[algopy._TValue], /, \*, key_prefix: [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [algopy.Bytes](#algopy.Bytes) | [algopy.String](#algopy.String) = ...)

BoxMap abstracts the reading and writing of a set of boxes using a common key and content type.
Each composite key (prefix + key) still needs to be made available to the application via the
`boxes` property of the Transaction.

### Initialization

Declare a box map.

* **Parameters:**
  * **key_type** – The type of the keys
  * **value_type** – The type of the values
  * **key_prefix** – The value used as a prefix to key data, can be empty.
    When the BoxMap is being assigned to a member variable,
    this argument is optional and defaults to the member variable name,
    and if a custom value is supplied it must be static.

#### \_\_contains_\_(key: algopy._TKey) → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns True if a box with the specified key exists in the map, regardless of the
truthiness of the contents of the box

#### \_\_delitem_\_(key: algopy._TKey) → [None](https://docs.python.org/3/library/constants.html#None)

Deletes a keyed box

#### \_\_getitem_\_(key: algopy._TKey) → algopy._TValue

Retrieve the contents of a keyed box. Fails if the box for the key has not been created.

#### \_\_setitem_\_(key: algopy._TKey, value: algopy._TValue) → [None](https://docs.python.org/3/library/constants.html#None)

Write *value* to a keyed box. Creates the box if it does not exist

#### box(key: algopy._TKey) → [algopy.Box](#algopy.Box)[algopy._TValue]

Returns a Box holding the box value at key

#### get(key: algopy._TKey, \*, default: algopy._TValue) → algopy._TValue

Retrieve the contents of a keyed box, or return the default value if the box has not been
created.

* **Parameters:**
  * **key** – The key of the box to get
  * **default** – The default value to return if the box has not been created.

#### *property* key_prefix *: [algopy.Bytes](#algopy.Bytes)*

Provides access to the raw storage key-prefix

#### length(key: algopy._TKey) → [algopy.UInt64](#algopy.UInt64)

Get the length of an item in this BoxMap. Fails if the box does not exist

* **Parameters:**
  **key** – The key of the box to get

#### maybe(key: algopy._TKey) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[algopy._TValue, [bool](https://docs.python.org/3/library/functions.html#bool)]

Retrieve the contents of a keyed box if it exists, and return a boolean indicating if the
box exists.

* **Parameters:**
  **key** – The key of the box to get

### *class* algopy.BoxRef(/, \*, key: bytes | str | algopy.Bytes | algopy.String = ...)

BoxRef abstracts the reading and writing of boxes containing raw binary data. The size is
configured manually, and can be set to values larger than what the AVM can handle in a single
value.

### Initialization

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns True if the box has a value set, regardless of the truthiness of that value

#### create(\*, size: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Creates a box with the specified size, setting all bits to zero. Fails if the box already
exists with a different size. Fails if the specified size is greater than the max box size
(32,768)

Returns True if the box was created, False if the box already existed

#### delete() → [bool](https://docs.python.org/3/library/functions.html#bool)

Deletes the box if it exists and returns a value indicating if the box existed

#### extract(start_index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), length: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.Bytes](#algopy.Bytes)

Extract a slice of bytes from the box.

Fails if the box does not exist, or if `start_index + length > len(box)`

* **Parameters:**
  * **start_index** – The offset to start extracting bytes from
  * **length** – The number of bytes to extract

#### get(\*, default: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Retrieve the contents of the box, or return the default value if the box has not been
created.

* **Parameters:**
  **default** – The default value to return if the box has not been created

#### *property* key *: [algopy.Bytes](#algopy.Bytes)*

Provides access to the raw storage key

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Get the length of this Box. Fails if the box does not exist

#### maybe() → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]

Retrieve the contents of the box if it exists, and return a boolean indicating if the box
exists.

#### put(value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [None](https://docs.python.org/3/library/constants.html#None)

Replaces the contents of box with value. Fails if box exists and len(box) != len(value).
Creates box if it does not exist

* **Parameters:**
  **value** – The value to write to the box

#### replace(start_index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [None](https://docs.python.org/3/library/constants.html#None)

Write `value` to the box starting at `start_index`. Fails if the box does not exist,
or if `start_index + len(value) > len(box)`

* **Parameters:**
  * **start_index** – The offset to start writing bytes from
  * **value** – The bytes to be written

#### resize(new_size: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [None](https://docs.python.org/3/library/constants.html#None)

Resizes the box the specified `new_size`. Truncating existing data if the new value is
shorter or padding with zero bytes if it is longer.

* **Parameters:**
  **new_size** – The new size of the box

#### splice(start_index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), length: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [None](https://docs.python.org/3/library/constants.html#None)

set box to contain its previous bytes up to index `start_index`, followed by `bytes`,
followed by the original bytes of the box that began at index `start_index + length`

**Important: This op does not resize the box**
If the new value is longer than the box size, it will be truncated.
If the new value is shorter than the box size, it will be padded with zero bytes

* **Parameters:**
  * **start_index** – The index to start inserting `value`
  * **length** – The number of bytes after `start_index` to omit from the new value
  * **value** – The `value` to be inserted.

### *class* algopy.Bytes(value: [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = b'', /)

A byte sequence, with a maximum length of 4096 bytes, one of the primary data types on the AVM

### Initialization

Bytes can be initialized with a Python bytes literal, or bytes variable
declared at the module level

#### \_\_add_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Concatenate Bytes with another Bytes or bytes literal
e.g. `Bytes(b"Hello ") + b"World"`.

#### \_\_and_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Bytes can bitwise and with another Bytes or bytes e.g. `Bytes(b"FF") & b"0F")`

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if length of bytes is >0

#### \_\_contains_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Test whether another Bytes is a substring of this one.
Note this is expensive due to a lack of AVM support.

#### \_\_eq_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Bytes can be compared using the `==` operator with another Bytes or bytes

#### \_\_getitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) | [slice](https://docs.python.org/3/library/functions.html#slice)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.UInt64](#algopy.UInt64) | [None](https://docs.python.org/3/library/constants.html#None), [int](https://docs.python.org/3/library/functions.html#int) | [algopy.UInt64](#algopy.UInt64) | [None](https://docs.python.org/3/library/constants.html#None), [None](https://docs.python.org/3/library/constants.html#None)]) → [algopy.Bytes](#algopy.Bytes)

Returns a Bytes containing a single byte if indexed with UInt64 or int
otherwise the substring o bytes described by the slice

#### \_\_iadd_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Concatenate Bytes with another Bytes or bytes literal
e.g. `a += Bytes(b"World")`.

#### \_\_iand_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Bytes can bitwise and with another Bytes or bytes e.g. `a &= Bytes(b"0F")`

#### \_\_invert_\_() → [algopy.Bytes](#algopy.Bytes)

Bytes can be bitwise inverted e.g. `~Bytes(b"FF)`

#### \_\_ior_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Bytes can bitwise or with another Bytes or bytes e.g. `a |= Bytes(b"0F")`

#### \_\_iter_\_() → [collections.abc.Iterator](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[[algopy.Bytes](#algopy.Bytes)]

Bytes can be iterated, yielding each consecutive byte

#### \_\_ixor_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Bytes can bitwise xor with another Bytes or bytes e.g. `a ^= Bytes(b"0F")`

#### \_\_ne_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Bytes can be compared using the `!=` operator with another Bytes or bytes

#### \_\_or_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Bytes can bitwise or with another Bytes or bytes e.g. `Bytes(b"FF") | b"0F")`

#### \_\_radd_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Concatenate Bytes with another Bytes or bytes literal
e.g. `b"Hello " + Bytes(b"World")`.

#### \_\_reversed_\_() → [collections.abc.Iterator](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[[algopy.Bytes](#algopy.Bytes)]

Bytes can be iterated in reverse, yield each preceding byte starting at the end

#### \_\_xor_\_(other: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes)) → [algopy.Bytes](#algopy.Bytes)

Bytes can bitwise xor with another Bytes or bytes e.g. `Bytes(b"FF") ^ b"0F")`

#### *static* from_base32(value: [str](https://docs.python.org/3/library/stdtypes.html#str), /) → [algopy.Bytes](#algopy.Bytes)

Creates Bytes from a base32 encoded string e.g. `Bytes.from_base32("74======")`

#### *static* from_base64(value: [str](https://docs.python.org/3/library/stdtypes.html#str), /) → [algopy.Bytes](#algopy.Bytes)

Creates Bytes from a base64 encoded string e.g. `Bytes.from_base64("RkY=")`

#### *static* from_hex(value: [str](https://docs.python.org/3/library/stdtypes.html#str), /) → [algopy.Bytes](#algopy.Bytes)

Creates Bytes from a hex/octal encoded string e.g. `Bytes.from_hex("FF")`

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Returns the length of the Bytes

### *class* algopy.BytesBacked

Represents a type that is a single bytes value

#### *property* bytes *: [algopy.Bytes](#algopy.Bytes)*

Get the underlying Bytes

#### *classmethod* from_bytes(value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

### *class* algopy.CompiledContract

Provides compiled programs and state allocation values for a Contract.
Create by calling [`compile_contract`](#algopy.compile_contract).

#### approval_program *: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](#algopy.Bytes), [algopy.Bytes](#algopy.Bytes)]*

None

Approval program pages for a contract, after template variables have been replaced
and compiled to AVM bytecode

#### clear_state_program *: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](#algopy.Bytes), [algopy.Bytes](#algopy.Bytes)]*

None

Clear state program pages for a contract, after template variables have been replaced
and compiled to AVM bytecode

#### extra_program_pages *: [algopy.UInt64](#algopy.UInt64)*

None

By default, provides extra program pages required based on approval and clear state program
size, can be overridden when calling compile_contract

#### global_bytes *: [algopy.UInt64](#algopy.UInt64)*

None

By default, provides global num bytes based on contract state totals, can be overridden
when calling compile_contract

#### global_uints *: [algopy.UInt64](#algopy.UInt64)*

None

By default, provides global num uints based on contract state totals, can be overridden
when calling compile_contract

#### local_bytes *: [algopy.UInt64](#algopy.UInt64)*

None

By default, provides local num bytes based on contract state totals, can be overridden
when calling compile_contract

#### local_uints *: [algopy.UInt64](#algopy.UInt64)*

None

By default, provides local num uints based on contract state totals, can be overridden
when calling compile_contract

### *class* algopy.CompiledLogicSig

Provides account for a Logic Signature.
Create by calling [`compile_logicsig`](#algopy.compile_logicsig).

#### account *: [algopy.Account](#algopy.Account)*

None

Address of a logic sig program, after template variables have been replaced and compiled
to AVM bytecode

### *class* algopy.Contract

Base class for an Algorand Smart Contract

#### *classmethod* \_\_init_subclass_\_(\*, name: [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., scratch_slots: [algopy.urange](#algopy.urange) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](#algopy.urange), ...] | [list](https://docs.python.org/3/library/stdtypes.html#list)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](#algopy.urange)] = ..., state_totals: [algopy.StateTotals](#algopy.StateTotals) = ..., avm_version: [int](https://docs.python.org/3/library/functions.html#int) = ...)

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

#### *abstract* approval_program() → [algopy.UInt64](#algopy.UInt64) | [bool](https://docs.python.org/3/library/functions.html#bool)

Represents the program called for all transactions
where `OnCompletion` != `ClearState`

#### *abstract* clear_state_program() → [algopy.UInt64](#algopy.UInt64) | [bool](https://docs.python.org/3/library/functions.html#bool)

Represents the program called when `OnCompletion` == `ClearState`

### *class* algopy.FixedArray(values: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy._TArrayItem])

A fixed length Array of the specified type and length

### Initialization

#### \_\_getitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy._TArrayItem

Gets the item of the array at the provided index

#### \_\_iter_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array

#### \_\_reversed_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### \_\_setitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy._TArrayItem) → algopy._TArrayItem

Sets the item of the array at the specified index to provided value

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### freeze() → [algopy.ImmutableFixedArray](#algopy.ImmutableFixedArray)[algopy._TArrayItem, algopy._TArrayLength]

Returns an immutable copy of this array

#### *classmethod* full(item: algopy._TArrayItem) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Initializes a new array, filled with copies of the specified value

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Returns the (compile-time) length of the array

#### replace(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy._TArrayItem) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Returns a copy of the array with the item at the specified index replaced with the specified value

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.Global

Get Global values
Native TEAL op: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)

#### asset_create_min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The additional minimum balance required to create (and opt-in to) an asset.

#### asset_opt_in_min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The additional minimum balance required to opt-in to an asset.

#### caller_application_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

The application address of the application that called this application. ZeroAddress if this application is at the top-level. Application mode only.

#### caller_application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The application ID of the application that called this application. 0 if this application is at the top-level. Application mode only.

#### creator_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

Address of the creator of the current application. Application mode only.

#### current_application_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

Address that the current application controls. Application mode only.

#### current_application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Application](#algopy.Application)]*

Ellipsis

ID of current application executing. Application mode only.

#### genesis_hash *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

The Genesis Hash for the network.

#### group_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

ID of the transaction group. 32 zero bytes if the transaction is not part of a group.

#### group_size *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of transactions in this atomic transaction group. At least 1

#### latest_timestamp *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Last confirmed block UNIX timestamp. Fails if negative. Application mode only.

#### logic_sig_version *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Maximum supported version

#### max_txn_life *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

rounds

#### min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

microalgos

#### min_txn_fee *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

microalgos

#### *static* opcode_budget() → [algopy.UInt64](#algopy.UInt64)

The remaining cost that can be spent by opcodes in this program.

Native TEAL opcode: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)

#### payouts_enabled *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]*

Ellipsis

Whether block proposal payouts are enabled.
Min AVM version: 11

#### payouts_go_online_fee *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The fee required in a keyreg transaction to make an account incentive eligible.
Min AVM version: 11

#### payouts_max_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The maximum balance an account can have in the agreement round to receive block payouts in the proposal round.
Min AVM version: 11

#### payouts_min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The minimum balance an account must have in the agreement round to receive block payouts in the proposal round.
Min AVM version: 11

#### payouts_percent *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The percentage of transaction fees in a block that can be paid to the block proposer.
Min AVM version: 11

#### round *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Current round number. Application mode only.

#### zero_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address of all zero bytes

### *class* algopy.GlobalState

Global state associated with the application, the key will be the name of the member, this
is assigned to

#### NOTE
The `GlobalState` class provides a richer API that in addition to storing and retrieving
values, can test if a value is set or unset it. However if this extra functionality is not
needed then it is simpler to just store the data without the GlobalState proxy
e.g. `self.some_variable = UInt64(0)`

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if the key has a value set, regardless of the truthiness of that value

#### get(default: algopy._TState) → algopy._TState

Returns the value or `default` if no value is set

```python
name = self.name.get(Bytes(b"no name")
```

#### *property* key *: [algopy.Bytes](#algopy.Bytes)*

Provides access to the raw storage key

#### maybe() → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[algopy._TState, [bool](https://docs.python.org/3/library/functions.html#bool)]

Returns the value, and a bool

```python
name, name_exists = self.name.maybe()
if not name_exists:
    name = Bytes(b"no name")
```

#### *property* value *: algopy._TState*

Returns the value or and error if the value is not set

```python
name = self.name.value
```

### *class* algopy.ImmutableArray

An immutable array that supports fixed and dynamically sized immutable elements.
Modifications are done by returning a new copy of the array with the modifications applied.

Example:

```python
arr = ImmutableArray[UInt64]()

arr = arr.append(UInt64(42))
element = arr[0]
assert element == 42
arr = arr.pop()
```

#### \_\_add_\_(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy._TArrayItem], /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Return a copy of this array extended with the contents of another array

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not an empty array

#### \_\_getitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy._TArrayItem

Gets the item of the array at provided index

#### \_\_reversed_\_() → [collections.abc.Iterator](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### append(item: algopy._TArrayItem, /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Return a copy of the array with a another value appended to the end

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Returns the current length of the array

#### pop() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Return a copy of this array with the last item removed

#### replace(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy._TArrayItem) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Returns a copy of the array with the item at specified index replaced with the specified value

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.ImmutableFixedArray(values: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy._TArrayItem])

An immutable fixed length Array of the specified type and length

### Initialization

#### \_\_getitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy._TArrayItem

Gets the item of the array at the provided index

#### \_\_iter_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array

#### \_\_reversed_\_() → [Iterator](https://docs.python.org/3/library/typing.html#typing.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### *classmethod* full(item: algopy._TArrayItem) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Initializes a new array, filled with copies of the specified value

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Returns the (compile-time) length of the array

#### replace(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy._TArrayItem) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Returns a copy of the array with the item at the specified index replaced with the specified value

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### *class* algopy.LocalState(type_: [type](https://docs.python.org/3/library/functions.html#type)[algopy._TState], /, \*, key: [algopy.String](#algopy.String) | [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., description: [str](https://docs.python.org/3/library/stdtypes.html#str) = '')

Local state associated with the application and an account

### Initialization

Declare the local state key and it’s associated type

```python
self.names = LocalState(algopy.Bytes)
```

#### \_\_contains_\_(account: [algopy.Account](#algopy.Account) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Can test if data exists by using an `Account` reference or foreign account index

```python
assert account in self.names
```

#### \_\_delitem_\_(account: [algopy.Account](#algopy.Account) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [None](https://docs.python.org/3/library/constants.html#None)

Data can be removed by using an `Account` reference or foreign account index

```python
del self.names[account]
```

#### \_\_getitem_\_(account: [algopy.Account](#algopy.Account) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy._TState

Data can be accessed by an `Account` reference or foreign account index

```python
account_name = self.names[account]
```

#### \_\_setitem_\_(account: [algopy.Account](#algopy.Account) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy._TState) → [None](https://docs.python.org/3/library/constants.html#None)

Data can be stored by using an `Account` reference or foreign account index

```python
self.names[account] = account_name
```

#### get(account: [algopy.Account](#algopy.Account) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), default: algopy._TState) → algopy._TState

Can retrieve value using an `Account` reference or foreign account index,
and a fallback default value.

```python
name = self.names.get(account, Bytes(b"no name")
```

#### *property* key *: [algopy.Bytes](#algopy.Bytes)*

Provides access to the raw storage key

#### maybe(account: [algopy.Account](#algopy.Account) | [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[algopy._TState, [bool](https://docs.python.org/3/library/functions.html#bool)]

Can retrieve value, and a bool indicating if the value was present
using an `Account` reference or foreign account index.

```python
name, name_exists = self.names.maybe(account)
if not name_exists:
    name = Bytes(b"no name")
```

### *class* algopy.LogicSig

A logic signature

### *class* algopy.OnCompleteAction(value: [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

On Completion actions available in an application call transaction

### Initialization

A UInt64 can be initialized with a Python int literal, or an int variable
declared at the module level

#### ClearState *: [algopy.OnCompleteAction](#algopy.OnCompleteAction)*

Ellipsis

ClearState is similar to CloseOut, but may never fail. This
allows users to reclaim their minimum balance from an application
they no longer wish to opt in to.

#### CloseOut *: [algopy.OnCompleteAction](#algopy.OnCompleteAction)*

Ellipsis

CloseOut indicates that an application transaction will deallocate
some LocalState for the application from the user’s account

#### DeleteApplication *: [algopy.OnCompleteAction](#algopy.OnCompleteAction)*

Ellipsis

DeleteApplication indicates that an application transaction will
delete the AppParams for the application from the creator’s balance
record

#### NoOp *: [algopy.OnCompleteAction](#algopy.OnCompleteAction)*

Ellipsis

NoOP indicates that no additional action is performed when the transaction completes

#### OptIn *: [algopy.OnCompleteAction](#algopy.OnCompleteAction)*

Ellipsis

OptIn indicates that an application transaction will allocate some
LocalState for the application in the sender’s account

#### UpdateApplication *: [algopy.OnCompleteAction](#algopy.OnCompleteAction)*

Ellipsis

UpdateApplication indicates that an application transaction will
update the ApprovalProgram and ClearStateProgram for the application

#### \_\_add_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `UInt(4) + 2`.

This will error on overflow

#### \_\_and_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `UInt64(4) & 2`

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 will evaluate to `False` if zero, and `True` otherwise

#### \_\_eq_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `==` operator with another UInt64 or int

#### \_\_floordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `UInt64(4) // 2`.

This will error on divide by zero

#### \_\_ge_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>=` operator with another UInt64 or int

#### \_\_gt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>` operator with another UInt64 or int

#### \_\_iadd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be incremented with another UInt64 or int e.g. `a += UInt(2)`.

This will error on overflow

#### \_\_iand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `a &= UInt64(2)`

#### \_\_ifloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `a //= UInt64(2)`.

This will error on divide by zero

#### \_\_ilshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `a <<= UInt64(2)`

#### \_\_imod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `a %= UInt64(2)`.

This will error on mod by zero

#### \_\_imul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `a*= UInt64(2)`.

This will error on overflow

#### \_\_index_\_() → [int](https://docs.python.org/3/library/functions.html#int)

A UInt64 can be used in indexing/slice expressions

#### \_\_invert_\_() → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be bitwise inverted e.g. `~UInt64(4)`

#### \_\_ior_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `a |= UInt64(2)`

#### \_\_ipow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `a **= UInt64(2)`.

This will error on overflow

#### \_\_irshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `a >>= UInt64(2)`

#### \_\_isub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `a -= UInt64(2)`.

This will error on underflow

#### \_\_ixor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `a ^= UInt64(2)`

#### \_\_le_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<=` operator with another UInt64 or int

#### \_\_lshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `UInt64(4) << 2`

#### \_\_lt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<` operator with another UInt64 or int

#### \_\_mod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `UInt64(4) % 2`.

This will error on mod by zero

#### \_\_mul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_ne_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `!=` operator with another UInt64 or int

#### \_\_or_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `UInt64(4) | 2`

#### \_\_pos_\_() → [algopy.UInt64](#algopy.UInt64)

Supports unary + operator. Redundant given the type is unsigned

#### \_\_pow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `UInt64(4) ** 2`.

This will error on overflow

#### \_\_radd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_rand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `4 & UInt64(2)`

#### \_\_rfloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `4 // UInt64(2)`.

This will error on divide by zero

#### \_\_rlshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `4 << UInt64(2)`

#### \_\_rmod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `4 % UInt64(2)`.

This will error on mod by zero

#### \_\_rmul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `UInt64(4) + 2`.

This will error on overflow

#### \_\_ror_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `4 | UInt64(2)`

#### \_\_rpow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `4 ** UInt64(2)`.

This will error on overflow

#### \_\_rrshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `4 >> UInt64(2)`

#### \_\_rshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `UInt64(4) >> 2`

#### \_\_rsub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `4 - UInt64(2)`.

This will error on underflow

#### \_\_rxor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `4 ^ UInt64(2)`

#### \_\_sub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `UInt(4) - 2`.

This will error on underflow

#### \_\_xor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `UInt64(4) ^ 2`

### *class* algopy.OpUpFeeSource(value: [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

Defines the source of fees for the OpUp utility.

### Initialization

A UInt64 can be initialized with a Python int literal, or an int variable
declared at the module level

#### Any *: [algopy.OpUpFeeSource](#algopy.OpUpFeeSource)*

Ellipsis

First the excess will be used, remaining fees will be taken from the app account

#### AppAccount *: [algopy.OpUpFeeSource](#algopy.OpUpFeeSource)*

Ellipsis

The app’s account will cover all fees (set inner_tx.fee=Global.min_tx_fee())

#### GroupCredit *: [algopy.OpUpFeeSource](#algopy.OpUpFeeSource)*

Ellipsis

Only the excess fee (credit) on the outer group should be used (set inner_tx.fee=0)

#### \_\_add_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `UInt(4) + 2`.

This will error on overflow

#### \_\_and_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `UInt64(4) & 2`

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 will evaluate to `False` if zero, and `True` otherwise

#### \_\_eq_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `==` operator with another UInt64 or int

#### \_\_floordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `UInt64(4) // 2`.

This will error on divide by zero

#### \_\_ge_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>=` operator with another UInt64 or int

#### \_\_gt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>` operator with another UInt64 or int

#### \_\_iadd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be incremented with another UInt64 or int e.g. `a += UInt(2)`.

This will error on overflow

#### \_\_iand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `a &= UInt64(2)`

#### \_\_ifloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `a //= UInt64(2)`.

This will error on divide by zero

#### \_\_ilshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `a <<= UInt64(2)`

#### \_\_imod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `a %= UInt64(2)`.

This will error on mod by zero

#### \_\_imul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `a*= UInt64(2)`.

This will error on overflow

#### \_\_index_\_() → [int](https://docs.python.org/3/library/functions.html#int)

A UInt64 can be used in indexing/slice expressions

#### \_\_invert_\_() → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be bitwise inverted e.g. `~UInt64(4)`

#### \_\_ior_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `a |= UInt64(2)`

#### \_\_ipow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `a **= UInt64(2)`.

This will error on overflow

#### \_\_irshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `a >>= UInt64(2)`

#### \_\_isub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `a -= UInt64(2)`.

This will error on underflow

#### \_\_ixor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `a ^= UInt64(2)`

#### \_\_le_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<=` operator with another UInt64 or int

#### \_\_lshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `UInt64(4) << 2`

#### \_\_lt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<` operator with another UInt64 or int

#### \_\_mod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `UInt64(4) % 2`.

This will error on mod by zero

#### \_\_mul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_ne_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `!=` operator with another UInt64 or int

#### \_\_or_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `UInt64(4) | 2`

#### \_\_pos_\_() → [algopy.UInt64](#algopy.UInt64)

Supports unary + operator. Redundant given the type is unsigned

#### \_\_pow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `UInt64(4) ** 2`.

This will error on overflow

#### \_\_radd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_rand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `4 & UInt64(2)`

#### \_\_rfloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `4 // UInt64(2)`.

This will error on divide by zero

#### \_\_rlshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `4 << UInt64(2)`

#### \_\_rmod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `4 % UInt64(2)`.

This will error on mod by zero

#### \_\_rmul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `UInt64(4) + 2`.

This will error on overflow

#### \_\_ror_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `4 | UInt64(2)`

#### \_\_rpow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `4 ** UInt64(2)`.

This will error on overflow

#### \_\_rrshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `4 >> UInt64(2)`

#### \_\_rshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `UInt64(4) >> 2`

#### \_\_rsub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `4 - UInt64(2)`.

This will error on underflow

#### \_\_rxor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `4 ^ UInt64(2)`

#### \_\_sub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `UInt(4) - 2`.

This will error on underflow

#### \_\_xor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `UInt64(4) ^ 2`

### *class* algopy.ReferenceArray

A mutable array that supports fixed sized immutable elements. All references to this array
will see any updates made to it.

These arrays may use scratch slots if required. If a contract also needs to use scratch slots
for other purposes then they should be reserved using the `scratch_slots` parameter
in [`algopy.Contract`](#algopy.Contract),
[`algopy.arc4.ARC4Contract`](api-algopy.arc4.md#algopy.arc4.ARC4Contract) or [`algopy.logicsig`](#algopy.logicsig)

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if not an empty array

#### \_\_getitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → algopy._TArrayItem

Gets the item of the array at provided index

#### \_\_iter_\_() → [collections.abc.Iterator](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array

#### \_\_reversed_\_() → [collections.abc.Iterator](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[algopy._TArrayItem]

Returns an iterator for the items in the array, in reverse order

#### \_\_setitem_\_(index: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), value: algopy._TArrayItem) → algopy._TArrayItem

Sets the item of the array at specified index to provided value

#### append(item: algopy._TArrayItem, /) → [None](https://docs.python.org/3/library/constants.html#None)

Append an item to this array

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this array

#### extend(other: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy._TArrayItem], /) → [None](https://docs.python.org/3/library/constants.html#None)

Extend this array with the contents of another array

#### freeze() → [algopy.ImmutableArray](#algopy.ImmutableArray)[algopy._TArrayItem]

Returns an immutable copy of this array

#### *property* length *: [algopy.UInt64](#algopy.UInt64)*

Returns the current length of the array

#### pop() → algopy._TArrayItem

Remove and return the last item of this array

### *class* algopy.StateTotals(\*, global_uints: [int](https://docs.python.org/3/library/functions.html#int) = ..., global_bytes: [int](https://docs.python.org/3/library/functions.html#int) = ..., local_uints: [int](https://docs.python.org/3/library/functions.html#int) = ..., local_bytes: [int](https://docs.python.org/3/library/functions.html#int) = ...)

Options class to manually define the total amount of global and local state contract will use,
used by [`Contract.__init_subclass__`](#algopy.Contract.__init_subclass__).

This is not required when all state is assigned to `self.`, but is required if a
contract dynamically interacts with state via `AppGlobal.get_bytes` etc, or if you want
to reserve additional state storage for future contract updates, since the Algorand protocol
doesn’t allow increasing them after creation.

### Initialization

Specify the totals for both global and local, and for each type. Any arguments not
specified default to their automatically calculated values.

Values are validated against the known totals assigned through `self.`, a warning is
produced if the total specified is insufficient to accommodate all `self.` state values
at once.

### *class* algopy.String(value: [str](https://docs.python.org/3/library/stdtypes.html#str) = '', /)

A UTF-8 encoded string.

In comparison to `arc4.String`, this type does not store the array length prefix, since that
information is always available through the `len` AVM op. This makes it more efficient to
operate on when doing operations such as concatenation.

Note that due to the lack of UTF-8 support in the AVM, indexing and length operations are not
currently supported.

### Initialization

A String can be initialized with a Python `str` literal, or a `str` variable
declared at the module level

#### \_\_add_\_(other: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [algopy.String](#algopy.String)

Concatenate `String` with another `String` or `str` literal
e.g. `String("Hello ") + "World"`.

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

Returns `True` if the string is not empty

#### \_\_contains_\_(other: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Test whether another string is a substring of this one.
Note this is expensive due to a lack of AVM support.

#### \_\_eq_\_(other: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Supports using the `==` operator with another `String` or literal `str`

#### \_\_iadd_\_(other: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [algopy.String](#algopy.String)

Concatenate `String` with another `String` or `str` literal
e.g. `a = String("Hello"); a += "World"`.

#### \_\_ne_\_(other: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Supports using the `!=` operator with another `String` or literal `str`

#### \_\_radd_\_(other: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [algopy.String](#algopy.String)

Concatenate String with another `String` or `str` literal
e.g. `"Hello " + String("World")`.

#### *property* bytes *: [algopy.Bytes](#algopy.Bytes)*

Get the underlying Bytes

#### endswith(suffix: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Check if this string ends with another string.

The behaviour should mirror `str.endswith`, for example, if `suffix` is the empty string,
the result will always be `True`.

Only a single argument is currently supported.

#### *classmethod* from_bytes(value: [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Construct an instance from the underlying bytes (no validation)

#### join(others: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str), ...], /) → [algopy.String](#algopy.String)

Join a sequence of Strings with a common separator.

The behaviour should mirror `str.join`.

#### startswith(prefix: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str)) → [bool](https://docs.python.org/3/library/functions.html#bool)

Check if this string starts with another string.

The behaviour should mirror `str.startswith`, for example, if `prefix` is the empty string,
the result will always be `True`.

Only a single argument is currently supported.

### *class* algopy.Struct

Base class for Struct types

#### \_replace(\*\*kwargs: [Any](https://docs.python.org/3/library/typing.html#typing.Any)) → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Return a new instance of the struct replacing specified fields with new values.

Note that any mutable fields must be explicitly copied to avoid aliasing.

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Create a copy of this struct

#### validate() → [None](https://docs.python.org/3/library/constants.html#None)

Performs validation to ensure the value is well-formed, errors if it is not

### algopy.TemplateVar *: algopy._TemplateVarGeneric*

Ellipsis

Template variables can be used to represent a placeholder for a deploy-time provided value.

### *class* algopy.TransactionType(value: [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

The different transaction types available in a transaction

### Initialization

A UInt64 can be initialized with a Python int literal, or an int variable
declared at the module level

#### ApplicationCall *: [algopy.TransactionType](#algopy.TransactionType)*

Ellipsis

An Application Call transaction

#### AssetConfig *: [algopy.TransactionType](#algopy.TransactionType)*

Ellipsis

An Asset Config transaction

#### AssetFreeze *: [algopy.TransactionType](#algopy.TransactionType)*

Ellipsis

An Asset Freeze transaction

#### AssetTransfer *: [algopy.TransactionType](#algopy.TransactionType)*

Ellipsis

An Asset Transfer transaction

#### KeyRegistration *: [algopy.TransactionType](#algopy.TransactionType)*

Ellipsis

A Key Registration transaction

#### Payment *: [algopy.TransactionType](#algopy.TransactionType)*

Ellipsis

A Payment transaction

#### \_\_add_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `UInt(4) + 2`.

This will error on overflow

#### \_\_and_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `UInt64(4) & 2`

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 will evaluate to `False` if zero, and `True` otherwise

#### \_\_eq_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `==` operator with another UInt64 or int

#### \_\_floordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `UInt64(4) // 2`.

This will error on divide by zero

#### \_\_ge_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>=` operator with another UInt64 or int

#### \_\_gt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>` operator with another UInt64 or int

#### \_\_iadd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be incremented with another UInt64 or int e.g. `a += UInt(2)`.

This will error on overflow

#### \_\_iand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `a &= UInt64(2)`

#### \_\_ifloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `a //= UInt64(2)`.

This will error on divide by zero

#### \_\_ilshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `a <<= UInt64(2)`

#### \_\_imod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `a %= UInt64(2)`.

This will error on mod by zero

#### \_\_imul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `a*= UInt64(2)`.

This will error on overflow

#### \_\_index_\_() → [int](https://docs.python.org/3/library/functions.html#int)

A UInt64 can be used in indexing/slice expressions

#### \_\_invert_\_() → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be bitwise inverted e.g. `~UInt64(4)`

#### \_\_ior_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `a |= UInt64(2)`

#### \_\_ipow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `a **= UInt64(2)`.

This will error on overflow

#### \_\_irshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `a >>= UInt64(2)`

#### \_\_isub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `a -= UInt64(2)`.

This will error on underflow

#### \_\_ixor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `a ^= UInt64(2)`

#### \_\_le_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<=` operator with another UInt64 or int

#### \_\_lshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `UInt64(4) << 2`

#### \_\_lt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<` operator with another UInt64 or int

#### \_\_mod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `UInt64(4) % 2`.

This will error on mod by zero

#### \_\_mul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_ne_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `!=` operator with another UInt64 or int

#### \_\_or_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `UInt64(4) | 2`

#### \_\_pos_\_() → [algopy.UInt64](#algopy.UInt64)

Supports unary + operator. Redundant given the type is unsigned

#### \_\_pow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `UInt64(4) ** 2`.

This will error on overflow

#### \_\_radd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_rand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `4 & UInt64(2)`

#### \_\_rfloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `4 // UInt64(2)`.

This will error on divide by zero

#### \_\_rlshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `4 << UInt64(2)`

#### \_\_rmod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `4 % UInt64(2)`.

This will error on mod by zero

#### \_\_rmul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `UInt64(4) + 2`.

This will error on overflow

#### \_\_ror_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `4 | UInt64(2)`

#### \_\_rpow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `4 ** UInt64(2)`.

This will error on overflow

#### \_\_rrshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `4 >> UInt64(2)`

#### \_\_rshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `UInt64(4) >> 2`

#### \_\_rsub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `4 - UInt64(2)`.

This will error on underflow

#### \_\_rxor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `4 ^ UInt64(2)`

#### \_\_sub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `UInt(4) - 2`.

This will error on underflow

#### \_\_xor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `UInt64(4) ^ 2`

### *class* algopy.Txn

Get values for the current executing transaction
Native TEAL ops: [`txn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txn), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### *static* accounts(a: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](#algopy.Account)

Accounts listed in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### amount *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

microalgos

#### *static* application_args(a: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](#algopy.Bytes)

Arguments passed to the application in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Application](#algopy.Application)]*

Ellipsis

ApplicationID from ApplicationCall transaction

#### *static* applications(a: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](#algopy.Application)

Foreign Apps listed in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### approval_program *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

Approval program

#### *static* approval_program_pages(a: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](#algopy.Bytes)

Approval Program as an array of pages

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### asset_amount *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

value in Asset’s units

#### asset_close_to *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### asset_receiver *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### asset_sender *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address. Source of assets if Sender is the Asset’s Clawback address.

#### *static* assets(a: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](#algopy.Asset)

Foreign Assets listed in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### clear_state_program *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

Clear state program

#### *static* clear_state_program_pages(a: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](#algopy.Bytes)

ClearState Program as an array of pages

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### close_remainder_to *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### config_asset *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](#algopy.Asset)]*

Ellipsis

Asset ID in asset config transaction

#### config_asset_clawback *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### config_asset_decimals *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of digits to display after the decimal place when displaying the asset

#### config_asset_default_frozen *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]*

Ellipsis

Whether the asset’s slots are frozen by default or not, 0 or 1

#### config_asset_freeze *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### config_asset_manager *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### config_asset_metadata_hash *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

32 byte commitment to unspecified asset metadata

#### config_asset_name *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

The asset name

#### config_asset_reserve *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### config_asset_total *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Total number of units of this asset created

#### config_asset_unit_name *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

Unit name of the asset

#### config_asset_url *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

URL

#### created_application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Application](#algopy.Application)]*

Ellipsis

ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

#### created_asset_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](#algopy.Asset)]*

Ellipsis

Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

#### extra_program_pages *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

#### fee *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

microalgos

#### first_valid *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

round number

#### first_valid_time *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### freeze_asset *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](#algopy.Asset)]*

Ellipsis

Asset ID being frozen or un-frozen

#### freeze_asset_account *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address of the account whose asset slot is being frozen or un-frozen

#### freeze_asset_frozen *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]*

Ellipsis

The new frozen value, 0 or 1

#### global_num_byte_slice *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of global state byteslices in ApplicationCall

#### global_num_uint *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of global state integers in ApplicationCall

#### group_index *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

#### last_log *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

The last message emitted. Empty bytes if none were emitted. Application mode only

#### last_valid *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

round number

#### lease *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

32 byte lease value

#### local_num_byte_slice *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of local state byteslices in ApplicationCall

#### local_num_uint *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of local state integers in ApplicationCall

#### *static* logs(a: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](#algopy.Bytes)

Log messages emitted by an application call (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

#### nonparticipation *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]*

Ellipsis

Marks an account nonparticipating for rewards

#### note *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

Any data up to 1024 bytes

#### num_accounts *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of Accounts

#### num_app_args *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of ApplicationArgs

#### num_applications *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of Applications

#### num_approval_program_pages *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of Approval Program pages

#### num_assets *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of Assets

#### num_clear_state_program_pages *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of ClearState Program pages

#### num_logs *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Number of Logs (only with `itxn` in v5). Application mode only

#### on_completion *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.OnCompleteAction](#algopy.OnCompleteAction)]*

Ellipsis

ApplicationCall transaction on completion action

#### receiver *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### reject_version *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Application version for which the txn must reject
Min AVM version: 12

#### rekey_to *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte Sender’s new AuthAddr

#### selection_pk *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

32 byte address

#### sender *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](#algopy.Account)]*

Ellipsis

32 byte address

#### state_proof_pk *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

State proof public key

#### tx_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

The computed ID for this transaction. 32 bytes.

#### type *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

Transaction type as bytes

#### type_enum *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.TransactionType](#algopy.TransactionType)]*

Ellipsis

Transaction type as integer

#### vote_first *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The first round that the participation key is valid.

#### vote_key_dilution *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

Dilution for the 2-level participation key

#### vote_last *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](#algopy.UInt64)]*

Ellipsis

The last round that the participation key is valid.

#### vote_pk *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](#algopy.Bytes)]*

Ellipsis

32 byte address

#### xfer_asset *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](#algopy.Asset)]*

Ellipsis

Asset ID

### *class* algopy.UInt64(value: [int](https://docs.python.org/3/library/functions.html#int) = 0, /)

A 64-bit unsigned integer, one of the primary data types on the AVM

### Initialization

A UInt64 can be initialized with a Python int literal, or an int variable
declared at the module level

#### \_\_add_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `UInt(4) + 2`.

This will error on overflow

#### \_\_and_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `UInt64(4) & 2`

#### \_\_bool_\_() → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 will evaluate to `False` if zero, and `True` otherwise

#### \_\_eq_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `==` operator with another UInt64 or int

#### \_\_floordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `UInt64(4) // 2`.

This will error on divide by zero

#### \_\_ge_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>=` operator with another UInt64 or int

#### \_\_gt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `>` operator with another UInt64 or int

#### \_\_iadd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be incremented with another UInt64 or int e.g. `a += UInt(2)`.

This will error on overflow

#### \_\_iand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `a &= UInt64(2)`

#### \_\_ifloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `a //= UInt64(2)`.

This will error on divide by zero

#### \_\_ilshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `a <<= UInt64(2)`

#### \_\_imod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `a %= UInt64(2)`.

This will error on mod by zero

#### \_\_imul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `a*= UInt64(2)`.

This will error on overflow

#### \_\_index_\_() → [int](https://docs.python.org/3/library/functions.html#int)

A UInt64 can be used in indexing/slice expressions

#### \_\_invert_\_() → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be bitwise inverted e.g. `~UInt64(4)`

#### \_\_ior_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `a |= UInt64(2)`

#### \_\_ipow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `a **= UInt64(2)`.

This will error on overflow

#### \_\_irshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `a >>= UInt64(2)`

#### \_\_isub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `a -= UInt64(2)`.

This will error on underflow

#### \_\_ixor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `a ^= UInt64(2)`

#### \_\_le_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<=` operator with another UInt64 or int

#### \_\_lshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `UInt64(4) << 2`

#### \_\_lt_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `<` operator with another UInt64 or int

#### \_\_mod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `UInt64(4) % 2`.

This will error on mod by zero

#### \_\_mul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_ne_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [bool](https://docs.python.org/3/library/functions.html#bool)

A UInt64 can use the `!=` operator with another UInt64 or int

#### \_\_or_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `UInt64(4) | 2`

#### \_\_pos_\_() → [algopy.UInt64](#algopy.UInt64)

Supports unary + operator. Redundant given the type is unsigned

#### \_\_pow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `UInt64(4) ** 2`.

This will error on overflow

#### \_\_radd_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be added with another UInt64 or int e.g. `4 + UInt64(2)`.

This will error on overflow

#### \_\_rand_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise and with another UInt64 or int e.g. `4 & UInt64(2)`

#### \_\_rfloordiv_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be floor divided with another UInt64 or int e.g. `4 // UInt64(2)`.

This will error on divide by zero

#### \_\_rlshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be left shifted by another UInt64 or int e.g. `4 << UInt64(2)`

#### \_\_rmod_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be modded with another UInt64 or int e.g. `4 % UInt64(2)`.

This will error on mod by zero

#### \_\_rmul_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be multiplied with another UInt64 or int e.g. `UInt64(4) + 2`.

This will error on overflow

#### \_\_ror_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise or with another UInt64 or int e.g. `4 | UInt64(2)`

#### \_\_rpow_\_(power: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be raised to the power of another UInt64 or int e.g. `4 ** UInt64(2)`.

This will error on overflow

#### \_\_rrshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `4 >> UInt64(2)`

#### \_\_rshift_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be right shifted by another UInt64 or int e.g. `UInt64(4) >> 2`

#### \_\_rsub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `4 - UInt64(2)`.

This will error on underflow

#### \_\_rxor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `4 ^ UInt64(2)`

#### \_\_sub_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can be subtracted with another UInt64 or int e.g. `UInt(4) - 2`.

This will error on underflow

#### \_\_xor_\_(other: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.UInt64](#algopy.UInt64)

A UInt64 can bitwise xor with another UInt64 or int e.g. `UInt64(4) ^ 2`

### algopy.compile_contract(contract: [type](https://docs.python.org/3/library/functions.html#type)[[Contract](#algopy.Contract)], /, \*, extra_program_pages: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_uints: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_bytes: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_uints: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_bytes: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., template_vars: [collections.abc.Mapping](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[str](https://docs.python.org/3/library/stdtypes.html#str), [object](https://docs.python.org/3/library/functions.html#object)] = ..., template_vars_prefix: [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [algopy.CompiledContract](#algopy.CompiledContract)

Returns the compiled data for the specified contract

* **Parameters:**
  * **contract** – Algorand Python Contract to compile
  * **extra_program_pages** – Number of extra program pages, defaults to minimum required for contract
  * **global_uints** – Number of global uint64s, defaults to value defined for contract
  * **global_bytes** – Number of global bytes, defaults to value defined for contract
  * **local_uints** – Number of local uint64s, defaults to value defined for contract
  * **local_bytes** – Number of local bytes, defaults to value defined for contract
  * **template_vars** – Template variables to substitute into the contract,
    key should be without the prefix, must evaluate to a compile time constant
    and match the type of the template var declaration
  * **template_vars_prefix** – Prefix to add to provided template vars,
    defaults to the prefix supplied on command line (which defaults to TMPL_)

### algopy.compile_logicsig(logicsig: [LogicSig](#algopy.LogicSig), /, \*, template_vars: [collections.abc.Mapping](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[str](https://docs.python.org/3/library/stdtypes.html#str), [object](https://docs.python.org/3/library/functions.html#object)] = ..., template_vars_prefix: [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [algopy.CompiledLogicSig](#algopy.CompiledLogicSig)

Returns the Account for the specified logic signature

* **Parameters:**
  * **logicsig** – Algorand Python Logic Signature to compile
  * **template_vars** – Template variables to substitute into the logic signature,
    key should be without the prefix, must evaluate to a compile time constant
    and match the type of the template var declaration
  * **template_vars_prefix** – Prefix to add to provided template vars,
    defaults to the prefix supplied on command line (which defaults to TMPL_)

### algopy.ensure_budget(required_budget: [algopy.UInt64](#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), fee_source: [algopy.OpUpFeeSource](#algopy.OpUpFeeSource) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Ensure the available op code budget is greater than or equal to required_budget

### algopy.log(\*args: [object](https://docs.python.org/3/library/functions.html#object), sep: [algopy.String](#algopy.String) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [algopy.Bytes](#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = '') → [None](https://docs.python.org/3/library/constants.html#None)

Concatenates and logs supplied args as a single bytes value.

UInt64 args are converted to bytes and each argument is separated by `sep`.
Literal `str` values will be encoded as UTF8.

### algopy.logicsig(\*, name: [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., avm_version: [int](https://docs.python.org/3/library/functions.html#int) = ..., scratch_slots: [algopy.urange](#algopy.urange) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](#algopy.urange), ...] | [list](https://docs.python.org/3/library/stdtypes.html#list)[[int](https://docs.python.org/3/library/functions.html#int) | [algopy.urange](#algopy.urange)] = ()) → [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[], [bool](https://docs.python.org/3/library/functions.html#bool) | [algopy.UInt64](#algopy.UInt64)]], [algopy.LogicSig](#algopy.LogicSig)]

Decorator to indicate a function is a logic signature

### algopy.size_of(type_or_expression: [type](https://docs.python.org/3/library/functions.html#type) | [object](https://docs.python.org/3/library/functions.html#object), /) → [algopy.UInt64](#algopy.UInt64)

Returns the number of bytes required to store the provided type object
or the type of provided expression

### algopy.subroutine(\*, inline: [bool](https://docs.python.org/3/library/functions.html#bool) | [Literal](https://docs.python.org/3/library/typing.html#typing.Literal)[auto] = 'auto') → [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[algopy._P, algopy._R]], [collections.abc.Callable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[algopy._P, algopy._R]]

Decorator to indicate functions or methods that can be called by a Smart Contract

Inlining can be controlled with the decorator argument `inline`.
When unspecified it defaults to auto, which allows the optimizer to decide whether to inline
or not. Setting `inline=True` forces inlining, and `inline=False` ensures the function will
never be inlined.

### *class* algopy.uenumerate(iterable: [collections.abc.Iterable](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[algopy._T])

Yields pairs containing a count (from zero) and a value yielded by the iterable argument.

enumerate is useful for obtaining an indexed list:
(0, seq[0]), (1, seq[1]), (2, seq[2]), …

enumerate((a, b, c)) produces (0, a), (1, b), (2, c)

### Initialization

### *class* algopy.urange

Produces a sequence of UInt64 from start (inclusive) to stop (exclusive) by step.

urange(4) produces 0, 1, 2, 3
urange(i, j) produces i, i+1, i+2, …, j-1.
urange(i, j, 2) produces i, i+2, i+4, …, i+2n where n is the largest value where i+2n < j

### algopy.zero_bytes(typ: [type](https://docs.python.org/3/library/functions.html#type)[algopy.zero_bytes.T]) → algopy.zero_bytes.T

Initializes a new value of the specified type, based on it’s zero bytes representation.

Only works for fixed size types that are bytes encoded.
