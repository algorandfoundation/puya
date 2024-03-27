# Algorand Python
 
Algorand Python is a partial implementation of the Python programming language that runs on the AVM. It includes a statically typed framework for development of Algorand smart contracts and logic signatures, with Pythonic interfaces to underlying AVM functionality that works with standard Python tooling.

Algorand Python is compiled for execution on the AVM by PuyaPy, an optimising compiler that ensures the resulting AVM bytecode execution semantics that match the given Python code. PuyaPy produces output that is directly compatible with [AlgoKit typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to make deployment and calling easy.

[Documentation](https://algorandfoundation.github.io/puya/) | [Language guide](https://algorandfoundation.github.io/puya/language_guide.html)

## Quick start

The easiest way to use Algorand Python is to instantiate a template with AlgoKit via `algokit init -t python`. This will give you a full development environment with intellisense, linting, automatic formatting, breakpoint debugging, deployment and CI/CD.

Alternatively, if you want to start from scratch you can do the following:

1. Ensure you have Python 3.12+
2. Install the PuyaPy compiler into your project `poetry add puya --group=dev` and/or install [AlgoKit CLI](https://github.com/algorandfoundation/algokit-cli?tab=readme-ov-file#install)
3. Check you can run the compiler:
    ```shell
    puyapy -h
    # OR
    algokit compile py -h
    ```
4. Create a contract in a (e.g.) `contact.py` file:
    ```python
    from algopy import ARC4Contract, arc4
    class HelloWorldContract(ARC4Contract):
        @arc4.abimethod
        def hello(self, name: arc4.String) -> arc4.String:
            return "Hello, " + name
    ```
5. Compile the contract:
    ```shell
    # After running `poetry shell`:
    puyapy contract.py
    # OR if using AlgoKit CLI:
    algokit compile py contract.py
    ```
6. You should now have `HelloWorldContract.approval.teal` and `HelloWorldContract.clear.teal` on the file system!
7. We generally recommend using ARC-32 and [generated typed clients](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/features/generate.md#1-typed-clients) to have the most optimal deployment and consumption experience; to do this you need to ask PuyaPy to output an ARC-32 compatible app spec file:
    ```shell
    puyapy contract.py --output-arc32 --no-output-teal
    # OR
    algokit compile py contract.py --output-arc32 --no-output-teal
    ```
8. You should now have `HelloWorldContract.arc32.json`, which can be generated into a client e.g. using AlgoKit CLI:
    ```shell
    algokit generate client HelloWorldContract.arc32.json --output client.py
    ```
9. From here you can dive into the [examples](https://github.com/algorandfoundation/puya/tree/main/examples) or look at the [documentation](https://algorandfoundation.github.io/puya/).

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
