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
from puyapy import Account, UInt64, itxn, subroutine


@subroutine
def example(amount: UInt64, receiver: Account) -> None:
    itxn.PaymentTransactionParams(
        amount=amount,
        receiver=receiver,
        fee=0,
    ).submit()
```

#### Accessing result of a submitted inner transaction

```python
from puyapy import Asset, itxn, subroutine


@subroutine
def example() -> Asset:
    asset_txn = itxn.AssetConfigTransactionParams(
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
from puyapy import Asset, Bytes, itxn, log, subroutine


@subroutine
def example() -> tuple[Asset, Bytes]:
    asset1_params = itxn.AssetConfigTransactionParams(
        asset_name=b"Puya",
        unit_name=b"PYA",
        total=1000,
        decimals=3,
        fee=0,
    )
    app_params = itxn.ApplicationCallTransactionParams(
        application_id=1234,
        application_args=(Bytes(b"arg1"), Bytes(b"arg1"))
    )
    asset1_txn, app_txn = itxn.submit_txns(asset1_params, app_params)
    # log some details
    log(app_txn.logs(0))
    log(asset1_txn.txn_id)
    log(app_txn.txn_id)
    
    return asset1_txn.created_asset, app_txn.logs(1)
```

#### Create an application, and then call it

```python
from puyapy import Application, Bytes, itxn, subroutine

@subroutine
def example() -> Application:
    approval, clear = get_program_bytes()
    application_txn = itxn.ApplicationCallTransactionParams(
        approval_program=approval,
        clear_state_program=clear,
    ).submit()
    itxn.ApplicationCallTransactionParams(
        application_id=application_txn.created_application,
        application_args=(Bytes(b"arg1"), Bytes(b"arg2"))
    ).submit()
    return application_txn.created_application

@subroutine
def get_program_bytes() -> tuple[Bytes, Bytes]:
    ...
```

#### Create and submit transactions in a loop

```python
from puyapy import Account, UInt64, itxn, subroutine

@subroutine
def example(receivers: tuple[Account, Account, Account]) -> None:
    for receiver in receivers:
        itxn.PaymentTransactionParams(
            amount=UInt64(1_000_000),
            receiver=receiver,
            fee=0,
        ).submit()
```
### Limitations

Inner transactions are powerful, but currently do have some restrictions in how they are used.

#### Inner transaction objects cannot be passed to or returned from subroutines

```python
from puyapy import Application, Bytes, itxn, subroutine

@subroutine
def parameter_not_allowed(txn: itxn.PaymentInnerTransaction) -> None:
    # this is a compile error
    ...

@subroutine
def return_not_allowed() -> itxn.PaymentInnerTransaction:
    # this is a compile error
    ...

@subroutine
def passing_fields_allowed() -> Application:
    txn = itxn.ApplicationCallTransactionParams(...).submit()
    do_something(txn.txn_id, txn.logs(0)) # this is ok
    return txn.created_application # and this is ok

@subroutine
def do_something(txn_id: Bytes): # this is just a regular subroutine
    ...
```

#### Inner transaction parameters cannot be reassigned without a `.copy()`

```python
from puyapy import itxn, subroutine

@subroutine
def example() -> None:
    payment = itxn.PaymentTransactionParams(...)
    reassigned_payment = payment # this is an error
    copied_payment = payment.copy() # this is ok
```

#### Inner transactions cannot be reassigned

```python
from puyapy import itxn, subroutine

@subroutine
def example() -> None:
    payment_txn = itxn.PaymentTransactionParams(...).submit()
    reassigned_payment_txn = payment_txn # this is an error
    txn_id = payment_txn.txn_id # this is ok
```

#### Inner transactions methods cannot be called if there is a subsequent inner transaction submitted.

```python
from puyapy import itxn, subroutine

@subroutine
def example() -> None:
    app_1 = itxn.ApplicationCallTransactionParams(...).submit()
    log_from_call1 = app_1.logs(0) # this is ok
    
    # another inner transaction is submitted
    itxn.ApplicationCallTransactionParams(...).submit()
    
    app1_txn_id = app_1.txn_id # this is ok, properties are still available
    another_log_from_call1 = app_1.logs(1) # this will error at runtime as the array results are no longer available
```
