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

## Typing

Algorand Python code must be fully typed with 
[type annotations](https://docs.python.org/3/library/typing.html).

In practice, this mostly means annotating the arguments and return types of all functions.

## Subroutines

Subroutines are "internal" or "private" methods to a contract. They can exist as part of a contract
class, or at the module level so they can be used by multiple classes or even across multiple
projects.

All subroutines must be decorated with `algopy.subroutine`, like so:

```python3
def foo() -> None: # compiler error: not decorated with subroutine
    ...

@algopy.subroutine
def bar() -> None:
    ...
```


```{note}
Requiring this decorator serves two key purposes:

1. You get an understandable error message if you try and use a third party package that wasn't 
   built for Algorand Python 
1. It provides for the ability to modify the functions on the fly when running in Python itself, in
   a future testing framework.
```

Argument and return types to a subroutine can be any Algorand Python variable type (except for  
[some inner transaction types](lg-transactions.md#inner-transaction-objects-cannot-be-passed-to-or-returned-from-subroutines)
).

Returning multiple values is allowed, this is annotated in the standard Python way with `tuple`:

```python3
@algopy.subroutine
def return_two_things() -> tuple[algopy.UInt64, algopy.String]:
    ...
```

Keyword only and positional only argument list modifiers are supported:

```python3
@algopy.subroutine
def my_method(a: algopy.UInt64, /, b: algopy.UInt64, *, c: algopy.UInt64) -> None:
    ...
```
In this example, `a` can only be passed positionally, `b` can be passed either by position or by 
name, and `c` can only be passed by name.

The following argument/return types are not currently supported:
- Type unions
- Variadic args like `*args`, `**kwargs`
- Python types such as `int` 
- Default values are not supported


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
class Contract(algopy.Contract):
    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True
```

The return value of these methods can be either a `bool` that indicates whether the transaction
should approve or not, or a `algopy.UInt64` value, where `UInt64(0)` indicates that the transaction
should be rejected and any other value indicates that it should be approved.

### Example: Simple call counter

Here is a very simple example contract, that simple maintains a counter of how many times it has
been called (including on create).

```python3
class Counter(algopy.Contract):
    def __init__(self) -> None:
        self.counter = algopy.UInt64(0)
    
    def approval_program(self) -> bool:
        match algopy.Txn.on_completion:
            case algopy.OnCompleteAction.NoOp:
                self.increment_counter()
                return True
            case _:
                # reject all OnCompletionAction's other than NoOp
                return False
    
    def clear_state_program(self) -> bool:
        return True
    
    @algopy.subroutine
    def increment_counter(self) -> None:
        self.counter += 1
```

Some things to note:
- `self.counter` will be stored in the application's [Global State](lg-storage.md#global-state).
- The return type of `__init__` must be `None`, this is a general typed Python concern.
- Any methods other than `__init__`, `approval_program` or `clear_state_program` must be decorated
  with `@subroutine`.

### Example: Simplest possible `algopy.ARC4Contract` implementation

And here is a valid ARC4 contract:

```python
class ABIContract(algopy.ARC4Contract):
    pass
```

A default `@algopy.arc4.baremethod` that allows contract creation is automatically inserted if no
other public method allows execution on create.

The approval program is always automatically generated, and consists of a router which delegates 
based on the transaction application args to the correct public method.

A default `clear_state_program` is implemented which always approves, but this can be overridden.

### Example: An ARC4 call counter

```python3
import algopy

class ARC4Counter(algopy.ARC4Contract):
    def __init__(self) -> None:
        self.counter = algopy.UInt64(0)

    @algopy.arc4.abimethod(create="allow")
    def invoke(self) -> algopy.arc4.UInt64:
        self.increment_counter()
        return algopy.arc4.UInt64(self.counter)
    
    @algopy.subroutine
    def increment_counter(self) -> None:
        self.counter += 1
```

This functions very similarly to the [simple example](#example-simple-call-counter).

Things to note here:
- Since the `invoke` method has `create="allow"`, it can be called both as the method to create the
  app and also to invoke it after creation. This also means that no default bare-method create will
  be generated, so the only way to create the contract is through this method.
- The default options for `abimethod` is to only allow `NoOp` as an on-completion-action, so we
  don't need to check this manually.
- The current call count is returned from the `invoke` method.
- Every method in an `AR4Contract` except for the optional `__init__` and `clear_state_program`
  methods must be decorated with one of `algopy.arc4.abimethod`, `alogpy.arc4.baremethod`, or
  `algopy.subroutine`. `subroutines` won't be directly callable through the default router.

See the [ARC-4 section](lg-arc4.md) of this language guide for more info on the above.


## Logic signatures
