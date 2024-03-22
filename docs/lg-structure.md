# Contract structure

An Algorand Python smart contract is defined within a single class. You can extend other contracts (through inheritance), and also define standalone functions and reference them. This also works across different Python packages - in other words, you can have a Python library with common functions and re-use that library across multiple projects!

All contracts must inherit from the base class `puyapy.Contract` - either directly or indirectly, which can include inheriting from `puyapy.ARC4Contract`. For a non-ARC4 contract, a contract class must implement an `approval_program` and a `clear_state_program` method. For ARC4 contracts, these methods will be implemented for you, although you can optionally provide a `clear_state_program` (the default implementation just always approves).

As an example, this is a valid contract that always approves:

```python
import puyapy

class Contract(puyapy.Contract):
    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True
```

The return value of these methods can be either a `bool` that indicates whether the transaction should approve or not, or a `puyapy.UInt64` value, where `UInt64(0)` indicates that the transaction should be rejected and any other value indicates that it should be approved.

And here is a valid ARC4 contract:

```python
import puyapy

class ABIContract(puyapy.ARC4Contract):
    """This contract can be created, but otherwise does nothing"""
    pass
```
