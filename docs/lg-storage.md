# Storing data on-chain

Algorand smart contracts have [three different types of on-chain storage](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/state/)
they can utilise: [Global storage](#global-storage), [Local storage](#local-storage), [Box Storage](#box-storage), and [Scratch storage](#scratch-storage).

The life-cycle of a smart contract matches the semantics of Python classes when you consider
deploying a smart contract as "instantiating" the class. Any calls to that smart contract are made
to that instance of the smart contract, and any state assigned to `self.` variables will persist
across different invocations (provided the transaction it was a part of succeeds, of course). You can
deploy the same contract class multiple times, each will become a distinct and isolated instance.

During a single smart contract execution there is also the ability to use "temporary" storage
either global to the contract execution via [Scratch storage](#scratch-storage), or local to
the current method via [local variables and subroutine params](./lg-structure.md#subroutines).

## Global storage

Global storage is state that is stored against the contract instance and can be retrieved
by key. There are [AVM limits to the amount of global storage that can be allocated to a contract](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/state/#global-storage).

This is represented in Algorand Python by either:

1. Assigning any [Algorand Python typed](./lg-types.md) value to an instance variable (e.g. `self.value = UInt64(3)`)
2. Using an instance of `GlobalState`, which gives [some extra features](./api-algopy.md#algopy.GlobalState) to understand
   and control the value and the metadata of it (which propagates to the ARC-32 app spec file)

For example:

```python
self.global_int_full = GlobalState(UInt64(55), key="gif", description="Global int full")
self.global_int_simplified = UInt64(33)
self.global_int_no_default = GlobalState(UInt64)

self.global_bytes_full = GlobalState(Bytes(b"Hello"))
self.global_bytes_simplified = Bytes(b"Hello")
self.global_bytes_no_default = GlobalState(Bytes)

global_int_full_set = bool(self.global_int_full)
bytes_with_default_specified = self.global_bytes_no_default.get(b"Default if no value set")
int, is_set = self.global_int_simplified.maybe()
error_if_not_set = self.global_int_no_default.value
```

These values can be assigned anywhere you have access to `self` i.e. any instance methods/subroutines. The information about
global storage is automatically included in the ARC-32 app spec file and thus will automatically appear within
any [generated typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients).

## Local storage

Local storage is state that is stored against the contract instance for a specific account and can be retrieved
by key and account address. There are [AVM limits to the amount of local storage that can be allocated to a contract](https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/state/#local-storage).

This is represented in Algorand Python by using an instance of [`LocalState`](./api-algopy.md#algopy.LocalState).

For example:

```python
def __init__(self) -> None:
    self.local = LocalState(Bytes)
    self.local_with_metadata = LocalState(UInt64, key = "lwm", description = "Local with metadata")

@subroutine
def get_guaranteed_data(self, for_account: Account) -> Bytes:
    return self.local[for_account]

@subroutine
def get_data_with_default(self, for_account: Account, default: Bytes) -> Bytes:
    return self.local.get(for_account, default)

@subroutine
def get_data_or_assert(self, for_account: Account) -> Bytes:
    result, exists = self.local.maybe(for_account)
    assert exists, "no data for account"
    return result

@subroutine
def set_data(self, for_account: Account, value: Bytes) -> None:
    self.local[for_account] = value

@subroutine
def delete_data(self, for_account: Account) -> None:
    del self.local[for_account]
```

These values can be assigned anywhere you have access to `self` i.e. any instance methods/subroutines. The information about
local storage is automatically included in the ARC-32 app spec file and thus will automatically appear within
any [generated typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients).

## Box storage

We provide 3 different types for accessing box storage: [Box](./api-algopy.md#algopy.Box), [BoxMap](./api-algopy.md#algopy.BoxMap), and [BoxRef](./api-algopy.md#algopy.BoxBlob). We also expose raw operations via the [AVM ops](./lg-ops.md) module.

Before using box storage, be sure to familiarise yourself with the [requirements and restrictions](https://developer.algorand.org/articles/smart-contract-storage-boxes/) of the underlying API.

The `Box` type provides an abstraction over storing a single value in a single box. A box can be declared against `self`
in an `__init__` method (in which case the key must be a compile time constant); or as a local variable within any 
subroutine. `Box` proxy instances can be passed around like any other value. 

Once declared, you can interact with the box via its instance methods.


```python
import typing as t
from algopy import Box, arc4, Contract, op


class MyContract(Contract):
    def __init__(self) -> None:
        self.box_a = Box(arc4.StaticArray[arc4.UInt32, t.Literal[20]], key=b"a")
    
    def approval_program(self) -> bool:
        box_b = Box(arc4.String, key=b"b")
        box_b.value = arc4.String("Hello")
        # Check if the box exists
        if self.box_a:
            # Reassign the value
            self.box_a.value[2] = arc4.UInt32(40)
        else:
            # Assign a new value
            self.box_a.value = arc4.StaticArray[arc4.UInt32, t.Literal[20]].from_bytes(op.bzero(20 * 4))
        # Read a value
        return self.box_a.value[4] == arc4.UInt32(2)    
```

`BoxMap` is similar to the `Box` type, but allows for grouping a set of boxes with a common key and content type. 
A custom `key_prefix` can optionally be provided, with the default being to use the variable name as the prefix. 
The key can be a `Bytes` value, or anything that can be converted to `Bytes`. The final box name is the combination of `key_prefix + key`.

```python
from algopy import BoxMap, Contract, Account, Txn, String

class MyContract(Contract):
    def __init__(self) -> None:
        self.my_map = BoxMap(Account, String, key_prefix=b"a_")
    
    def approval_program(self) -> bool:        
        # Check if the box exists
        if Txn.sender in self.my_map:
            # Reassign the value
            self.my_map[Txn.sender] = String(" World")
        else:
            # Assign a new value
            self.my_map[Txn.sender] = String("Hello")
        # Read a value
        return self.my_map[Txn.sender] == String("Hello World")
```

`BoxRef` is a specialised type for interacting with boxes which contain binary data. In addition to being able to set and read the box value, there are operations for extracting and replacing just a portion of the box data which 
is useful for minimizing the amount of reads and writes required, but also allows you to interact with byte arrays which are longer than the AVM can support (currently 4096).

```python
from algopy import BoxRef, Contract, Global, Txn


class MyContract(Contract):
    def approval_program(self) -> bool:
        my_blob = BoxRef(key=b"blob")

        sender_bytes = Txn.sender.bytes
        app_address = Global.current_application_address.bytes
        assert my_blob.create(8000)
        my_blob.replace(0, sender_bytes)
        my_blob.splice(0, 0, app_address)
        first_64 = my_blob.extract(0, 32 * 2)
        assert first_64 == app_address + sender_bytes
        assert my_blob.delete()
        value, exists = my_blob.maybe()
        assert not exists
        assert my_blob.get(default=sender_bytes) == sender_bytes
        my_blob.create(sender_bytes + app_address)
        assert my_blob, "Blob exists"
        assert my_blob.length == 64
        return True
```



If none of these abstractions suit your needs, you can use the box storage [AVM ops](./lg-ops.md) to interact with box storage. These ops match closely to the opcodes available on the AVM. 

For example:

```python
op.Box.create(b"key", size)
op.Box.put(Txn.sender.bytes, answer_ids.bytes)
(votes, exists) = op.Box.get(Txn.sender.bytes)
op.Box.replace(TALLY_BOX_KEY, index, op.itob(current_vote + 1))
```

See the [voting contract example](https://github.com/algorandfoundation/puya/tree/main/examples/voting/voting.py) for a real-world example that uses box storage.

## Scratch storage

To use stratch storage you need to [register the scratch storage that you want to use](./lg-structure.md#contract-class-configuration) and then you can use the scratch storage [AVM ops](./lg-ops.md).

For example:

```python
from algopy import Bytes, Contract, UInt64, op, urange

TWO = 2
TWENTY = 20


class MyContract(Contract, scratch_slots=(1, TWO, urange(3, TWENTY))):
    def approval_program(self) -> bool:
        op.Scratch.store(1, UInt64(5))

        op.Scratch.store(2, Bytes(b"Hello World"))

        for i in urange(3, 20):
            op.Scratch.store(i, i)

        assert op.Scratch.load_uint64(1) == UInt64(5)

        assert op.Scratch.load_bytes(2) == b"Hello World"

        assert op.Scratch.load_uint64(5) == UInt64(5)
        return True

    def clear_state_program(self) -> bool:
        return True
```
