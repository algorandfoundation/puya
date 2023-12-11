# Puya - Algorand TEAL compiler + AlgoPy Python language bindings

```shell
poetry install
poetry shell
# Run the compiler
puya examples/amm
# OR compile all examples
python -m scripts.compile_all_examples
# OR run tests
pytest
```

[Project background and guiding principles](docs/principles.md). 

Examples:
- [voting](examples/voting/voting.py)
- [AMM](examples/amm/contract.py)
- [auction](examples/TEALScript/auction/contract.py)
- [non-ABI calculator](examples/calculator/contract.py)
- [local storage](examples/local_storage)
