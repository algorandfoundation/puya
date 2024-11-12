# PuyaPy compiler

The PuyaPy compiler is a multi-stage, optimising compiler that takes Algorand Python and prepares it for execution on the AVM. PuyaPy ensures the resulting AVM bytecode execution semantics that match the given Python code. PuyaPy produces output that is directly compatible with [AlgoKit typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to make deployment and calling easy (among other formats).

The PuyaPy compiler is based on the [Puya compiler architecture](#compiler-architecture), which allows for multiple frontend languages to leverage the majority of the compiler logic so adding new frontend languages for execution on Algorand is relatively easy.

## Compiler installation

The minimum supported Python version for running the PuyaPy compiler is 3.12.

There are three ways of installing the PuyaPy compiler.

1. You can install [AlgoKit CLI](https://github.com/algorandfoundation/algokit-cli?tab=readme-ov-file#install) and you can then use the `algokit compile py` command.
2. You can install the PuyaPy compiler into your project and thus lock the compiler version for that project:
    ```shell
    pip install puyapy
    # OR
    poetry add puyapy --group=dev
    ```
    Note: if you do this then when you use`algokit compile py` within that project directory it will invoke the installed compiler rather than a global one.
3. You can install the compiler globally using [pipx](https://pipx.pypa.io/stable/):
    ```shell
    pipx install puya
    ```

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

## Using the compiler

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

## Compiler architecture

The PuyaPy compiler is based on the Puya compiler architecture, which allows for multiple frontend languages to leverage the majority of the compiler logic so adding new frontend languages for execution on Algorand is relatively easy.

The PuyaPy compiler takes Algorand Python through a series of transformations with each transformation serving a specific purpose:

    Python code
        -> Python Abstract Syntax Tree (AST)
        -> MyPy AST
        -> Puya AST (AWST)
        -> Intermediate Representation (IR) in SSA form
        -> Optimizations (multiple rounds)
        -> Destructured IR
        -> Optimizations (multiple rounds)
        -> Memory IR (MIR)
        -> Optimizations (multiple rounds)
        -> TealOps IR
        -> Optimizations (multiple rounds)
        -> TEAL code
        -> AVM bytecode

While this may appear complex, splitting it in this manner allows for each step to be expressed in a simple form to do one thing (well) and allows us to make use of industry research into compiler algorithms and formats.

## Type checking

The first and second steps of the [compiler pipeline](#compiler-architecture) are significant to note, because it's where we perform type checking. We leverage [MyPy](https://mypy-lang.org/) to do this, so we recommend that you install and use the latest version of MyPy in your development environment to get the best typing information that aligns to what the PuyaPy compiler expects. This should work with standard Python tooling e.g. with Visual Studio Code, PyCharm, et. al.

The easiest way to get a productive development environment with Algorand Python is to instantiate a template with AlgoKit via `algokit init -t python`. This will give you a full development environment with intellisense, linting, automatic formatting, breakpoint debugging, deployment and CI/CD.

Alternatively, you can construct your own environment by configuring MyPy, Ruff, etc. with the same configuration files [used by that template](https://github.com/algorandfoundation/algokit-python-template).

The MyPy config that PuyaPy uses is in [compile.py](https://github.com/algorandfoundation/puya/blob/main/src/puya/compile.py#L79)

## Compiler usage

The options available for the compile can be seen by executing `puyapy -h` or `algokit compile py -h`:

```
puyapy [-h] [--version] [-O {0,1,2}]
    [--output-teal | --no-output-teal] [--output-arc32 | --no-output-arc32]
    [--output-client | --no-output-client] [--out-dir OUT_DIR]
    [--log-level {notset,debug,info,warning,error,critical}] [-g {0,1,2}] [--output-awst | --no-output-awst]
    [--output-ssa-ir | --no-output-ssa-ir] [--output-optimization-ir | --no-output-optimization-ir]
    [--output-destructured-ir | --no-output-destructured-ir] [--output-memory-ir | --no-output-memory-ir]
    [--target-avm-version {10}]
    [--locals-coalescing-strategy {root_operand,root_operand_excluding_args,aggressive}]
    PATH [PATH ...]
```

### Options

| Option                                                   | Description                                                                                                                                                           | Default                 |
|----------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------|
| `-h`, `--help`                                           | Show the help message and exit                                                                                                                                        | N/A                     |
| `--version`                                              | Show program's version number and exit                                                                                                                                | N/A                     |
| `-O {0,1,2}` <br />`--optimization-level {0,1,2}`        | Set optimization level of output TEAL / AVM bytecode                                                                                                                  | `1`                     |
| `--output-teal`, `--no-output-teal`                      | Output TEAL                                                                                                                                                           | `True`                  |
| `--output-arc32`, `--no-output-arc32`                    | Output {contract}.arc32.json ARC-32 app spec file if the contract is an ARC-4 contract                                                                                | `True`                  |
| `--output-arc56`, `--no-output-arc56`                    | Output {contract}.arc56.json ARC-56 app spec file if the contract is an ARC-4 contract                                                                                | `False`                 |
| `--output-client`, `--no-output-client`                  | Output Algorand Python contract client for typed ARC4 ABI calls                                                                                                       | `False`                 |
| `--output-bytecode`, `--no-output-bytecode`              | Output AVM bytecode                                                                                                                                                   | `False`                 |
| `--out-dir OUT_DIR`                                      | The path for outputting artefacts                                                                                                                                     | Same folder as contract |
| `--log-level {notset,debug,info,warning,error,critical}` | Minimum level to log to console                                                                                                                                       | `info`                  |
| `-g {0,1,2}`, `--debug-level {0,1,2}`                    | Output debug information level<br /> `0` = No debug annotations <br /> `1` = Output debug annotations <br /> `2` = Reserved for future use, currently the same as `1` | `1`                     |
| `--template-var`                                         | Allows specifying template values. Can be used multiple times, see below for examples                                                                                 | N/A                     |
| `--template-vars-prefix`                                 | Prefix to use for template variables                                                                                                                                  | "TMPL_"                 |

### Defining template values

[Template Variables](#algopy.TemplateVar), can be replaced with literal values during compilation to bytecode using the `--template-var` option.
Additionally, Algorand Python functions that create AVM bytecode, such as [compile_contract](#algopy.compile_contract) and [compile_logicsig](#algopy.compile_logicsig), can also provide the specified values.

#### Examples of Variable Definitions

The table below illustrates how different variables and values can be defined:

| Variable Type                     | Example Algorand Python                          | Value definition example |
|--------------------------|-------------------------------------------|--------------------------|
| [UInt64](#algopy.UInt64) | `algopy.TemplateVar[UInt64]("SOME_INT")`  | `SOME_INT=1234`          |
| [Bytes](#algopy.Bytes)   | `algopy.TemplateVar[Bytes]("SOME_BYTES")` | `SOME_BYTES=0x1A2B`      |
| [String](#algopy.String) | `algopy.TemplateVar[String]("SOME_STR")`  | `SOME_STR="hello"`       |

All template values specified via the command line are prefixed with "TMPL_" by default. 
The default prefix can be modified using the `--template-vars-prefix` option.

### Advanced options

There are additional compiler options that allow you to tweak the behaviour in more advanced ways or tweak the output to receive intermediate representations from the compiler pipeline. Most users won't need to use these options unless exploring the inner workings of the compiler or performing more advanced optimisations.

| Option                                                                               | Description                                                                                                                       | Default        |
| ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| `--output-awst`, `--no-output-awst`                                                  | Output parsed result of Puya Abstract Syntax Tree (AWST)                                                                          | `False`        |
| `--output-ssa-ir`, `--no-output-ssa-ir`                                              | Output the Intermediate Representation (IR) in Single Static Assignment (SSA) form before optimisations form                      | `False`        |
| `--output-optimization-ir`, `--no-output-optimization-ir`                            | Output the IR after each optimization step                                                                                        | `False`        |
| `--output-destructured-ir`, `--no-output-destructured-ir`                            | Output the IR after SSA destructuring and before Memory IR (MIR)                                                                  | `False`        |
| `--output-memory-ir`, `--no-output-memory-ir`                                        | Output Memory IR (MIR) before lowering to TealOps IR                                                                              |                |
| `--target-avm-version {10}`                                                          | Target AVM version for the output                                                                                                 | `10`           |
| `--locals-coalescing-strategy {root_operand,root_operand_excluding_args,aggressive}` | Strategy choice for out-of-ssa local variable coalescing. The best choice for your app is best determined through experimentation | `root_operand` |

## Sample `pyproject.toml`

A sample `pyproject.toml` file with known good configuration is:

```ini
[tool.poetry]
name = "algorand_python_contract"
version = "0.1.0"
description = "Algorand smart contracts"
authors = ["Name <name@domain.tld>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.12"
algokit-utils = "^2.2.0"
python-dotenv = "^1.0.0"
algorand-python = "^1.0.0"

[tool.poetry.group.dev.dependencies]
black = { extras = ["d"], version = "*" }
ruff = "^0.1.6"
mypy = "*"
pytest = "*"
pytest-cov = "*"
pip-audit = "*"
pre-commit = "*"
puyapy = "^1.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.ruff]
line-length = 120
select = [
  "E",
  "F",
  "ANN",
  "UP",
  "N",
  "C4",
  "B",
  "A",
  "YTT",
  "W",
  "FBT",
  "Q",
  "RUF",
  "I",
]
ignore = [
  "ANN101", # no type for self
  "ANN102", # no type for cls
]
unfixable = ["B", "RUF"]

[tool.ruff.flake8-annotations]
allow-star-arg-any = true
suppress-none-returning = true

[tool.pytest.ini_options]
pythonpath = ["smart_contracts", "tests"]

[tool.mypy]
files = "smart_contracts/"
python_version = "3.12"
disallow_any_generics = true
disallow_subclassing_any = true
disallow_untyped_calls = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_return_any = true
strict_equality = true
strict_concatenate = true
disallow_any_unimported = true
disallow_any_expr = true
disallow_any_decorated = true
disallow_any_explicit = true
```
