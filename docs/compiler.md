# PuyaPy compiler

The PuyaPy compiler is a multi-stage, optimising compiler that takes Algorand Python and prepares it for execution on the AVM. PuyaPy ensures the resulting AVM bytecode execution semantics that match the given Python code. PuyaPy produces output that is directly compatible with [AlgoKit typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to make deployment and calling easy (among other formats).

The PuyaPy compiler is based on the Puya compiler architecture, which allows for multiple frontend languages to leverage the majority of the compiler logic so adding new frontend languages for execution on Algorand is relatively easy.

## Compiler installation

The minimum supported Python version for running the PuyaPy compiler is 3.12.

There are three ways of installing the PuyaPy compiler.

1. You can install [AlgoKit CLI](https://github.com/algorandfoundation/algokit-cli?tab=readme-ov-file#install) and you can then use the `algokit compile py` command.
2. You can install the PuyaPy compiler into your project and thus lock the compiler version for that project:
   `shell
   pip install puyapy
    # OR
    poetry add puyapy --group=dev
    `Note: if you do this then when you use`algokit compile py` within that project directory it will invoke the installed compiler rather than a global one.
3. You can install the compiler globally using [pipx](https://pipx.pypa.io/stable/):
   `shell
pipx install puya
`

Alternatively, it can be installed per project. For example, if you're using [poetry](https://python-poetry.org),
you can install it as a dev-dependency like so:

If you just want to play with some examples, you can clone the repo and have a poke around:

```shell
git clone https://github.com/algorandfoundation/puya.git
cd puya
poetry install
poetry shell
# compile the "Hello World" example
puyapy examples/hello_world
```

## Compiler usage

To check that you can run the compiler successfully after installation, you can run the
help command:

```
puyapy -h
# OR
algokit compile py -h
```

To compile a contract or contracts, just supply the path(s) - either to the .py files themselves,
or the containing directories. In the case of containing directories, any (non-abstract) contracts
discovered therein will be compiled, allowing you to compile multiple contracts at once. You can
also supply more than one path at a time to the compiler.

e.g. either `puyapy my_project/` or `puyapy my_project/contract.py` will work to compile a single contract.

## Type checking

The PuyaPy compiler takes Algorand Python through a series of transformations:

    Python AST -> MyPy AST -> AWST -> IR -> MIR -> TEAL -> AVM bytecode

The first and second steps are significant to note, because it's where we perform type checking. We leverage [MyPy](https://mypy-lang.org/) to do this, so we recommend that you install and use the latest version of MyPy in your development environment to get the best typing information that aligns to what the PuyaPy compiler expects. This should work with standard Python tooling e.g. with Visual Studio Code, PyCharm, et. al.

The easiest way to get a productive development environment with Algorand Python is to instantiate a template with AlgoKit via `algokit init -t python`. This will give you a full development environment with intellisense, linting, automatic formatting, breakpoint debugging, deployment and CI/CD.

Alternatively, you can construct your own environment by configuring MyPy, Ruff, etc. with the same configuration files [used by that template](https://github.com/algorandfoundation/algokit-python-template).

## Compiler options

todo
