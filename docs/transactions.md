# Transactions

PuyaPy provides types for accessing fields of other transactions in a group, as well as
creating and submitting inner transactions.

The following types are available:

| Group Transaction                                                    | Inner Transaction Parameters                                                     | Inner Transaction                                                              |
|----------------------------------------------------------------------|----------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [PaymentTransaction](puyapy.gtxn.PaymentTransaction)                 | [PaymentTransactionParams](puyapy.itxn.PaymentTransactionParams)                 | [PaymentInnerTransaction](puyapy.itxn.PaymentInnerTransaction)                 |
| [KeyRegistrationTransaction](puyapy.gtxn.KeyRegistrationTransaction) | [KeyRegistrationTransactionParams](puyapy.itxn.KeyRegistrationTransactionParams) | [KeyRegistrationInnerTransaction](puyapy.itxn.KeyRegistrationInnerTransaction) |
| [AssetConfigTransaction](puyapy.gtxn.AssetConfigTransaction)         | [AssetConfigTransactionParams](puyapy.itxn.AssetConfigTransactionParams)         | [AssetConfigInnerTransaction](puyapy.itxn.AssetConfigInnerTransaction)         |
| [AssetTransferTransaction](puyapy.gtxn.AssetTransferTransaction)     | [AssetTransferTransactionParams](puyapy.itxn.AssetTransferTransactionParams)     | [AssetTransferInnerTransaction](puyapy.itxn.AssetTransferInnerTransaction)     |
| [AssetFreezeTransaction](puyapy.gtxn.AssetFreezeTransaction)         | [AssetFreezeTransactionParams](puyapy.itxn.AssetFreezeTransactionParams)         | [AssetFreezeInnerTransaction](puyapy.itxn.AssetFreezeInnerTransaction)         |
| [ApplicationCallTransaction](puyapy.gtxn.ApplicationCallTransaction) | [ApplicationCallTransactionParams](puyapy.itxn.ApplicationCallTransactionParams) | [ApplicationCallInnerTransaction](puyapy.itxn.ApplicationCallInnerTransaction) |
| [AnyTransaction](puyapy.gtxn.AnyTransaction)                         | [AnyTransactionParams](puyapy.itxn.AnyTransactionParams)                         | [AnyInnerTransaction](puyapy.itxn.AnyInnerTransaction)                         |


## Group Transactions

Group transactions can be used as ARC4 parameters or instantiated from a group index.

### ARC4 parameter

Group transactions can be used as parameters in ARC4 method

For example to require a payment transaction in an ARC4 ABI method:
```python
import puyapy


class MyContract(puyapy.ARC4Contract):

    @puyapy.arc4.abimethod()
    def process_payment(self: puyapy.gtxn.PaymentTransaction) -> None:
        ...
```

```{note}
The [AnyTransaction](puyapy.gtxn.AnyTransaction) type cannot be used as an ARC4 ABI argument
```

### Group Index

Group transactions can also be created using the group index of the transaction. 
If instantiating one of the type specific transactions they will be checked to ensure the transaction is of the expected type.
The [AnyTransaction](puyapy.gtxn.AnyTransaction) is not checked for a specific type and provides access to all transaction fields

For example, to obtain a reference to a payment transaction:
```python
import puyapy

@puyapy.subroutine()
def process_payment(group_index: puyapy.UInt64) -> None:
    pay_txn = puyapy.gtxn.PaymentTransaction(group_index)
    ...
```

## Inner Transactions

Inner transactions are defined using the parameter types, and can then be submitted individually by calling the
`.submit()` method, or as a group by calling `submit_inner_txn()`


### Examples

#### Create and submit an inner transaction
```python
import puyapy


@puyapy.subroutine
def create_payment(amount: puyapy.UInt64, receiver: puyapy.Account) -> None:
    puyapy.itxn.PaymentTransactionParams(
        amount=amount,
        receiver=receiver,
        fee=0,
    ).submit()
```

#### Accessing result of a submitted inner transaction
```python
import puyapy


@puyapy.subroutine
def create_asset() -> puyapy.Asset:
    asset_txn = puyapy.itxn.AssetConfigTransactionParams(
        asset_name=b"Puya",
        unit_name=b"PYA",
        total=1000,
        decimals=3,
        fee=0,
    ).submit()
    return asset_txn.created_asset
```

#### Submitting multiple transactions
```python
import puyapy


@puyapy.subroutine
def create_two_assets() -> tuple[puyapy.Asset, puyapy.Asset]:
    asset1_params = puyapy.itxn.AssetConfigTransactionParams(
        asset_name=b"Puya",
        unit_name=b"PYA",
        total=1000,
        decimals=3,
        fee=0,
    )
    asset2_params = asset1_params.copy() # a parameter object can be copied and then modified
    asset2_params.set(asset_name=b"Puya 2", unit_name="PYA2")
    asset1_txn, asset2_txn = puyapy.itxn.submit_inner_txn(asset1_params, asset2_params)
    return asset1_txn.created_asset, asset2_txn.created_asset
```

#### Create an application, and then call it
```python
import puyapy

def get_program_bytes() -> tuple[puyapy.Bytes, puyapy.Bytes]:
    ...

@puyapy.subroutine
def create_application() -> puyapy.Application:
    approval, clear = get_program_bytes()
    application_txn = puyapy.itxn.ApplicationCallTransactionParams(
        approval_program=approval,
        clear_state_program=clear,
    ).submit()
    puyapy.itxn.ApplicationCallTransactionParams(
        application_id=application_txn.created_application,
        application_args=(puyapy.Bytes(b"arg1"), puyapy.Bytes(b"arg2"))
    ).submit()
    return application_txn.created_application
```

#### Create and submit transactions in a loop
```python
import puyapy

@puyapy.subroutine
def create_payments(receivers: tuple[puyapy.Account, puyapy.Account, puyapy.Account]) -> None:
    for receiver in receivers:
        puyapy.itxn.PaymentTransactionParams(
            amount=puyapy.UInt64(1_000_000),
            receiver=receiver,
            fee=0,
        ).submit()
```
### Limitations

Inner transactions are powerful, but currently do have some restrictions in how they are used.

* Inner transaction objects cannot be passed to subroutines
  ```{note}
  Individual fields can be passed to subroutines
  ```
* Inner transaction parameters cannot be reassigned without a `.copy()`
* Inner transactions cannot be reassigned
* Inner transactions array values cannot be accessed if there is a subsequent inner transaction submitted. 
  An assertion will raise an error if this is attempted
  ```{note}
  This can be worked around by assigning array results to a local variable before submitting another transaction
  ```
