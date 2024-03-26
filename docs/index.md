# Algorand Python

Algorand Python is a partial implementation of the Python programming language that runs on the AVM. It includes a statically typed framework for development of Algorand smart contracts and logic signatures, with Pythonic interfaces to underlying AVM functionality that works with standard Python tooling.

Algorand Python is compiled for execution on the AVM by PuyaPy, an optimising compiler that ensures the resulting AVM bytecode execution semantics that match the given Python code. PuyaPy produces output that is directly compatible with [AlgoKit typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to make deployment and calling easy.

## Compiler installation

The minimum supported Python version for running the PuyaPy compiler is 3.12.

You can install the PuyaPy compiler globally using [pipx](https://pipx.pypa.io/stable/):

```shell
pipx install puya
```

Alternatively, it can be installed per project. For example, if you're using [poetry](https://python-poetry.org),
you can install it as a dev-dependency like so:

```shell
poetry add -G dev puya
```

Or if you just want to play with some examples, you can clone the repo and have a poke around:

```shell
git clone https://github.com/algorandfoundation/puya.git
cd puya
poetry install
poetry shell
# compile the "Hello World" example
puyapy examples/hello_world
```

## Compiler usage

To check that you can run the `puyapy` command successfully after installation, you can run the
help command:

    puyapy -h

To compile a contract or contracts, just supply the path(s) - either to the .py files themselves,
or the containing directories. In the case of containing directories, any (non-abstract) contracts
discovered therein will be compiled, allowing you to compile multiple contracts at once. You can
also supply more than one path at a time to the compiler.

e.g. either `puyapy my_project/` or `puyapy my_project/contract.py` will work to compile a single contract.

! TODO: make and link a page with all compiler CLI options

## Programming with Algorand Python

To get started developing with Algorand Python, please take a look at the [Language Guide](language-guide.md).

```{toctree}
---
maxdepth: 2
caption: Contents
hidden: true
---

language-guide
principles
api
```
