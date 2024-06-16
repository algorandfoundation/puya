# Algorand Python Testing

`algorand-python-testing` is a supplementary package to [`algorand-python`](https://github.com/algorandfoundation/puya) that allows unit testing of smart contract code directly. It offers offline, fast, and reliable unit testing capabilities, providing a familiar _pythonic_ testing experience.

### Purpose and Benefits

-   **Fast and Reliable**: Test your `Algorand Python` smart contracts offline, ensuring quick and dependable results without the need for blockchain deployment.
-   **Granular Testing**: Testing individual contract methods, mock and patch contract state, pinpoint and verify contract behavior.
-   **Property Testing**: Verify the contract's correctness under a variety of randomized inputs and constraints.
-   **Comprehensive**: Supports a wide range of testing scenarios and use cases.

[Documentation](TODO) | [Algorand Python Documentation](https://algorandfoundation.github.io/puya/) | [Algorand Python Language guide](https://algorandfoundation.github.io/puya/language-guide.html)

## 1. Quick start

### Installation

To get started with unit testing your `Algorand Python` smart contracts, install the package with pip:

```bash
pip install algopy-testing-python
```

### Testing your first contract

Let's write a simple "Hello World" contract and test it using the `algopy-testing-python` framework.

Assume the following starter contract available on all `AlgoKit Python` templates out of the box (create via `algokit init -t python`):

```python
from algopy import ARC4Contract, arc4

class HelloWorld(ARC4Contract):
    @arc4.abimethod()
    def hello(self, name: arc4.String) -> arc4.String:
        return "Hello, " + name
```

Now, let's create a test file `test_hello_world.py`:

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

The `algopy_testing_context` context manager simulates blockchain interactions, manages state, and executes transactions. Contracts subclassed from `ARC4Contract` or `Contract` are automatically prepared for testing. The `any_*` methods generate random values of specified `algopy` types with size constraints.

The package can be used with various Python testing frameworks like [`pytest`](https://docs.pytest.org/en/latest/), [`unittest`](https://docs.python.org/3/library/unittest.html), and integrates with [`hypothesis`](https://hypothesis.readthedocs.io/en/latest/) for property-based testing using custom strategies.

## 2. Core concepts

### Test Context

The `AlgopyTestContext` class is the main abstraction of the testing framework. It provides a controlled environment to simulate blockchain interactions, manage state, and execute transactions.

-   **Initialization**: Create a test context using the `algopy_testing_context` context manager.
-   **Global Fields**: Patch global fields using `patch_global_fields`.
-   **Transaction Fields**: Patch transaction fields using `patch_txn_fields`.
-   **Accounts, Assets, Applications**: Manage accounts, assets, and applications within the context.

### Accounts, Assets, Applications

The framework provides classes to represent accounts, assets, and applications, allowing you to create and manipulate them within the test context.

-   **Account**: Represents an Algorand account. Use methods like `is_opted_in` to check if an account has opted into an asset or application.
-   **Asset**: Represents an Algorand asset. Use methods like `balance` to get the asset balance of an account.
-   **Application**: Represents an Algorand application. Access application fields and state using the provided methods.

### Transactions

The framework supports various types of transactions, including payment, asset transfer, and application call transactions.

-   **Transaction Types**: Use classes like `PaymentTransaction`, `AssetTransferTransaction`, and `ApplicationCallTransaction` to create and manipulate transactions.
-   **Group Transactions**: Manage transaction groups using methods like `set_transaction_group` and `add_transactions`.

### State

The framework provides mechanisms to manage global and local state within the test context.

-   **Global State**: Use the `GlobalState` class to manage global state variables.
-   **Local State**: Use the `LocalState` class to manage local state variables for accounts.
-   **Scratch Slots**: TO BE DONE
-   **Boxes**: TO BE DONE

### AVM Ops

Algorand Python provide a matching implementation in python to all pure functions defined in the AVM. For a full list of supported AVM operations, please refer to [TODO]().

## 3. Writing tests

### Test structure

TBD

### Assertions and validations

TBD

## 4. Advanced Usage

### Mocking and Patching

TBD

## Contributing

We welcome contributions to this project! Read the [contributing guide](CONTRIBUTING.md) to get started.
