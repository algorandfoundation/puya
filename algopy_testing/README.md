# Algorand Python Testing framework

Test your Algorand Python smart contracts using your favorite python testing tools.

## Installation

TBD

## Coverage check

Execute below to see current progress on implementing algopy stubs for use in testing contexts:

```bash
poetry run poe gen_stub_cov
```

Will compare and display every class and function from algopy stubs against whats implemented.

## Regenerating test contracts

Execute below to regenerate the test contracts:

```bash
poetry run poe gen_test_artifacts
```

For each, contract in folders at `tests/artifacts/*` folder, the script will:

1. Compile the contract using `puyapy` from sibling folder (since we are in the same monorepo), storing avm files under `/tests/{contract_name}/data/*`.
2. Generate the client using `algokit generate client`, storing the python typed client under `/tests/{contract_name}/client.py`.

## Linting codebase

Execute below to lint the codebase:

```bash
poetry run poe pre_commit # executes black -> ruff -> mypy
```
