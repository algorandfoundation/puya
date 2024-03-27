# AVM operations

Algorand Python allows you to do express [every op code the AVM has available](https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#operations) apart from ops that manipulate the stack (to avoid conflicts with the compiler), and `log` (to avoid confusion with the superior [Algorand Python log function](./lg-logs.md)). These ops are exposed via the [`algopy.op`](#algopy.op) submodule.
We generally recommend importing this entire submodule so you can use intellisense to discover the available methods:

```python
from algopy import UInt64, op, subroutine

@subroutine
def sqrt_16() -> UInt64:
    return op.sqrt(16)
```

All ops are typed using Algorand Python types and have correct static type representations.

Many ops have higher-order functionality that Algorand Python exposes and would limit the need to reach for the underlying ops. For instance, there is first-class support for local and global storage so there is little need to use the likes of `app_local_get` et. al. But they are still exposed just in case you want to do something that Algorand Python's abstractions don't support.

## Txn

The `Txn` opcodes are so commonly used they have been exposed directly in the `algopy` module and can be easily imported to make it terser to access:

```python
from algopy import subroutine, Txn

@subroutine
def has_no_app_args() -> bool:
    return Txn.num_app_args == 0
```

## Global

The `Global` opcodes are so commonly used they have been exposed directly in the `algopy` module and can be easily imported to make it terser to access:

```python
from algopy import subroutine, Global, Txn

@subroutine
def only_allow_creator() -> None:
    assert Txn.sender == Global.creator_address, "Only the contract creator can perform this operation"
```
