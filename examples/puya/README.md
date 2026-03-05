# Puya Example Contracts

A progressive suite of 16 Algorand smart contract examples demonstrating Puya/algopy features, from a basic counter to full DeFi and DAO patterns. Each example compiles to TEAL and deploys to LocalNet.

## Prerequisites

- [Python](https://www.python.org/) >= 3.12
- [AlgoKit CLI](https://github.com/algorandfoundation/algokit-cli) installed with LocalNet running (`algokit localnet start`)

## Quick Start

```bash
# Install example dependencies
cd examples/puya
uv sync

# Run a single example (compiles, deploys, and exercises the contract)
uv run python 01-counter/index.py

# Run all 16 examples
./verify-all.sh
```

## Examples

| # | Name | Description | Key Features |
|---|------|-------------|--------------|
| 01 | [Counter](01-counter/) | GlobalState and UInt64 arithmetic | `UInt64`, uint64 arithmetic (`+=`, `-=`), `@arc4.abimethod(create="require")` |
| 02 | [Greeter](02-greeter/) | String handling and readonly methods | `String` params/returns, `@arc4.abimethod(readonly=True)`, docstrings |
| 03 | [Logic Sig Gate](03-logic-sig-gate/) | LogicSig with template variables and Ed25519 signature verification | `@logicsig`, `TemplateVar`, `op.ed25519verify_bare` |
| 04 | [Type Explorer](04-type-explorer/) | `UInt64`, `BigUInt`, and `Bytes` types with AVM opcodes and wide math | `UInt64`/`BigUInt`/`Bytes` conversions, `Bytes.from_hex`, `op.sha256`, `op.addw` |
| 05 | [Membership Registry](05-membership-registry/) | Local state management with opt-in and close-out lifecycle | `GlobalState`, `LocalState`, opt-in/close-out, `Account` properties |
| 06 | [Key-Value Store](06-key-value-store/) | Box and BoxMap storage with CRUD operations | `Box`, `BoxMap`, `.extract`/`.replace`/`.splice`, `StateTotals` |
| 07 | [Array Playground](07-array-playground/) | Native arrays, FixedArray, ReferenceArray, and iteration patterns | `Array`, `FixedArray`, `ReferenceArray`, `ImmutableArray`, `urange()` |
| 08 | [Object Tuples](08-object-tuples/) | Structs as method params, return values, and state | `Struct`, `GlobalState`, named tuples, `frozen=True` |
| 09 | [Token Manager](09-token-manager/) | Inner transactions for full ASA lifecycle management | `itxn.AssetConfig`, `itxn.AssetTransfer`, `itxn.AssetFreeze`, bootstrapping guard |
| 10 | [Multi-Txn Distributor](10-multi-txn-distributor/) | Grouped inner transactions and outer group transaction access | `itxn.submit_txns`, `gtxn`, `TransactionType` |
| 11 | [Contract Factory](11-contract-factory/) | `compile_contract` and contract-to-contract calls | `compile_contract`, `arc4.abi_call`, `TemplateVar` |
| 12 | [Event Logger](12-event-logger/) | ARC-28 event emission with native types and positional args | `arc4.emit()` with `arc4.Struct` types, positional and signature forms |
| 13 | [Inheritance Showcase](13-inheritance-showcase/) | Single and multi-level inheritance with abstract classes | `abc.abstractmethod`, `super()` calls, method overrides |
| 14 | [Crypto Vault](14-crypto-vault/) | Hash functions, signature verification, and scratch space | `op.sha256`/`op.sha3_256`/`op.keccak256`, `ensure_budget`, `scratch_slots` |
| 15 | [DEX Pool](15-dex-pool/) | Constant-product AMM (x*y=k) with inner transactions and wide math | Reserves, `op.mulw`/`op.divmodw`, `op.bsqrt`, `itxn.submit_txns` |
| 16 | [Governance DAO](16-governance-dao/) | Full DAO proposal lifecycle using Box/BoxMap storage and ARC-28 events | `Box`, `BoxMap`, `arc4.Struct`, `arc4.DynamicArray`, `arc4.emit()`, `ensure_budget` |

## Shared Modules

- [`shared/utils.py`](shared/utils.py) — Runtime helpers for compilation, app-spec loading, assertions, and console output

## Troubleshooting

**LocalNet not running**
```
Error: connect ECONNREFUSED 127.0.0.1:4001
```
Start LocalNet with `algokit localnet start` and verify with `algokit localnet status`.

**Missing dependencies**
Make sure you ran `uv sync` in the `examples/puya/` directory before running examples.

**Stale LocalNet state**
If examples fail after a previous run, reset LocalNet to clear all deployed apps and accounts:
```bash
algokit localnet reset
```

**Import errors for `shared` module**
Ensure you are running examples with `uv run python` from the `examples/puya/` directory so that the local `pyproject.toml` is used.

## Development — Adding New Examples

1. Create a new directory following the naming convention: `NN-kebab-case-name/`
2. Add a `contract.py` with a docstring header describing what the example demonstrates
3. Add an `index.py` that compiles, deploys, and exercises the contract
4. Add the directory name to the `EXAMPLES` array in `verify-all.sh`
5. Add a row to the examples table in this README
