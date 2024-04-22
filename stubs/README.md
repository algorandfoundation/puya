# Algorand Python framework - API for writing Algorand Python smart contracts

## Installation

The minimum supported Python version for writing Algorand Python smart contracts is 3.12.

You can install the Algorand Python framework from PyPI into your project virtualenv:
```shell
pip install algorand-python
```
If you're using poetry for dependency and virutalenv management, you can add it that way with
`poetry add algorand-python`.

Once you have installed the Algorand Python framework, you can access the type definitions from the `algopy` module, e.g.
```python
from algopy import Contract
```

For more details on using this API and the puyapy compiler see https://algorandfoundation.github.io/puya/

## Versioning

The Algorand Python API follows [semver](https://semver.org/) principles, however since the compiler is very closely
coupled with the stubs definition, it's worth noting the interplay.

### Major
An increase in the major version should only occur if existing contracts would fail to type-check
after the update.

Some examples of situations that might cause this:
- Breaking changes to the signature of an existing function, such as a new parameter being added 
  to an existing
  method and no default value is provided.
- Something has been renamed, or moved such that the import path has changed (excluding moving 
  between private modules, indicated with a leading underscore).
- Something has been removed.

The first two examples would necessitate changes in the compiler itself as well, which should
also be considered breaking changes, thus there would be a coinciding new major version of the 
compiler.

The third example may not necessitate a change to the compiler, although it probably would be 
likely there is one to remove the supporting code, but either way, since it will also change
the behaviour in terms of what version range of the stubs is supported, should also result in a
new major version of the compiler.

However, vice versa is not necessarily true: a new major version of the compiler may not require
a new major version of the stubs. For example:
- Any breaking change to the compiler that has no changes in the stubs.
- The default value of a parameter has changed. This changes the meaning of existing code that
  does not supply a default, thus requiring a major version bump of the compiler, but no 
  existing contracts will fail to compile.

### Minor
When new functionality is added, the minor version should be bumped.

Example situations:
- A new high level API has been added.
- A new parameter has been added to an existing method but a default value has been provided.
- A new TEAL/AVM version has been released with new low-level op-codes that should be exposed.
 
In each of these cases, there should be zero impact on whether existing contracts will compile
or not. They all would also require a new compiler version to be released. Although the existing
compiler version could continue to work with new stubs version, provided none of the new 
functionality is used, for simplicity the compiler should be updated to require the new stubs 
version as a minimum.

### Patch
When a bug in the stubs themselves is fixed, or a non-functional change is made (such as 
changes to docstrings / documentation), the patch version should be bumped.

Examples:
- Docstrings added/removed/updated.
- Type parameters that were incorrectly specified are fixed
  ([concrete example](https://github.com/algorandfoundation/puya/issues/191)).
- Adding something that was unintentionally omitted from the stubs, but is otherwise supported by 
  the current compiler. 
  Generally in these cases, the code would compile if a `# type: ignore[<error-code>]` was added 
  ([concrete example](https://github.com/algorandfoundation/puya/issues/200)).

In each of these cases, the new stubs should functional correctly when paired with the current
release of the compiler.

The second example is a slight break from semver principles, since this is not backwards 
compatible, as existing contracts may fail to compile. However, those contracts should not have
compiled in the first place. The minimum version of stubs supported by the compiler should be
increased to this new patch release, however this will only take effect on the next release of the
compiler itself. The current compiler release would detect the new stubs version as supported 
though, and so users can update to that new version of the stubs once it is released.
