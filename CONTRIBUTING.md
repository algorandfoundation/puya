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

`poe` is used for running various scripts/commands used in local development.

Testing uses `pytest`. You'll need to have a local `algod` node running for most of the tests
to run, see [algokit-cli](https://github.com/algorandfoundation/algokit-cli).

Part of the tests include checking for no output changes to `examples/` or `test_cases/`. If there
are deliberate changes, you should commit those for the tests to pass.

Additionally, if there are any material changes to the output (ie the generated code), you will
need to run `poe compile_all` to ensure the `examples/sizes.txt` file gets updated.

## Updating langspec for new AVM versions

The Puya compiler needs some additional information about AVM ops (such as op code values and application modes) that the langspec in the official go-alogrand repo does not provide.
As such we have a branch of go-algorand with some minimal adjustments to the langspec generation code to add the required info.
The following steps describe the current process to update the langspec used in the Puya compiler

1. Checkout https://github.com/daniel-makerx/go-algorand and then
   1. Switch to `op-spec` branch, the branch will need to be rebased onto master and updated for any relevant changes.
       However initially it is recommended to follow the remaining steps first to ensure the process is working
       Things that may require updating after rebasing:
           * update any new FieldSpec types in `data/transactions/logic/fields.go` by adding a Modes() function. This will typically cause a `make build` to fail if not done.
           * update `cmd/opdoc/opdoc.go:argEnums()` to include any new enums. This will typically cause an error when running the `poe gen` step when not done.
           * update `cmd/opdoc/opdoc.go:main()` with the desired version, typically for Puya we want this to be the next unreleased version. 
   2. Install Go. (Also ensure `$GOPATH$/bin` environment variable is included on your path as some build tools are installed here)
   3. Execute the following scripts as per the Initial Environment Setup in the README.md
       `./scripts/configure_dev.sh`
       `./scripts/buildtools/install_buildtools.sh`
   4. Execute `make build` in the repository root 
   5. Execute `make README.md` in the `data/transactions/logic` directory. This will produce a langspec and markdown file for each version
   6. Copy the latest langspec into the Puya repository e.g. `cp langspec_v12.json ~/repos/algorand/puya/langspec.json`
2. Then within the Puya project
   1. Run `poe gen` to update all generated files derived from the langspec
   2. Update `src/puya/algo_constants.py:SUPPORTED_AVM_VERSIONS` as appropriate
   3. Add relevant test cases for new ops
   4. Bump the algopy-stubs version as appropriate (typically this would just be a minor version bump) 

