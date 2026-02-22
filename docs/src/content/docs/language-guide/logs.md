---
title: Logging
description: Logging output from Algorand Python smart contracts
---

Algorand Python provides a [`log` method](/puya/api/algopy/#algopy.log) that allows you to emit debugging and event information as well as return values from your contracts to the caller.

This `log` method is a superset of the [AVM `log` method](/puya/language-guide/ops/) that adds extra functionality:

-   You can log multiple items rather than a single item
-   Items are concatenated together with an optional separator (which defaults to: `""`)
-   Items are automatically converted to bytes for you
-   Support for:
    -   `int` literals / module variables (encoded as raw bytes, not ASCII)
    -   `UInt64` values (encoded as raw bytes, not ASCII)
    -   `str` literals / module variables (encoded as UTF-8)
    -   `bytes` literals / module variables (encoded as is)
    -   `Bytes` values (encoded as is)
    -   `BytesBacked` values, which includes [`String`](/puya/api/algopy/#algopy.String), [`BigUInt`](/puya/api/algopy/#algopy.BigUInt), [`Account`](/puya/api/algopy/#algopy.Account) and all of the [ARC-4 types](/puya/api/algopy/arc4/) (encoded as their underlying bytes values)

Logged values are [available to the calling client](https://dev.algorand.co/reference/rest-api/algod/#pendingtransactionresponse) and attached to the transaction record stored on the blockchain ledger.

If you want to emit ARC-28 events in the logs then there is a [purpose-built function for that](/puya/language-guide/arc28/).

Here's an example contract that uses the log method in various ways:

```python
from algopy import BigUInt, Bytes, Contract, log, op

class MyContract(Contract):
    def approval_program(self) -> bool:
        log(0)
        log(b"1")
        log("2")
        log(op.Txn.num_app_args + 3)
        log(Bytes(b"4") if op.Txn.num_app_args else Bytes())
        log(
            b"5",
            6,
            op.Txn.num_app_args + 7,
            BigUInt(8),
            Bytes(b"9") if op.Txn.num_app_args else Bytes(),
            sep="_",
        )
        return True

    def clear_state_program(self) -> bool:
        return True
```