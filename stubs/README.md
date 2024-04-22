# Algorand Python framework - API for writing Algorand Python smart contracts

## Installation

The minimum supported Python version for writing Algorand Python smart contracts is 3.12.

You can install the Algorand Python framework from PyPI into your project virtualenv:
```shell
pip install algorand-python
```
If you're using poetry for dependency and virutalenv management, you can add it that way with
`poetry add algorand-python`.

Once you have installed the Algorand Python framework, you can access the type definitions from the `algopy` module, e.g.
```python
from algopy import Contract
```

For more details on using this API and the puyapy compiler see https://algorandfoundation.github.io/puya/

## Versioning

The Algorand Python API follows [semver](https://semver.org/) versioning to indicate the type of changes in the API 

### Major
Increases in the major version number are a breaking change that will require updating existing contracts due to 
incompatible changes to the API. Generally this would coincide with compiler changes requiring a major version update.

### Minor 
Increases in the minor version number indicate new functionality, existing contracts do not need to be updated, but an updated compiler is required.

### Patch
Increase in the patch version number indicate a fix to the API itself, or updated documentation, these changes do not require an updated compiler.
