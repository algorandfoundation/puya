# AlgoPy - API for writing Algorand Python smart contracts

## Installation

### API
The minimum supported Python version for writing Algorand Python smart contracts is 3.12.

You can install AlgoPy from PyPI into your project virtualenv:
```shell
pip install algopy-stubs
```
If you're using poetry for dependency and virutalenv management, you can add it that way with
`poetry add algopy-stubs`.

### Compiler

To compile a smart contract, you will also need the PuyaPy compiler, this can either be installed globally (e.g. `pipx install puya`), or
as a dev dependency in your project virtualenv (e.g. `poetry add puya --group=dev`)

## Usage

To compile a contract or contracts, just supply the path(s) - either to the .py files themselves,
or the containing directories. In the case of containing directories, any contracts discovered
therein will be compiled, allowing you to compile multiple contracts at once. You can also supply
more than one path at a time to the compiler.

e.g. `puyapy my_project/` or `puyapy my_project/contract.py` will work to compile a single contract.

## Examples

 There are many examples in this repo, here are some of the more useful ones that showcase what
 is possible.

- [hello world](examples/hello_world/contract.py)
- [hello world (ARC4)](examples/hello_world_arc4/contract.py)
- [voting](examples/voting/voting.py)
- [AMM](examples/amm/contract.py)
- [auction](examples/auction/contract.py)
- [non-ABI calculator](examples/calculator/contract.py)
- [local storage](examples/local_state)

The compiled output is available under the `out/` directory alongside these, e.g. the approval
TEAL for `voting` is available at [examples/voting/out/voting.approval.teal](examples/voting/out/voting.approval.teal).
