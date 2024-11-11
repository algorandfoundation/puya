# Transactions

Algorand Python provides types for accessing fields of other transactions in a group, as well as
creating and submitting inner transactions from your smart contract.

The following types are available:

| Group Transactions                                                   | Inner Transaction Field sets                     | Inner Transaction                                                              |
| -------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------ |
| [PaymentTransaction](algopy.gtxn.PaymentTransaction)                 | [Payment](algopy.itxn.Payment)                   | [PaymentInnerTransaction](algopy.itxn.PaymentInnerTransaction)                 |
| [KeyRegistrationTransaction](algopy.gtxn.KeyRegistrationTransaction) | [KeyRegistration](algopy.itxn.KeyRegistration)   | [KeyRegistrationInnerTransaction](algopy.itxn.KeyRegistrationInnerTransaction) |
| [AssetConfigTransaction](algopy.gtxn.AssetConfigTransaction)         | [AssetConfig](algopy.itxn.AssetConfig)           | [AssetConfigInnerTransaction](algopy.itxn.AssetConfigInnerTransaction)         |
| [AssetTransferTransaction](algopy.gtxn.AssetTransferTransaction)     | [AssetTransfer](algopy.itxn.AssetTransfer)       | [AssetTransferInnerTransaction](algopy.itxn.AssetTransferInnerTransaction)     |
| [AssetFreezeTransaction](algopy.gtxn.AssetFreezeTransaction)         | [AssetFreeze](algopy.itxn.AssetFreeze)           | [AssetFreezeInnerTransaction](algopy.itxn.AssetFreezeInnerTransaction)         |
| [ApplicationCallTransaction](algopy.gtxn.ApplicationCallTransaction) | [ApplicationCall](algopy.itxn.ApplicationCall)   | [ApplicationCallInnerTransaction](algopy.itxn.ApplicationCallInnerTransaction) |
| [Transaction](algopy.gtxn.Transaction)                               | [InnerTransaction](algopy.itxn.InnerTransaction) | [InnerTransactionResult](algopy.itxn.InnerTransactionResult)                   |

## Group Transactions

Group transactions can be used as ARC4 parameters or instantiated from a group index.

### ARC4 parameter

Group transactions can be used as parameters in ARC4 method

For example to require a payment transaction in an ARC4 ABI method:

```python
import algopy


class MyContract(algopy.ARC4Contract):

    @algopy.arc4.abimethod()
    def process_payment(self: algopy.gtxn.PaymentTransaction) -> None:
        ...
```

### Group Index

Group transactions can also be created using the group index of the transaction.
If instantiating one of the type specific transactions they will be checked to ensure the transaction is of the expected type.
[Transaction](algopy.gtxn.Transaction) is not checked for a specific type and provides access to all transaction fields

For example, to obtain a reference to a payment transaction:

```python
import algopy


@algopy.subroutine()
def process_payment(group_index: algopy.UInt64) -> None:
    pay_txn = algopy.gtxn.PaymentTransaction(group_index)
    ...
```

## Inner Transactions

Inner transactions are defined using the parameter types, and can then be submitted individually by calling the
`.submit()` method, or as a group by calling [`submit_txns`](#algopy.itxn.submit_txns)

### Examples

#### Create and submit an inner transaction

```python
from algopy import Account, UInt64, itxn, subroutine


@subroutine
def example(amount: UInt64, receiver: Account) -> None:
    itxn.Payment(
        amount=amount,
        receiver=receiver,
        fee=0,
    ).submit()
```

#### Accessing result of a submitted inner transaction

```python
from algopy import Asset, itxn, subroutine


@subroutine
def example() -> Asset:
    asset_txn = itxn.AssetConfig(
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
from algopy import Asset, Bytes, itxn, log, subroutine


@subroutine
def example() -> tuple[Asset, Bytes]:
    asset1_params = itxn.AssetConfig(
        asset_name=b"Puya",
        unit_name=b"PYA",
        total=1000,
        decimals=3,
        fee=0,
    )
    app_params = itxn.ApplicationCall(
        app_id=1234,
        app_args=(Bytes(b"arg1"), Bytes(b"arg1"))
    )
    asset1_txn, app_txn = itxn.submit_txns(asset1_params, app_params)
    # log some details
    log(app_txn.logs(0))
    log(asset1_txn.txn_id)
    log(app_txn.txn_id)

    return asset1_txn.created_asset, app_txn.logs(1)
```

#### Create an ARC4 application, and then call it

```python
from algopy import Bytes, arc4, itxn, subroutine

HELLO_WORLD_APPROVAL: bytes = ...
HELLO_WORLD_CLEAR: bytes = ...


@subroutine
def example() -> None:
    # create an application
    application_txn = itxn.ApplicationCall(
        approval_program=HELLO_WORLD_APPROVAL,
        clear_state_program=HELLO_WORLD_CLEAR,
        fee=0,
    ).submit()
    app = application_txn.created_app

    # invoke an ABI method
    call_txn = itxn.ApplicationCall(
        app_id=app,
        app_args=(arc4.arc4_signature("hello(string)string"), arc4.String("World")),
        fee=0,
    ).submit()
    # extract result
    hello_world_result = arc4.String.from_log(call_txn.last_log)
```

#### Create and submit transactions in a loop

```python
from algopy import Account, UInt64, itxn, subroutine


@subroutine
def example(receivers: tuple[Account, Account, Account]) -> None:
    for receiver in receivers:
        itxn.Payment(
            amount=UInt64(1_000_000),
            receiver=receiver,
            fee=0,
        ).submit()
```

### Limitations

Inner transactions are powerful, but currently do have some restrictions in how they are used.

#### Inner transaction objects cannot be passed to or returned from subroutines

```python
from algopy import Application, Bytes, itxn, subroutine


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
    txn = itxn.ApplicationCall(...).submit()
    do_something(txn.txn_id, txn.logs(0))  # this is ok
    return txn.created_app  # and this is ok


@subroutine
def do_something(txn_id: Bytes):  # this is just a regular subroutine
    ...
```

#### Inner transaction parameters cannot be reassigned without a `.copy()`

```python
from algopy import itxn, subroutine


@subroutine
def example() -> None:
    payment = itxn.Payment(...)
    reassigned_payment = payment  # this is an error
    copied_payment = payment.copy()  # this is ok
```

#### Inner transactions cannot be reassigned

```python
from algopy import itxn, subroutine


@subroutine
def example() -> None:
    payment_txn = itxn.Payment(...).submit()
    reassigned_payment_txn = payment_txn  # this is an error
    txn_id = payment_txn.txn_id  # this is ok
```

#### Inner transactions methods cannot be called if there is a subsequent inner transaction submitted or another subroutine is called.

```python
from algopy import itxn, subroutine


@subroutine
def example() -> None:
    app_1 = itxn.ApplicationCall(...).submit()
    log_from_call1 = app_1.logs(0)  # this is ok

    # another inner transaction is submitted
    itxn.ApplicationCall(...).submit()
    # or another subroutine is called
    call_some_other_subroutine()

    app1_txn_id = app_1.txn_id  # this is ok, properties are still available
    another_log_from_call1 = app_1.logs(1)  # this is not allowed as the array results may no longer be available, instead assign to a variable before submitting another transaction
```
