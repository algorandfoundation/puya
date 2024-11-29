# Contributing to Puya

Contributions of all kinds are welcome. For new features, please open an issue to discuss first.

## Workflow

[Conventional commits](https://www.conventionalcommits.org/en/v1.0.0/#summary) are used.
Not all commits require a convention, but in general a user-facing change should include at least
one commit with either a `fix:` or `feat:` commit, so that is included in the release notes.
Other conventions such as `docs:` or `test:` are not necessarily required but may be helpful to
see when reviewing.

## Local development tips

`poetry` is used for virtual environment and dependency management.

Dependencies for building docs are in a separate `docs` dependency group, this is only required 
if you want to build the documentation locally to see the effects of any edits you made.

`ruff` is used for linting and formatting, `mypy` is used for static analysis. `pre-commit` is
configured, so you will want to either install the hooks with `pre-commit install` or you can run
things manually via `pre-commit run --all-files`.

Testing uses `pytest`. You'll need to have a local `algod` node running for most of the tests
to run, see [algokit-cli](https://github.com/algorandfoundation/algokit-cli).

Part of the tests include checking for no output changes to `examples/` or `test_cases/`. If there
are deliberate changes, you should commit those for the tests to pass.

Additionally, if there are any material changes to the output (ie the generated code), you will
need to run `./scripts/compile_all_examples.py` to ensure the `examples/sizes.txt` file gets 
updated.



