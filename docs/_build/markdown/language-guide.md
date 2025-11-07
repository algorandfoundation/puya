# Language Guide

Algorand Python is conceptually two things:

1. A partial implementation of the Python programming language that runs on the AVM.
2. A framework for development of Algorand smart contracts and logic signatures, with Pythonic
   interfaces to underlying AVM functionality.

You can install the Algorand Python types from PyPi:

> `pip install algorand-python`

or

> `poetry add algorand-python`

---

As a partial implementation of the Python programming language, it maintains the syntax and
semantics of Python. The subset of the language that is supported will grow over time, but it will
never be a complete implementation due to the restricted nature of the AVM as an execution
environment. As a trivial example, the `async` and `await` keywords, and all associated features,
do not make sense to implement.

Being a partial implementation of Python means that existing developer tooling like IDE syntax
highlighting, static type checkers, linters, and auto-formatters, will work out-of-the-box. This is
as opposed to an approach to smart contract development that adds or alters language elements or
semantics, which then requires custom developer tooling support, and more importantly, requires the
developer to learn and understand the potentially non-obvious differences from regular Python.

The greatest advantage to maintaining semantic and syntactic compatibility, however, is only
realised in combination with the framework approach. Supplying a set of interfaces representing
smart contract development and AVM functionality required allows for the possibility of
implementing those interfaces in pure Python! This will make it possible in the near future for you
to execute tests against your smart contracts without deploying them to Algorand, and even step
into and break-point debug your code from those tests.

The framework provides interfaces to the underlying AVM types and operations. By virtue of the AVM
being statically typed, these interfaces are also statically typed, and require your code to be as
well.

