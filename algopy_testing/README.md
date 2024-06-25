# Algorand Python Testing

Algorand Python Testing is a companion package to [Algorand Python](https://github.com/algorandfoundation/puya) that enables efficient unit testing of Algorand Python smart contracts in an offline environment. It emulates key AVM behaviors without requiring a network connection, offering fast and reliable testing capabilities with a familiar Pythonic interface.

[Documentation](https://algorandfoundation.github.io/algopy_testing/index.html) | [Algorand Python Documentation](https://algorandfoundation.github.io/puya/)

## Quick start

The easiest way to use Algorand Python Testing is to instantiate a template with AlgoKit via `algokit init -t python`. This will give you a full development environment with testing capabilities built-in.

Alternatively, if you want to start from scratch:

1. Ensure you have Python 3.12+
2. Install [AlgoKit CLI](https://github.com/algorandfoundation/algokit-cli?tab=readme-ov-file#install)
3. Install Algorand Python Testing into your project:
    ```bash
    pip install algopy-testing-python
    ```
4. Create a test file (e.g., `test_contract.py`):

    ```python
    from algopy_testing import algopy_testing_context
    from your_contract import YourContract

    def test_your_contract():
    with algopy_testing_context() as ctx:
    contract = YourContract() # Your test code here
    ```

5. Run your tests using your preferred Python testing framework (e.g., pytest, unittest)

For more detailed information, check out the [full documentation](https://algorandfoundation.github.io/algopy_testing).

## Features

-   Offline testing environment simulating core AVM functionality
-   Compatible with popular Python testing frameworks
-   Supports testing of ARC4 contracts, smart signatures, and more
-   Provides tools for mocking blockchain state and transactions

## Examples

For detailed examples showcasing various testing scenarios, refer to the [examples section](https://algorandfoundation.github.io/algopy_testing/examples.html) in the documentation.

## Contributing

We welcome contributions to this project! Please read our [contributing guide](CONTRIBUTING.md) to get started.
