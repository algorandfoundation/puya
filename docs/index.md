# Algorand Python

Algorand Python is a partial implementation of the Python programming language that runs on the AVM. It includes a statically typed framework for development of Algorand smart contracts and logic signatures, with Pythonic interfaces to underlying AVM functionality that works with standard Python tooling.

Algorand Python is compiled for execution on the AVM by PuyaPy, an optimising compiler that ensures the resulting AVM bytecode execution semantics that match the given Python code. PuyaPy produces output that is directly compatible with [AlgoKit typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to make deployment and calling easy.

## Quick start

The easiest way to use Algorand Python is to instantiate a template with AlgoKit via `algokit init -t python`. This will give you a full development environment with intellisense, linting, automatic formatting, breakpoint debugging, deployment and CI/CD.

Alternatively, if you want to start from scratch you can do the following:

1. Ensure you have Python 3.12+
2. Install [AlgoKit CLI](https://github.com/algorandfoundation/algokit-cli?tab=readme-ov-file#install)
3. Check you can run the compiler:
    ```shell
    algokit compile py -h
    ```
4. Install Algorand Python into your project `poetry add algorand-python`
5. Create a contract in a (e.g.) `contract.py` file:
    ```python
    from algopy import ARC4Contract, arc4
    class HelloWorldContract(ARC4Contract):
        @arc4.abimethod
        def hello(self, name: arc4.String) -> arc4.String:
            return "Hello, " + name
    ```
6. Compile the contract:
    ```shell
    algokit compile py contract.py
    ```
7. You should now have `HelloWorldContract.approval.teal` and `HelloWorldContract.clear.teal` on the file system!
8. We generally recommend using ARC-32 and [generated typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to have the most optimal deployment and consumption experience; to do this you need to ask PuyaPy to output an ARC-32 compatible app spec file:
    ```shell
    algokit compile py contract.py --output-arc32 --no-output-teal
    ```
9. You should now have `HelloWorldContract.arc32.json`, which can be generated into a client e.g. using AlgoKit CLI:
    ```shell
    algokit generate client HelloWorldContract.arc32.json --output client.py
    ```
10. From here you can dive into the [examples](https://github.com/algorandfoundation/puya/tree/main/examples) or look at the [documentation](https://algorandfoundation.github.io/puya/).

## Programming with Algorand Python

To get started developing with Algorand Python, please take a look at the [Language Guide](./language-guide.md).

## Using the PuyaPy compiler

To see detailed guidance for using the PuyaPy compiler, please take a look at the [Compiler guide](./compiler.md).

```{toctree}
---
maxdepth: 2
caption: Contents
hidden: true
---

language-guide
principles
api
compiler
algopy_testing/index
```
