# Puya - Algorand TEAL compiler + AlgoPy Python language bindings

[Project background and guiding principles](docs/principles.md).

## Installation

The minimum supported Python version for running Puya itself is 3.12.

You can install the developer preview of Puya directly from this repo by using [pipx](https://pipx.pypa.io/stable/):
```shell
pipx install git+https://github.com/algorandfoundation/puya.git
```

Or you can clone the repo and have a poke around without installing it globally.

```shell
git clone https://github.com/algorandfoundation/puya.git
cd puya
poetry install
poetry shell
```

Note that with this method you'll need to activate the virtual environment created by poetry
before using the puya command in each new shell that you open - you can do this by running
`poetry shell` in the `puya` directory.

To check that you can run the `puya` command successfully after that, you can run the help command:

`puya -h`

To compile a contract or contracts, just supply the path(s) - either to the .py files themselves,
or the containing directories. In the case of containing directories, any contracts discovered
therein will be compiled, allowing you to compile multiple contracts at once. You can also supply
more than one path at a time to the compiler.

## Language guide

Coming soon! For now, refer to the examples to see what's possible.

## Examples

- [voting](examples/voting/voting.py)
- [AMM](examples/amm/contract.py)
- [auction](examples/TEALScript/auction/contract.py)
- [non-ABI calculator](examples/calculator/contract.py)
- [local storage](examples/local_storage)
