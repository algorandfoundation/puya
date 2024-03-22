# Algorand Python & PuyaPy: Python to TEAL compiler

Algorand Python is a semantically and syntactically compatible, typed Python language that works with standard Python tooling and allows you to express smart contracts (apps) and smart signatures (logic signatures) for deployment on the Algorand Virtual Machine (AVM).

This is done by compiling Algorand Python using the Puya compiler, which takes Algorand Python and outputs valid, optimised TEAL code with execution semantics that match the given Python code.

[Project background and guiding principles](principles.md).

PuyaPy supports a statically-typed subset of valid Python syntax. Importantly, that subset has
identical semantics when comparing Python behaviour and behaviour of the executed TEAL.
For example, `foo = spam() or eggs()` will only execute `eggs()` if `bool(spam())` is `False`.

## Compiler installation

The minimum supported Python version for running PuyaPy itself is 3.12.

You can install the developer preview of PuyaPy from PyPI into your project virtualenv:

```shell
pip install puya
```

Alternatively, if you're using poetry for dependency and virutalenv management, you can add it that way with:

```shell
poetry add puya
```

Or if you just want to play with some examples, you can clone the repo and have a poke around:

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

For more in depth details see our [Language Guide](language_guide.md).

```{toctree}
---
maxdepth: 2
caption: Contents
hidden: true
---

language_guide
principles
api
```
