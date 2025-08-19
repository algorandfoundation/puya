# PuyaPy migration from 4.x to 5.0

PuyaPy 5.0 and the accompanying Algorand Python 3.0 `algopy` stubs have some breaking changes from prior versions, this document outlines those changes and how to resolve them

## `algopy.Array` to `algopy.ReferenceArray`

The `algopy.Array` type present in 4.x has been renamed to `algopy.ReferenceArray` to make it clearer how it differs from the other array types.
If a contract was using this type in 4.x it could encounter one of the following errors after upgrading to 5.0
* `No overload variant of "Array" matches argument types`
* `expression is not valid as an assignment target`
* `unsupported assignment target`
* `mutable values cannot be passed more than once to a subroutine`

A simple way to solve this for existing contracts using the old name is to alias the `ReferenceArray` type as `Array`.

e.g.
```python
from algopy import ReferenceArray as Array
```

If you need to use both `algopy.ReferenceArray` and the new `algopy.Array` then it would be better to update existing
`algopy.Array` references to `algopy.ReferenceArray`

e.g. code that was using `algopy.Array` prior to 5.0
```python
from algopy import *

@subroutine
def some_method(arr: Array[UInt64]) -> None: ...
```

After migrating to 5.0, should use `algopy.ReferenceArray` for existing code, and is free to use `algopy.Array` for new code
```python
from algopy import *

@subroutine
def some_method(arr: ReferenceArray[UInt64]) -> None: ... 

@subroutine
def a_new_method(arr: Array[UInt64]) -> None:
```

## `algopy.Account`, `algopy.Asset` and `algopy.Application` routing behaviour

The default routing behaviour for resources types `algopy.Account`, `algopy.Asset` and `algopy.Application` has changed in 5.0, the new behaviour
will treat these types as their underlying ARC-4 value type when constructing ABI method signatures. This allows for more efficient resource packing
when using the `algokit_utils` populate resource functionality.

| Type                 | 4.x (`foreign_index`)  | 5.0 (`value`) |
|----------------------|------------------------|---------------|
| `algopy.Account`     | `account`              | `address`     |
| `algopy.Asset`       | `asset`                | `uint64`      |
| `algopy.Application` | `application`          | `uint64`      |

There are two methods to return to the 4.x behaviour for these types: 

1.) Use original behaviour for entire compilation by using CLI options

The original behaviour can be restored by using the `--resource-encoding` CLI option on `puyapy`

e.g.
`puyapy --resource-encoding=index path/to/contracts`

2.) Use original behaviour for specific methods by using an `abimethod` option
Individual methods can be forced to use the original behaviour by setting the `resource_encoding` option
on `arc4.abimethod` e.g.

```python
from algopy import arc4, Account, Application, Asset

class MyContract(arc4.ARC4Contract):
    @arc4.abimethod(resource_encoding="index")
    def my_abi_method(self, app: Application, asset: Asset, account: Account) -> None:
        ...
        # has an ARC-4 signature of my_abi_method(application,asset,account)void
```
