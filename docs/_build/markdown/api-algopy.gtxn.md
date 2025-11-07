# [`algopy.gtxn`](#module-algopy.gtxn)

## Module Contents

### Classes

| [`ApplicationCallTransaction`](#algopy.gtxn.ApplicationCallTransaction)   | Application call group transaction   |
|---------------------------------------------------------------------------|--------------------------------------|
| [`AssetConfigTransaction`](#algopy.gtxn.AssetConfigTransaction)           | Asset config group transaction       |
| [`AssetFreezeTransaction`](#algopy.gtxn.AssetFreezeTransaction)           | Asset freeze group transaction       |
| [`AssetTransferTransaction`](#algopy.gtxn.AssetTransferTransaction)       | Asset transfer group transaction     |
| [`KeyRegistrationTransaction`](#algopy.gtxn.KeyRegistrationTransaction)   | Key registration group transaction   |
| [`PaymentTransaction`](#algopy.gtxn.PaymentTransaction)                   | Payment group transaction            |
| [`Transaction`](#algopy.gtxn.Transaction)                                 | Group Transaction of any type        |
| [`TransactionBase`](#algopy.gtxn.TransactionBase)                         | Shared transaction properties        |

### API

### *class* algopy.gtxn.ApplicationCallTransaction(group_index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int))

Application call group transaction

### Initialization

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

### *class* algopy.gtxn.AssetConfigTransaction(group_index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int))

Asset config group transaction

### Initialization

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

### *class* algopy.gtxn.AssetFreezeTransaction(group_index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int))

Asset freeze group transaction

### Initialization

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

### *class* algopy.gtxn.AssetTransferTransaction(group_index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int))

Asset transfer group transaction

### Initialization

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

### *class* algopy.gtxn.KeyRegistrationTransaction(group_index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int))

Key registration group transaction

### Initialization

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

### *class* algopy.gtxn.PaymentTransaction(group_index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int))

Payment group transaction

### Initialization

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

### *class* algopy.gtxn.Transaction(group_index: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int))

Group Transaction of any type

### Initialization

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

### *class* algopy.gtxn.TransactionBase

Shared transaction properties

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
