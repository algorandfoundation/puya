# PuyaPy - Python to TEAL compiler

> [!WARNING]
> PuyaPy is currently in alpha / developer preview. It is not recommended for production usage yet.

PuyaPy is an optimising TEAL compiler that allows you to write code to execute on the Algorand
Virtual Machine (AVM) with Python syntax.

[Project background and guiding principles](docs/principles.md).

PuyaPy supports a strongly-typed subset of valid Python syntax. Importantly, that subset has 
identical semantics when comparing Python behaviour and behaviour of the executed TEAL. 
For example, `foo = spam() or eggs()` will only execute `eggs()` if `bool(spam())` is `False`.

## Installation

The minimum supported Python version for running PuyaPy itself is 3.12.

You can install the developer preview of PuyaPy directly from this repo into your project virtualenv:
```shell
pip install git+https://github.com/algorandfoundation/puya.git
```
If you're using poetry for dependency and virutalenv management, the above URL should work with
`poetry add`.

Or if you just want to play with some examples, you can clone the repo and have a poke around.

```shell
git clone https://github.com/algorandfoundation/puya.git
cd puya
poetry install
poetry shell
```

Note that with this method you'll need to activate the virtual environment created by poetry
before using the puyapy command in each new shell that you open - you can do this by running
`poetry shell` in the `puya` directory.

## Compiler usage

To check that you can run the `puyapy` command successfully after that, you can run the help command:

`puyapy -h`

To compile a contract or contracts, just supply the path(s) - either to the .py files themselves,
or the containing directories. In the case of containing directories, any contracts discovered
therein will be compiled, allowing you to compile multiple contracts at once. You can also supply
more than one path at a time to the compiler.

e.g. `puyapy my_project/` or `puyapy my_project/contract.py` will work to compile a single contract.

## Language fundamentals

> [!NOTE]
> A more comprehensive guide is coming soon!

### Contracts

A smart contract is defined within a single class. You can extend other contracts (through inheritance),
and also define standalone functions and reference them. This also works across different Python 
packages - in other words, you can have a Python library with common functions and re-use that
library across multiple projects!

All contracts must inherit from the base class `puyapy.Contract` - either directly or indirectly,
which can include inheriting from `puyapy.ARC4Contract`. For a non-ARC4 contract, a contract class
must implement an `approval_program` and a `clear_state_program` method. For ARC4 contracts, these
methods will be implemented for you, although you can optionally provide a `clear_state_program`
(the default implementation just always approves).

As an example, this is a valid contract that always approves:

```python
import puyapy

class Contract(puyapy.Contract):
    def approval_program(self) -> bool:
        return True
    
    def clear_state_program(self) -> bool:
        return True
```

And here is a valid ARC4 contract:

```python
import puyapy

class ABIContract(puyapy.ARC4Contract):
    """This contract can be created, but otherwise does nothing"""
    pass

```

## Examples

 There are many examples in this repo, here are some of the more useful ones that showcase what
 is possible.

- [voting](examples/voting/voting.py)
- [AMM](examples/amm/contract.py)
- [auction](examples/TEALScript/auction/contract.py)
- [non-ABI calculator](examples/calculator/contract.py)
- [local storage](examples/local_storage)

The compiled output is available under the `out/` directory alongside these, e.g. the approval
TEAL for `voting` is available at [examples/voting/out/voting.approval.teal](examples/voting/out/voting.approval.teal).
