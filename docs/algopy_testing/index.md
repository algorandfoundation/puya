# Algorand Python Testing

`algorand-python-testing` is a companion package to [Algorand Python](https://github.com/algorandfoundation/puya) that enables efficient unit testing of Algorand Python smart contracts in an offline environment. This package emulates key AVM behaviors without requiring a network connection, offering fast and reliable testing capabilities with a familiar Pythonic interface.

The `algorand-python-testing` package provides:

-   A simple interface for fast and reliable unit testing
-   An offline testing environment that simulates core AVM functionality
-   A familiar Pythonic experience, compatible with testing frameworks like [pytest](https://docs.pytest.org/en/latest/), [unittest](https://docs.python.org/3/library/unittest.html), and [hypothesis](https://hypothesis.readthedocs.io/en/latest/)

> **NOTE**: This package is currently in **preview** and should be used with caution until the first stable release.

## Quick Start

The `algorand-python` package is a main prerequisite for using `algorand-python-testing`. It provides stubs and type annotations for the Algorand Python syntax, offering valuable code completion and type checking capabilities when writing smart contracts. However, it's important to note that you cannot directly execute this Python code in a standard Python interpreter. This is because the code is designed to be compiled by the [`puya`](https://github.com/algorandfoundation/puya) compiler into [TEAL](https://developer.algorand.org/docs/reference/teal/index.html) code, which is then deployed on the Algorand Network.

Traditionally, testing Algorand smart contracts involved deploying them on sandboxed Algorand Networks and interacting with actual application instances. While this approach is extremely valuable and robust, it may not always be the most efficient, requires network connection and can't offer a lot of versatility when it comes to testing Algorand Python code.

This is where `algorand-python-testing` comes into play. It allows developers to leverage the rich ecosystem of Python testing frameworks and perform unit tests on their code without the need for deployment on the Algorand Network. This approach enables faster iteration cycles and more granular testing of smart contract logic.

> **NOTE**: While unit testing capabilities of `algorand-python-testing` are highly beneficial and recommended, it's important to note that this package does not advocate for only writing unit tests for Algorand Python code. It adds a new dimension to the testing capabilities of the smart contracts and is highly recommended to be used in conjunction with other test types, especially the ones that run against **real** Algorand Network.

### Prerequisites

-   Python 3.12 or later
-   [Algorand Python](https://github.com/algorandfoundation/puya)

### Installation

To get started with unit testing your `Algorand Python` smart contracts, install the package:

#### using `pip`

```bash
pip install algopy-python-testing

```

#### using `poetry`

```bash
poetry add algopy-python-testing
```

### Testing your first contract

Let's write an introductory "Hello World" contract and test it using the `algopy-testing-python` framework.

Assume the following starter contract (available as starter on all `algokit init -t python` based templates):

#### Contract Definition

```python
from algopy import ARC4Contract, arc4

class HelloWorld(ARC4Contract):
    @arc4.abimethod()
    def hello(self, name: arc4.String) -> arc4.String:
        return "Hello, " + name
```

#### Test Definition

```python
from algopy_testing import algopy_testing_context
from contracts.hello_world import HelloWorld

def test_hello_world():
    with algopy_testing_context() as ctx:
        # Arrange
        input_size = 10
        random_input = ctx.any_string(input_size)
        contract = HelloWorld()

        # Act
        result = contract.hello(random_input)

        # Assert
        assert result == f"Hello, {random_input}"
```

Let's analyze the `test_hello_world()` function:

1. Function Definition: Tests the `HelloWorld` contract.
2. Testing Context: Uses `algopy_testing_context()` to simulate an Algorand environment.
3. Test Setup:
    - Generates a random 10-character string input of type `algopy.String`.
    - Instantiates the `HelloWorld` contract.
4. Contract Interaction:
   Invokes the contract's `hello()` method with the random input. This occurs within a Python interpreter, not on the actual Algorand network. This provides the ability to inspect the contract's state and debug execution as a regular Python program.
5. Assertion:
   Verifies the expected behavior: `assert result == f"Hello, {random_input}"`.

Key features of `algopy_testing_context`:

-   Simulated AVM environment
-   Random, type-specific test data generation
-   Contract instantiation and interaction in a simulated deployment
-   Behavior assertion without live blockchain deployment

The `any_*` methods (e.g., `any_string()`) are powerful tools for generating diverse test inputs, enabling comprehensive test suites across various potential inputs.

### Next steps

To dig deeper into the capabilities of `algorand-python-testing`, continue with the following sections.

```{toctree}
---
maxdepth: 2
caption: Contents
hidden: true
---

usage
examples
coverage
```