The most basic types on the AVM are `uint64` and `bytes[]`, representing unsigned 64-bit integers
and byte arrays respectively. These are represented by [`UInt64`](api-algopy.md#algopy.UInt64) and
[`Bytes`](api-algopy.md#algopy.Bytes) in Algorand Python. There are further “bounded” types supported by the AVM
which are backed by these two simple primitives. For example, `bigint` represents a variably sized
(up to 512-bits), unsigned integer, but is actually backed by a `bytes[]`. This is represented by
[`BigUInt`](api-algopy.md#algopy.BigUInt) in Algorand Python.

Unfortunately, none of these types map to standard Python primitives. In Python, an `int` is
unsigned, and effectively unbounded. A `bytes` similarly is limited only by the memory available,
whereas an AVM `bytes[]` has a maximum length of 4096. In order to both maintain semantic
compatibility and allow for a framework implementation in plain Python that will fail under the
same conditions as when deployed to the AVM, support for Python primitives is
[limited](lg-types.md#python-built-in-types).

For more information on the philosophy and design of Algorand Python, please see
[“Principles”](principles.md#principles).

If you aren’t familiar with Python, a good place to start before continuing below is with the
[official tutorial](https://docs.python.org/3/tutorial/index.html). Just beware that as mentioned
above, [not all features are supported](lg-unsupported-python-features.md).

## Table of Contents

* [Program structure](lg-structure.md)
  * [Modules](lg-structure.md#modules)
  * [Typing](lg-structure.md#typing)
  * [Subroutines](lg-structure.md#subroutines)
  * [Contract classes](lg-structure.md#contract-classes)
    * [Contract class configuration](lg-structure.md#contract-class-configuration)
    * [Example: Simplest possible `algopy.Contract` implementation](lg-structure.md#example-simplest-possible-algopy-contract-implementation)
    * [Example: Simple call counter](lg-structure.md#example-simple-call-counter)
    * [Example: Simplest possible `algopy.ARC4Contract` implementation](lg-structure.md#example-simplest-possible-algopy-arc4contract-implementation)
    * [Example: An ARC-4 call counter](lg-structure.md#example-an-arc-4-call-counter)
  * [Logic signatures](lg-structure.md#logic-signatures)
* [Types](lg-types.md)
  * [AVM types](lg-types.md#avm-types)
    * [UInt64](lg-types.md#uint64)
    * [Bytes](lg-types.md#bytes)
    * [String](lg-types.md#string)
    * [BigUInt](lg-types.md#biguint)
    * [bool](lg-types.md#bool)
    * [Account](lg-types.md#account)
    * [Asset](lg-types.md#asset)
    * [Application](lg-types.md#application)
  * [Python built-in types](lg-types.md#python-built-in-types)
    * [bool](lg-types.md#id2)
    * [tuple](lg-types.md#tuple)
    * [typing.NamedTuple](lg-types.md#typing-namedtuple)
    * [None](lg-types.md#none)
    * [int, str, bytes, float](lg-types.md#int-str-bytes-float)
  * [Template variables](lg-types.md#template-variables)
  * [ARC-4 types](lg-types.md#arc-4-types)
  * [Type Validation](lg-types.md#type-validation)
    * [Validated Sources of Values](lg-types.md#validated-sources-of-values)
    * [Non-Validated Sources](lg-types.md#non-validated-sources)
* [Control flow structures](lg-control.md)
  * [If statements](lg-control.md#if-statements)
  * [Ternary conditions](lg-control.md#ternary-conditions)
  * [While loops](lg-control.md#while-loops)
  * [For Loops](lg-control.md#for-loops)
  * [Match Statements](lg-control.md#match-statements)
* [Module level constructs](lg-modules.md)
  * [Module constants](lg-modules.md#module-constants)
  * [If statements](lg-modules.md#if-statements)
  * [Integer math](lg-modules.md#integer-math)
  * [Strings](lg-modules.md#strings)
  * [Type aliases](lg-modules.md#type-aliases)
* [Python builtins](lg-builtins.md)
  * [len](lg-builtins.md#len)
  * [range](lg-builtins.md#range)
  * [enumerate](lg-builtins.md#enumerate)
  * [reversed](lg-builtins.md#reversed)
  * [types](lg-builtins.md#types)
* [Error handling and assertions](lg-errors.md)
  * [Assertions](lg-errors.md#assertions)
    * [Assertion error handling](lg-errors.md#assertion-error-handling)
  * [Explicit failure](lg-errors.md#explicit-failure)
  * [Exception handling](lg-errors.md#exception-handling)
* [Data structures](lg-data-structures.md)
  * [Mutability vs Immutability](lg-data-structures.md#mutability-vs-immutability)
  * [Static size vs Dynamic size](lg-data-structures.md#static-size-vs-dynamic-size)
  * [Size constraints](lg-data-structures.md#size-constraints)
  * [Algorand Python composite types](lg-data-structures.md#algorand-python-composite-types)
    * [`tuple`](lg-data-structures.md#tuple)
    * [`typing.NamedTuple`](lg-data-structures.md#typing-namedtuple)
    * [`Struct`](lg-data-structures.md#struct)
    * [`arc4.Tuple`](lg-data-structures.md#arc4-tuple)
    * [`arc4.Struct`](lg-data-structures.md#arc4-struct)
  * [Algorand Python array types](lg-data-structures.md#algorand-python-array-types)
    * [`algopy.FixedArray`](lg-data-structures.md#algopy-fixedarray)
    * [`algopy.Array`](lg-data-structures.md#algopy-array)
    * [`algopy.ReferenceArray`](lg-data-structures.md#algopy-referencearray)
    * [`algopy.ImmutableArray`](lg-data-structures.md#algopy-immutablearray)
    * [`algopy.arc4.DynamicArray` / `algopy.arc4.StaticArray`](lg-data-structures.md#algopy-arc4-dynamicarray-algopy-arc4-staticarray)
  * [Tips](lg-data-structures.md#tips)
* [Storing data on-chain](lg-storage.md)
  * [Global storage](lg-storage.md#global-storage)
  * [Local storage](lg-storage.md#local-storage)
  * [Box storage](lg-storage.md#box-storage)
  * [Scratch storage](lg-storage.md#scratch-storage)
* [Logging](lg-logs.md)
* [Transactions](lg-transactions.md)
  * [Group Transactions](lg-transactions.md#group-transactions)
    * [ARC-4 parameter](lg-transactions.md#arc-4-parameter)
    * [Group Index](lg-transactions.md#group-index)
  * [Inner Transactions](lg-transactions.md#inner-transactions)
    * [Examples](lg-transactions.md#examples)
    * [Limitations](lg-transactions.md#limitations)
* [AVM operations](lg-ops.md)
  * [Txn](lg-ops.md#txn)
  * [Global](lg-ops.md#global)
* [Opcode budgets](lg-opcode-budget.md)
* [ARC-4: Application Binary Interface](lg-arc4.md)
  * [ARC-32 and ARC-56](lg-arc4.md#arc-32-and-arc-56)
  * [Methods](lg-arc4.md#methods)
  * [Router](lg-arc4.md#router)
  * [Types](lg-arc4.md#types)
    * [Booleans](lg-arc4.md#booleans)
    * [Unsigned ints](lg-arc4.md#unsigned-ints)
    * [Unsigned fixed point decimals](lg-arc4.md#unsigned-fixed-point-decimals)
    * [Bytes and strings](lg-arc4.md#bytes-and-strings)
    * [Static arrays](lg-arc4.md#static-arrays)
    * [Address](lg-arc4.md#address)
    * [Dynamic arrays](lg-arc4.md#dynamic-arrays)
    * [Tuples](lg-arc4.md#tuples)
    * [Structs](lg-arc4.md#structs)
    * [ARC-4 Container Packing](lg-arc4.md#arc-4-container-packing)
    * [Reference types](lg-arc4.md#reference-types)
    * [Mutability](lg-arc4.md#mutability)
* [ARC-28: Structured event logging](lg-arc28.md)
  * [Emitting Events](lg-arc28.md#emitting-events)
* [Calling other applications](lg-calling-apps.md)
  * [`algopy.arc4.abi_call`](lg-calling-apps.md#algopy-arc4-abi-call)
    * [Alternative ways to use `arc4.abi_call`](lg-calling-apps.md#alternative-ways-to-use-arc4-abi-call)
  * [`algopy.arc4.arc4_create`](lg-calling-apps.md#algopy-arc4-arc4-create)
  * [`algopy.arc4.arc4_update`](lg-calling-apps.md#algopy-arc4-arc4-update)
  * [Using `itxn.ApplicationCall`](lg-calling-apps.md#using-itxn-applicationcall)
* [Compiling to AVM bytecode](lg-compile.md)
  * [Outputting AVM bytecode from CLI](lg-compile.md#outputting-avm-bytecode-from-cli)
  * [Obtaining bytecode within other contracts](lg-compile.md#obtaining-bytecode-within-other-contracts)
  * [Template variables](lg-compile.md#template-variables)
    * [CLI](lg-compile.md#cli)
    * [Within other contracts](lg-compile.md#within-other-contracts)
* [Unsupported Python features](lg-unsupported-python-features.md)
  * [raise, try/except/finally](lg-unsupported-python-features.md#raise-try-except-finally)
  * [with](lg-unsupported-python-features.md#with)
  * [async](lg-unsupported-python-features.md#async)
  * [closures & lambdas](lg-unsupported-python-features.md#closures-lambdas)
  * [global keyword](lg-unsupported-python-features.md#global-keyword)
  * [Inheritance (outside of contract classes)](lg-unsupported-python-features.md#inheritance-outside-of-contract-classes)
* [PuyaPy migration from 4.x to 5.0](lg-migration-4-5.md)
  * [`algopy.Array` to `algopy.ReferenceArray`](lg-migration-4-5.md#algopy-array-to-algopy-referencearray)
  * [`algopy.Account`, `algopy.Asset` and `algopy.Application` routing behaviour](lg-migration-4-5.md#algopy-account-algopy-asset-and-algopy-application-routing-behaviour)
  * [Constructor signatures of `ImmutableArray` and `ReferenceArray`](lg-migration-4-5.md#constructor-signatures-of-immutablearray-and-referencearray)
