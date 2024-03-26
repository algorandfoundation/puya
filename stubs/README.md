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
