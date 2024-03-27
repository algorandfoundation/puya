# Contract structure

An Algorand Python smart contract is defined within a single class. You can extend other contracts (through inheritance), and also define standalone functions and reference them. This also works across different Python packages - in other words, you can have a Python library with common functions and re-use that library across multiple projects!

## Contract classes

All contracts must inherit from the base class `algopy.Contract` - either directly or indirectly, which can include inheriting from `algopy.ARC4Contract`.

TODO: concrete vs abstract, link to inheritance for code-reuse

### Example: Simplest possible `algopy.Contract` implementation

For a non-ARC4 contract, the contract class must implement an `approval_program` and a `clear_state_program` method. 

As an example, this is a valid contract that always approves:

```python
import algopy

class Contract(algopy.Contract):
    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True
```

The return value of these methods can be either a `bool` that indicates whether the transaction should approve or not, or a `algopy.UInt64` value, where `UInt64(0)` indicates that the transaction should be rejected and any other value indicates that it should be approved.

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

### Example: Switching based on on-complete and contract creation

A common pattern is to perform different logic depending on the on-complete action passed to the contract call or whether the contract is being created or not. This is [handled for you when creating ARC-4 contracts](./lg-arc4.md), but if you are creating a contract by hand then following is an example of how you could potentially split based on on-complete and creation:

```python
from algopy import Contract, OnCompleteAction, Txn, log, subroutine


class ManualRouting(Contract):
    def approval_program(self) -> bool:
        if not Txn.application_id:
            self.create()
        else:
            match Txn.on_completion:
                case OnCompleteAction.UpdateApplication:
                    self.update()
                case OnCompleteAction.DeleteApplication:
                    self.delete()
                case _:
                    self.other()
        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def create(self) -> None:
        log("creating")

    @subroutine
    def update(self) -> None:
        log("updating")

    @subroutine
    def delete(self) -> None:
        log("deleting")

    @subroutine
    def other(self) -> None:
        log("other", Txn.on_completion, Txn.num_app_args)

```

TODO: `__init__` methods


## Subroutines

TODO: no *args, **kwargs support

## Modules & sub-modules

- multiple contracts per module
- modules with no contracts
- importing other modules
- link to lg-modules.md for more details about supported module level code


## logic signatures
