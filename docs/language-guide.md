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
and byte arrays respectively. These are represented by [`UInt64`](#algopy.UInt64) and
[`Bytes`](#algopy.Bytes) in Algorand Python. There are further "bounded" types supported by the AVM
which are backed by these two simple primitives. For example, `bigint` represents a variably sized
(up to 512-bits), unsigned integer, but is actually backed by a `bytes[]`. This is represented by
[`BigUInt`](#algopy.BigUInt) in Algorand Python.

Unfortunately, none of these types map to standard Python primitives. In Python, an `int` is
unsigned, and effectively unbounded. A `bytes` similarly is limited only by the memory available,
whereas an AVM `bytes[]` has a maximum length of 4096. In order to both maintain semantic
compatibility and allow for a framework implementation in plain Python that will fail under the
same conditions as when deployed to the AVM, support for Python primitives is
[limited](lg-types.md#python-built-in-types).

For more information on the philosophy and design of Algorand Python, please see
["Principles"](principles.md#principles).

If you aren't familiar with Python, a good place to start before continuing below is with the
[official tutorial](https://docs.python.org/3/tutorial/index.html). Just beware that as mentioned
above, [not all features are supported](./lg-unsupported-python-features.md).

## Table of Contents

```{toctree}
---
maxdepth: 3
---

lg-structure
lg-types
lg-control
lg-modules
lg-builtins
lg-errors
lg-storage
lg-logs
lg-transactions
lg-ops
lg-opcode-budget
lg-arc4
lg-arc28
lg-calling-apps
lg-compile
lg-unsupported-python-features
```
