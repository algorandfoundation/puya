# Program structure

An Algorand Python smart contract is defined within a single class. You can extend other
contracts (through inheritance), and also define standalone functions and reference them. This also
works across different Python packages - in other words, you can have a Python library with common
functions and re-use that library across multiple projects!

## Modules

Algorand Python modules are files that end in `.py`, as with standard Python. Sub-modules are
supported as well, so you're free to organise your Algorand Python code however you see fit. 
The standard python import rules apply, including 
[relative vs absolute import](https://docs.python.org/3/reference/import.html#package-relative-imports)
requirements.

A given module can contain zero, one, or many smart contracts and/or logic signatures.

A module can contain [contracts](#contract-classes), [subroutines](#subroutines), 
[logic signatures](#logic-signatures), and [compile-time constant code and values](lg-modules.md).

## Contract classes

An Algorand smart contract consists of two distinct "programs", and approval program, and a 
clear-state program. These are tied together in Algorand Python as a single class.

All contracts must inherit from the base class `algopy.Contract` - either directly or indirectly,
which can include inheriting from `algopy.ARC4Contract`.

The life-cycle of a smart contract matches the semantics of Python classes when you consider 
deploying a smart contract as "instantiating" the class. Any calls to that smart contract are made
to that instance of the smart contract, and any state assigned to `self.` will persist across 
different invocations (provided the transaction it was a part of succeeds, of course). You can 
deploy the same contract class multiple times, each will become a distinct and isolated instance.

Contract classes can optionally implement an `__init__` method, which will be executed exactly 
once, on first deployment. This method takes no arguments, but can contain arbitrary code, 
including reading directly from the transaction arguments via [`Txn`](#algopy.op.Txn). This makes
it a good place to put common initialisation code, particularly in ARC-4 contracts with multiple
methods that allow for creation.

The contract class body should not contain any logic or variable initialisations, only method 
definitions. Forward type declarations are allowed.

Example:

```python3
class MyContract(algopy.Contract):
    foo: algopy.UInt64  # okay
    bar = algopy.UInt64(1) # not allowed

    if True: # also not allowed
        bar = algopy.UInt64(2)
```

Only concrete (ie non-abstract) classes produce output artifacts for deployment. To mark a class
as explicitly abstract, inherit from [`abc.ABC`](https://docs.python.org/3/library/abc.html#abc.ABC).

```{note}
The compiler will produce a warning if a Contract class is implicitly abstract, i.e. if any
abstract methods are unimplemented. 
```

For more about inheritance and it's role in code reuse, see the section
in [Code reuse](lg-code-reuse.md#inheritance)

### Example: Simplest possible `algopy.Contract` implementation

For a non-ARC4 contract, the contract class must implement an `approval_program` and
a `clear_state_program` method. 

As an example, this is a valid contract that always approves:

```python
import algopy

class Contract(algopy.Contract):
    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True
```

The return value of these methods can be either a `bool` that indicates whether the transaction
should approve or not, or a `algopy.UInt64` value, where `UInt64(0)` indicates that the transaction
should be rejected and any other value indicates that it should be approved.

### Example: Simplest possible `algopy.ARC4Contract` implementation

And here is a valid ARC4 contract:

```python
import algopy

class ABIContract(algopy.ARC4Contract):
    pass
```

A default `@algopy.arc4.baremethod` that allows contract creation is automatically inserted if no
other public method allows execution on create.

The approval program is always automatically generated, and consists of a router which delegates 
based on the transaction application args to the correct public method.

A default `clear_state_program` is implemented which always approves, but this can be overridden.

## Subroutines

TODO: no *args, **kwargs support



## logic signatures
