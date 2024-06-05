# Algorand Python

Algorand Python is a partial implementation of the Python programming language that runs on the AVM. It includes a statically typed framework for development of Algorand smart contracts and logic signatures, with Pythonic interfaces to underlying AVM functionality that works with standard Python tooling.

Algorand Python is compiled for execution on the AVM by PuyaPy, an optimising compiler that ensures the resulting AVM bytecode execution semantics that match the given Python code. PuyaPy produces output that is directly compatible with [AlgoKit typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to make deployment and calling easy.

[Documentation](https://algorandfoundation.github.io/puya/) | [Language guide](https://algorandfoundation.github.io/puya/language-guide.html)

## Installation

### Recommended method

The easiest way to use Algorand Python is to instantiate a template with AlgoKit via:

```algokit init -t python```

This will give you a full development environment with intellisense, linting, automatic formatting, breakpoint debugging, deployment and CI/CD.

A sample smart contract will be placed under `PROJECT_NAME/projects/PROJECT_NAME/smart_contracts/SMART_CONTRACT_NAME/contract.py` (replacing `PROJECT_NAME` and `SMART_CONTRACT_NAME` with the values you chose during the template wizard.)

### Manual Alternative

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

## Usage

1. Navigate to your contract and compile it:
    ```shell
    algokit compile py contract.py
    ```
2. You should now have `HelloWorldContract.approval.teal` and `HelloWorldContract.clear.teal` on the file system!
3. We generally recommend using ARC-32 and [generated typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to have the most optimal deployment and consumption experience; to do this you need to ask PuyaPy to output an ARC-32 compatible app spec file:
    ```shell
    algokit compile py contract.py --output-arc32 --no-output-teal
    ```
4. You should now have `HelloWorldContract.arc32.json`, which can be generated into a client e.g. using AlgoKit CLI:
    ```shell
    algokit generate client HelloWorldContract.arc32.json --output client.py
    ```
5. From here you can dive into the [examples](https://github.com/algorandfoundation/puya/tree/main/examples) or look at the [documentation](https://algorandfoundation.github.io/puya/).

## Examples

There are [many](https://github.com/algorandfoundation/puya/tree/main/examples) [examples](https://github.com/algorandfoundation/puya/tree/main/test_cases) in this repo, here are some of the more useful ones that showcase what
is possible.

-   [hello world](https://github.com/algorandfoundation/puya/tree/main/examples/hello_world/contract.py)
-   [hello world (ARC4)](https://github.com/algorandfoundation/puya/tree/main/examples/hello_world_arc4/contract.py)
-   [voting](https://github.com/algorandfoundation/puya/tree/main/examples/voting/voting.py)
-   [AMM](https://github.com/algorandfoundation/puya/tree/main/examples/amm/contract.py)
-   [auction](https://github.com/algorandfoundation/puya/tree/main/examples/auction/contract.py)
-   [non-ABI calculator](https://github.com/algorandfoundation/puya/tree/main/examples/calculator/contract.py)
-   [local storage](https://github.com/algorandfoundation/puya/tree/main/examples/local_state/local_state_contract.py)

The compiled output is available under the `out/` directory alongside these, e.g. the approval
TEAL for `voting` is available at [examples/voting/out/VotingRoundApp.approval.teal](https://github.com/algorandfoundation/puya/blob/main/examples/voting/out/VotingRoundApp.approval.teal).
