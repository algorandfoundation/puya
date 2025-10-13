# PuyaPy compiler

The PuyaPy compiler is a multi-stage, optimising compiler that takes Algorand Python and prepares it for execution on the AVM. PuyaPy ensures the resulting AVM bytecode has execution semantics that match the given Python code. PuyaPy produces output that is directly compatible with [AlgoKit typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to make deployment and calling easy (among other formats).

The PuyaPy compiler is based on the [Puya compiler architecture](https://github.com/algorandfoundation/puya/blob/main/ARCHITECTURE.md),
which allows for multiple frontend languages to leverage the majority of the compiler logic so adding new frontend languages for execution on Algorand is relatively easy.

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

```shell
poetry add puyapy --group=dev
```

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

## Type checking

The first and second steps of the [compiler pipeline](https://github.com/algorandfoundation/puya/blob/main/ARCHITECTURE.md) are significant to note, because it's where we perform type checking. We leverage [MyPy](https://mypy-lang.org/) to do this, so we recommend that you install and use the latest version of MyPy in your development environment to get the best typing information that aligns to what the PuyaPy compiler expects. This should work with standard Python tooling e.g. with Visual Studio Code, PyCharm, et. al.

The easiest way to get a productive development environment with Algorand Python is to instantiate a template with AlgoKit via `algokit init -t python`. This will give you a full development environment with intellisense, linting, automatic formatting, breakpoint debugging, deployment and CI/CD.

Alternatively, you can construct your own environment by configuring MyPy, Ruff, etc. with the same configuration files [used by that template](https://github.com/algorandfoundation/algokit-python-template).

The MyPy config that PuyaPy uses is in [parse.py](https://github.com/algorandfoundation/puya/blob/8be90f7c84ecd6eaa972e4dbf82f3ec7a616fc75/src/puyapy/parse.py#L274)

## Compiler usage

The options available for the compile can be seen by executing `puyapy -h` or `algokit compile py -h`:

```
Usage: puyapy [ARGS] [OPTIONS]

PuyaPy compiler for compiling Algorand Python to TEAL

╭─ Commands ─────────────────────────────────────────────────────────────────────────────╮
│ --help -h  Display this message and exit.                                              │
│ --version  Display application version.                                                │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Arguments ────────────────────────────────────────────────────────────────────────────╮
│ *  PATH  Files or directories to compile [required]                                    │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Outputs ──────────────────────────────────────────────────────────────────────────────╮
│ Options for controlling what is output and where                                       │
│                                                                                        │
│ --out-dir                             Path for outputting artefacts                    │
│ --log-level                           Minimum level to log to console [choices:        │
│                                       notset, debug, info, warning, error, critical]   │
│                                       [default: info]                                  │
│ --output-teal --no-output-teal        Output TEAL code [default: True]                 │
│ --output-source-map                   Output debug source maps [default: True]         │
│   --no-output-source-map                                                               │
│ --output-arc56 --no-output-arc56      Output {contract}.arc56.json ARC-56 app spec     │
│                                       file [default: True]                             │
│ --output-arc32 --no-output-arc32      Output {contract}.arc32.json ARC-32 app spec     │
│                                       file [default: False]                            │
│ --output-bytecode                     Output AVM bytecode [default: False]             │
│   --no-output-bytecode                                                                 │
│ --output-client                       Output Algorand Python contract client for typed │
│   --no-output-client                  ARC-4 ABI calls [default: False]                 │
│ --debug-level                     -g  Output debug information level, 0 = none, 1 =    │
│                                       debug, 2 = reserved for future use [choices: 0,  │
│                                       1, 2] [default: 1]                               │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Compilation ──────────────────────────────────────────────────────────────────────────╮
│ Options that affect the compilation process, such as optimisation options etc.         │
│                                                                                        │
│ --optimization-level             -O  Set optimization level of output TEAL / AVM       │
│                                      bytecode [choices: 0, 1, 2] [default: 1]          │
│ --target-avm-version                 Target AVM version [choices: 10, 11, 12, 13]      │
│                                      [default: 11]                                     │
│ --resource-encoding                  If "index", then resource types (Application,     │
│                                      Asset, Account) in ABI methods should be passed   │
│                                      as an index into their appropriate foreign array. │
│                                      The default option "value", as of PuyaPy 5.0,     │
│                                      means these values will be passed directly.       │
│                                      [choices: index, value] [default: value]          │
│ --locals-coalescing-strategy         Strategy choice for out-of-ssa local variable     │
│                                      coalescing. The best choice for your app is best  │
│                                      determined through experimentation [choices:      │
│                                      root-operand, root-operand-excluding-args,        │
│                                      aggressive] [default: root-operand]               │
│ --validate-abi-values                Validates ABI transaction arguments by ensuring   │
│   --no-validate-abi-values           they are the correct size [default: True]         │
│ --validate-abi-dynamic-severity      Severity level for unvalidatable dynamic ABI      │
│                                      types [choices: notset, debug, info, warning,     │
│                                      error, critical] [default: warning]               │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Templating ───────────────────────────────────────────────────────────────────────────╮
│ Options for controlling the generation of TEAL template files                          │
│                                                                                        │
│ --template-var          -T  Define template vars for use when assembling via           │
│                             --output-bytecode. Should be specified without the prefix  │
│                             (see --template-vars-prefix), e.g. -T SOME_INT=1234        │
│                             SOME_BYTES=0x1A2B SOME_BOOL=True -T SOME_STR="hello"       │
│ --template-vars-prefix      Define the prefix to use with --template-var [default:     │
│                             TMPL_]                                                     │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Additional outputs ───────────────────────────────────────────────────────────────────╮
│ Controls additional compiler outputs that may be useful to compiler developers.        │
│                                                                                        │
│ --output-awst                     Output parsed result of AWST [default: False]        │
│ --output-awst-json                Output parsed result of AWST as JSON [default:       │
│                                   False]                                               │
│ --output-source-annotations-json  Output source annotations result of AWST parse as    │
│                                   JSON [default: False]                                │
│ --output-ssa-ir                   Output IR (in SSA form) before optimizations         │
│                                   [default: False]                                     │
│ --output-optimization-ir          Output IR after each optimization [default: False]   │
│ --output-destructured-ir          Output IR after SSA destructuring and before MIR     │
│                                   [default: False]                                     │
│ --output-memory-ir                Output MIR before lowering to TEAL [default: False]  │
│ --output-teal-intermediates       Output TEAL before peephole optimization and before  │
│                                   block optimization [default: False]                  │
│ --output-op-statistics            Output statistics about ops used for each program    │
│                                   compiled optimization_level: Set optimization level  │
│                                   of output TEAL / AVM bytecode [default: False]       │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

### Defining template values

[Template Variables](#algopy.TemplateVar), can be replaced with literal values during compilation to bytecode using the `--template-var` option.
Additionally, Algorand Python functions that create AVM bytecode, such as [compile_contract](#algopy.compile_contract) and [compile_logicsig](#algopy.compile_logicsig), can also provide the specified values.

#### Examples of Variable Definitions

The table below illustrates how different variables and values can be defined:

| Variable Type            | Example Algorand Python                   | Value definition example |
| ------------------------ | ----------------------------------------- | ------------------------ |
| [UInt64](#algopy.UInt64) | `algopy.TemplateVar[UInt64]("SOME_INT")`  | `SOME_INT=1234`          |
| [Bytes](#algopy.Bytes)   | `algopy.TemplateVar[Bytes]("SOME_BYTES")` | `SOME_BYTES=0x1A2B`      |
| [String](#algopy.String) | `algopy.TemplateVar[String]("SOME_STR")`  | `SOME_STR="hello"`       |

All template values specified via the command line are prefixed with "TMPL\_" by default.
The default prefix can be modified using the `--template-vars-prefix` option.

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
