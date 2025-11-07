# [`algopy.itxn`](#module-algopy.itxn)

## Module Contents

### Classes

| [`ApplicationCall`](#algopy.itxn.ApplicationCall)                                 | Creates a set of fields used to submit an Application Call inner transaction   |
|-----------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [`ApplicationCallInnerTransaction`](#algopy.itxn.ApplicationCallInnerTransaction) | Application Call inner transaction                                             |
| [`AssetConfig`](#algopy.itxn.AssetConfig)                                         | Creates a set of fields used to submit an Asset Config inner transaction       |
| [`AssetConfigInnerTransaction`](#algopy.itxn.AssetConfigInnerTransaction)         | Asset Config inner transaction                                                 |
| [`AssetFreeze`](#algopy.itxn.AssetFreeze)                                         | Creates a set of fields used to submit a Asset Freeze inner transaction        |
| [`AssetFreezeInnerTransaction`](#algopy.itxn.AssetFreezeInnerTransaction)         | Asset Freeze inner transaction                                                 |
| [`AssetTransfer`](#algopy.itxn.AssetTransfer)                                     | Creates a set of fields used to submit an Asset Transfer inner transaction     |
| [`AssetTransferInnerTransaction`](#algopy.itxn.AssetTransferInnerTransaction)     | Asset Transfer inner transaction                                               |
| [`InnerTransaction`](#algopy.itxn.InnerTransaction)                               | Creates a set of fields used to submit an inner transaction of any type        |
| [`InnerTransactionResult`](#algopy.itxn.InnerTransactionResult)                   | An inner transaction of any type                                               |
| [`KeyRegistration`](#algopy.itxn.KeyRegistration)                                 | Creates a set of fields used to submit a Key Registration inner transaction    |
| [`KeyRegistrationInnerTransaction`](#algopy.itxn.KeyRegistrationInnerTransaction) | Key Registration inner transaction                                             |
| [`Payment`](#algopy.itxn.Payment)                                                 | Creates a set of fields used to submit a Payment inner transaction             |
| [`PaymentInnerTransaction`](#algopy.itxn.PaymentInnerTransaction)                 | Payment inner transaction                                                      |

### Functions

| [`submit_txns`](#algopy.itxn.submit_txns)   | Submits a group of up to 16 inner transactions parameters   |
|---------------------------------------------|-------------------------------------------------------------|

### API

### *class* algopy.itxn.ApplicationCall(\*, app_id: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., approval_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., clear_state_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., on_completion: [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., extra_program_pages: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., app_args: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[object](https://docs.python.org/3/library/functions.html#object), ...] = ..., accounts: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), ...] = ..., assets: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Asset](api-algopy.md#algopy.Asset), ...] = ..., apps: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Application](api-algopy.md#algopy.Application), ...] = ..., reject_version: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...)

Creates a set of fields used to submit an Application Call inner transaction

### Initialization

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Copies a set of inner transaction parameters

#### set(\*, app_id: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., approval_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., clear_state_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., on_completion: [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., extra_program_pages: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., app_args: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[object](https://docs.python.org/3/library/functions.html#object), ...] = ..., accounts: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), ...] = ..., assets: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Asset](api-algopy.md#algopy.Asset), ...] = ..., apps: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Application](api-algopy.md#algopy.Application), ...] = ..., reject_version: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Updates inner transaction parameter values

#### submit() → algopy.itxn._TResult_co

Submits inner transaction parameters and returns the resulting inner transaction

### *class* algopy.itxn.ApplicationCallInnerTransaction

Application Call inner transaction

#### accounts(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)

Accounts listed in the ApplicationCall transaction

#### app_args(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Arguments passed to the application in the ApplicationCall transaction

#### *property* app_id *: [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID from ApplicationCall transaction

#### *property* approval_program *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Approval program

#### approval_program_pages(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Approval Program as an array of pages

#### apps(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)

Foreign Apps listed in the ApplicationCall transaction

#### assets(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)

Foreign Assets listed in the ApplicationCall transaction

#### *property* clear_state_program *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Clear State program

#### clear_state_program_pages(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Clear State Program as an array of pages

#### *property* created_app *: [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID allocated by the creation of an application

#### *property* extra_program_pages *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

#### *property* fee *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* first_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* first_valid_time *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### *property* global_num_bytes *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state byteslices in ApplicationCall

#### *property* global_num_uint *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state integers in ApplicationCall

#### *property* group_index *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group.
A stand-alone transaction is implicitly element 0 in a group of 1

#### *property* last_log *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The last message emitted. Empty bytes if none were emitted. Application mode only

#### *property* last_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* lease *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

#### *property* local_num_bytes *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state byteslices in ApplicationCall

#### *property* local_num_uint *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state integers in ApplicationCall

#### logs(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Log messages emitted by an application call

#### *property* note *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

#### *property* num_accounts *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ApplicationArgs

#### *property* num_app_args *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ApplicationArgs

#### *property* num_approval_program_pages *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Approval Program pages

#### *property* num_apps *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Applications

#### *property* num_assets *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Assets

#### *property* num_clear_state_program_pages *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Clear State Program pages

#### *property* num_logs *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of logs

#### *property* on_completion *: [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction)*

ApplicationCall transaction on completion action

#### *property* reject_version *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Application version for which the txn must reject

#### *property* rekey_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

#### *property* sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* txn_id *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

#### *property* type *: [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

#### *property* type_bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

### *class* algopy.itxn.AssetConfig(\*, config_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., total: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., unit_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., asset_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., decimals: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., default_frozen: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., url: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., metadata_hash: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., manager: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., reserve: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., freeze: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., clawback: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...)

Creates a set of fields used to submit an Asset Config inner transaction

### Initialization

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Copies a set of inner transaction parameters

#### set(\*, config_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., total: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., unit_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., asset_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., decimals: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., default_frozen: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., url: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., metadata_hash: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., manager: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., reserve: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., freeze: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., clawback: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Updates inner transaction parameter values

#### submit() → algopy.itxn._TResult_co

Submits inner transaction parameters and returns the resulting inner transaction

### *class* algopy.itxn.AssetConfigInnerTransaction

Asset Config inner transaction

#### *property* asset_name *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The asset name

#### *property* clawback *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* config_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID in asset config transaction

#### *property* created_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID allocated by the creation of an ASA

#### *property* decimals *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of digits to display after the decimal place when displaying the asset

#### *property* default_frozen *: [bool](https://docs.python.org/3/library/functions.html#bool)*

Whether the asset’s slots are frozen by default or not, 0 or 1

#### *property* fee *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* first_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* first_valid_time *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### *property* freeze *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* group_index *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group.
A stand-alone transaction is implicitly element 0 in a group of 1

#### *property* last_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* lease *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

#### *property* manager *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* metadata_hash *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte commitment to unspecified asset metadata

#### *property* note *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

#### *property* rekey_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

#### *property* reserve *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* total *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Total number of units of this asset created

#### *property* txn_id *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

#### *property* type *: [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

#### *property* type_bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

#### *property* unit_name *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Unit name of the asset

#### *property* url *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

URL

### *class* algopy.itxn.AssetFreeze(\*, freeze_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), freeze_account: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str), frozen: [bool](https://docs.python.org/3/library/functions.html#bool), sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...)

Creates a set of fields used to submit a Asset Freeze inner transaction

### Initialization

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Copies a set of inner transaction parameters

#### set(\*, freeze_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., freeze_account: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., frozen: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Updates inner transaction parameter values

#### submit() → algopy.itxn._TResult_co

Submits inner transaction parameters and returns the resulting inner transaction

### *class* algopy.itxn.AssetFreezeInnerTransaction

Asset Freeze inner transaction

#### *property* fee *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* first_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* first_valid_time *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### *property* freeze_account *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address of the account whose asset slot is being frozen or un-frozen

#### *property* freeze_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID being frozen or un-frozen

#### *property* frozen *: [bool](https://docs.python.org/3/library/functions.html#bool)*

The new frozen value, 0 or 1

#### *property* group_index *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group.
A stand-alone transaction is implicitly element 0 in a group of 1

#### *property* last_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* lease *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

#### *property* note *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

#### *property* rekey_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

#### *property* sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* txn_id *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

#### *property* type *: [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

#### *property* type_bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

### *class* algopy.itxn.AssetTransfer(\*, xfer_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), asset_receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str), asset_amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., asset_sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., asset_close_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...)

Creates a set of fields used to submit an Asset Transfer inner transaction

### Initialization

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Copies a set of inner transaction parameters

#### set(\*, xfer_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., asset_amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., asset_sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., asset_receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., asset_close_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Updates transaction parameter values

#### submit() → algopy.itxn._TResult_co

Submits inner transaction parameters and returns the resulting inner transaction

### *class* algopy.itxn.AssetTransferInnerTransaction

Asset Transfer inner transaction

#### *property* asset_amount *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

value in Asset’s units

#### *property* asset_close_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* asset_receiver *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* asset_sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address. Source of assets if Sender is the Asset’s Clawback address.

#### *property* fee *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* first_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* first_valid_time *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### *property* group_index *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group.
A stand-alone transaction is implicitly element 0 in a group of 1

#### *property* last_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* lease *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

#### *property* note *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

#### *property* rekey_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

#### *property* sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* txn_id *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

#### *property* type *: [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

#### *property* type_bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

#### *property* xfer_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID

### *class* algopy.itxn.InnerTransaction(\*, type: [algopy.TransactionType](api-algopy.md#algopy.TransactionType), receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., close_remainder_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., vote_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., selection_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., vote_first: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_last: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_key_dilution: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., non_participation: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., state_proof_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., config_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., total: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., unit_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., asset_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., decimals: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., default_frozen: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., url: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., metadata_hash: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., manager: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., reserve: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., freeze: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., clawback: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., xfer_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., asset_amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., asset_sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., asset_receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., asset_close_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., freeze_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., freeze_account: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., frozen: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., app_id: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., approval_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., clear_state_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., on_completion: [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., extra_program_pages: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., app_args: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[object](https://docs.python.org/3/library/functions.html#object), ...] = ..., accounts: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), ...] = ..., assets: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Asset](api-algopy.md#algopy.Asset), ...] = ..., apps: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Application](api-algopy.md#algopy.Application), ...] = ..., reject_version: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...)

Creates a set of fields used to submit an inner transaction of any type

### Initialization

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Copies a set of inner transaction parameters

#### set(\*, type: [algopy.TransactionType](api-algopy.md#algopy.TransactionType) = ..., receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., close_remainder_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., vote_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., selection_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., vote_first: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_last: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_key_dilution: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., non_participation: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., state_proof_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., config_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., total: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., unit_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., asset_name: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., decimals: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., default_frozen: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., url: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., metadata_hash: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., manager: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., reserve: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., freeze: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., clawback: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., xfer_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., asset_amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., asset_sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., asset_receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., asset_close_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., freeze_asset: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., freeze_account: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., frozen: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., app_id: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., approval_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., clear_state_program: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), ...] = ..., on_completion: [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., global_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_uint: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., local_num_bytes: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., extra_program_pages: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., app_args: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[object](https://docs.python.org/3/library/functions.html#object), ...] = ..., accounts: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), ...] = ..., assets: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Asset](api-algopy.md#algopy.Asset), ...] = ..., apps: [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Application](api-algopy.md#algopy.Application), ...] = ..., reject_version: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Updates inner transaction parameter values

#### submit() → algopy.itxn._TResult_co

Submits inner transaction parameters and returns the resulting inner transaction

### *class* algopy.itxn.InnerTransactionResult

An inner transaction of any type

#### accounts(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)

Accounts listed in the ApplicationCall transaction

#### *property* amount *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### app_args(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Arguments passed to the application in the ApplicationCall transaction

#### *property* app_id *: [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID from ApplicationCall transaction

#### *property* approval_program *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Approval program

#### approval_program_pages(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Approval Program as an array of pages

#### apps(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)

Foreign Apps listed in the ApplicationCall transaction

#### *property* asset_amount *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

value in Asset’s units

#### *property* asset_close_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* asset_name *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The asset name

#### *property* asset_receiver *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* asset_sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address. Source of assets if Sender is the Asset’s Clawback address.

#### assets(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)

Foreign Assets listed in the ApplicationCall transaction

#### *property* clawback *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* clear_state_program *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Clear State program

#### clear_state_program_pages(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Clear State Program as an array of pages

#### *property* close_remainder_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* config_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID in asset config transaction

#### *property* created_app *: [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID allocated by the creation of an application

#### *property* created_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID allocated by the creation of an ASA

#### *property* decimals *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of digits to display after the decimal place when displaying the asset

#### *property* default_frozen *: [bool](https://docs.python.org/3/library/functions.html#bool)*

Whether the asset’s slots are frozen by default or not, 0 or 1

#### *property* extra_program_pages *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

#### *property* fee *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* first_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* first_valid_time *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### *property* freeze *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* freeze_account *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address of the account whose asset slot is being frozen or un-frozen

#### *property* freeze_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID being frozen or un-frozen

#### *property* frozen *: [bool](https://docs.python.org/3/library/functions.html#bool)*

The new frozen value, 0 or 1

#### *property* global_num_bytes *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state byteslices in ApplicationCall

#### *property* global_num_uint *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state integers in ApplicationCall

#### *property* group_index *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group.
A stand-alone transaction is implicitly element 0 in a group of 1

#### *property* last_log *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The last message emitted. Empty bytes if none were emitted. Application mode only

#### *property* last_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* lease *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

#### *property* local_num_bytes *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state byteslices in ApplicationCall

#### *property* local_num_uint *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state integers in ApplicationCall

#### logs(index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int)) → [algopy.Bytes](api-algopy.md#algopy.Bytes)

Log messages emitted by an application call

#### *property* manager *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* metadata_hash *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte commitment to unspecified asset metadata

#### *property* non_participation *: [bool](https://docs.python.org/3/library/functions.html#bool)*

Marks an account nonparticipating for rewards

#### *property* note *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

#### *property* num_accounts *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ApplicationArgs

#### *property* num_app_args *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ApplicationArgs

#### *property* num_approval_program_pages *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Approval Program pages

#### *property* num_apps *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Applications

#### *property* num_assets *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Assets

#### *property* num_clear_state_program_pages *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Clear State Program pages

#### *property* num_logs *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of logs

#### *property* on_completion *: [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction)*

ApplicationCall transaction on completion action

#### *property* receiver *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* reject_version *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Application version for which the txn must reject

#### *property* rekey_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

#### *property* reserve *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* selection_key *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

#### *property* sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* state_proof_key *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

64 byte state proof public key

#### *property* total *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Total number of units of this asset created

#### *property* txn_id *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

#### *property* type *: [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

#### *property* type_bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

#### *property* unit_name *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Unit name of the asset

#### *property* url *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

URL

#### *property* vote_first *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The first round that the participation key is valid.

#### *property* vote_key *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

#### *property* vote_key_dilution *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Dilution for the 2-level participation key

#### *property* vote_last *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The last round that the participation key is valid.

#### *property* xfer_asset *: [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID

### *class* algopy.itxn.KeyRegistration(\*, vote_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., selection_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., vote_first: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_last: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_key_dilution: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., non_participation: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., state_proof_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...)

Creates a set of fields used to submit a Key Registration inner transaction

### Initialization

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Copies a set of inner transaction parameters

#### set(\*, vote_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., selection_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., vote_first: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_last: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., vote_key_dilution: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., non_participation: [bool](https://docs.python.org/3/library/functions.html#bool) = ..., state_proof_key: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Updates inner transaction parameter values

#### submit() → algopy.itxn._TResult_co

Submits inner transaction parameters and returns the resulting inner transaction

### *class* algopy.itxn.KeyRegistrationInnerTransaction

Key Registration inner transaction

#### *property* fee *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* first_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* first_valid_time *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### *property* group_index *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group.
A stand-alone transaction is implicitly element 0 in a group of 1

#### *property* last_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* lease *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

#### *property* non_participation *: [bool](https://docs.python.org/3/library/functions.html#bool)*

Marks an account nonparticipating for rewards

#### *property* note *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

#### *property* rekey_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

#### *property* selection_key *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

#### *property* sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* state_proof_key *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

64 byte state proof public key

#### *property* txn_id *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

#### *property* type *: [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

#### *property* type_bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

#### *property* vote_first *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The first round that the participation key is valid.

#### *property* vote_key *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

#### *property* vote_key_dilution *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Dilution for the 2-level participation key

#### *property* vote_last *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The last round that the participation key is valid.

### *class* algopy.itxn.Payment(\*, receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str), amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., close_remainder_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...)

Creates a set of fields used to submit a Payment inner transaction

### Initialization

#### copy() → [Self](https://docs.python.org/3/library/typing.html#typing.Self)

Copies a set of inner transaction parameters

#### set(\*, receiver: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., amount: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = ..., close_remainder_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., sender: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ..., fee: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int) = 0, note: [algopy.String](api-algopy.md#algopy.String) | [algopy.Bytes](api-algopy.md#algopy.Bytes) | [str](https://docs.python.org/3/library/stdtypes.html#str) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) = ..., rekey_to: [algopy.Account](api-algopy.md#algopy.Account) | [str](https://docs.python.org/3/library/stdtypes.html#str) = ...) → [None](https://docs.python.org/3/library/constants.html#None)

Updates inner transaction parameter values

#### submit() → algopy.itxn._TResult_co

Submits inner transaction parameters and returns the resulting inner transaction

### *class* algopy.itxn.PaymentInnerTransaction

Payment inner transaction

#### *property* amount *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* close_remainder_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* fee *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

#### *property* first_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* first_valid_time *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

#### *property* group_index *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group.
A stand-alone transaction is implicitly element 0 in a group of 1

#### *property* last_valid *: [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

#### *property* lease *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

#### *property* note *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

#### *property* receiver *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* rekey_to *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

#### *property* sender *: [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

#### *property* txn_id *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

#### *property* type *: [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

#### *property* type_bytes *: [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

### algopy.itxn.submit_txns(\_t1: algopy.itxn._InnerTransaction[algopy.itxn._T1], \_t2: algopy.itxn._InnerTransaction[algopy.itxn._T2], \_t3: algopy.itxn._InnerTransaction[algopy.itxn._T3], \_t4: algopy.itxn._InnerTransaction[algopy.itxn._T4], \_t5: algopy.itxn._InnerTransaction[algopy.itxn._T5], \_t6: algopy.itxn._InnerTransaction[algopy.itxn._T6], \_t7: algopy.itxn._InnerTransaction[algopy.itxn._T7], \_t8: algopy.itxn._InnerTransaction[algopy.itxn._T8], \_t9: algopy.itxn._InnerTransaction[algopy.itxn._T9], \_t10: algopy.itxn._InnerTransaction[algopy.itxn._T10], \_t11: algopy.itxn._InnerTransaction[algopy.itxn._T11], \_t12: algopy.itxn._InnerTransaction[algopy.itxn._T12], \_t13: algopy.itxn._InnerTransaction[algopy.itxn._T13], \_t14: algopy.itxn._InnerTransaction[algopy.itxn._T14], \_t15: algopy.itxn._InnerTransaction[algopy.itxn._T15], \_t16: algopy.itxn._InnerTransaction[algopy.itxn._T16], /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[algopy.itxn._T1, algopy.itxn._T2, algopy.itxn._T3, algopy.itxn._T4, algopy.itxn._T5, algopy.itxn._T6, algopy.itxn._T7, algopy.itxn._T8, algopy.itxn._T9, algopy.itxn._T10, algopy.itxn._T11, algopy.itxn._T12, algopy.itxn._T13, algopy.itxn._T14, algopy.itxn._T15, algopy.itxn._T16]

Submits a group of up to 16 inner transactions parameters

* **Returns:**
  A tuple of the resulting inner transactions
