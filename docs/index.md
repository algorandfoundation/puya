# Algorand Python & PuyaPy: <br/> An optimising Python to TEAL compiler

Algorand Python is a semantically and syntactically compatible, typed Python language that works 
with standard Python tooling and allows you to develop smart contracts (apps) and smart signatures
(logic signatures) for deployment on the Algorand Virtual Machine (AVM).

This is done by compiling Algorand Python using the PuyaPy compiler, which takes the Python code
and outputs valid TEAL code with execution semantics that match the given Python code.

Algorand Python is a statically-typed subset of valid Python syntax. Importantly, that subset has
identical semantics when comparing Python behaviour and behaviour of the executed TEAL.

## Compiler installation

The minimum supported Python version for running the PuyaPy compiler is 3.12.

You can install PuyaPy globally using [pipx](https://pipx.pypa.io/stable/):

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

To get started developing with Python on Algorand, please take a look at our [Language Guide](language-guide.md).

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
