# PuyaPy migration from 5.x to 6.0

TODO: flesh this out before merging!

Breaking changes due to "fast parsing" work:

## File naming & structuring
1. Python code must have lowercase extension `.py`. Module init must be lowercase `__init__.py`.
1. No implicit namespace packages (was previously supported in third party packages):
   1. However, can still omit `__init__.py` in sub-packages of explicit sources
1. No directory / py-file shadowing, even that which would be supported by Python.

## Import statements
1. Import cycles that would've failed in Python no longer supported, use deferred imports or TYPE_CHECKING instead
1. Import statements can only appear:
   - At the top level of a module, function, ... or class (maybe deprecate this too? it's weird)
   - Inside an `if TYPE_CHECKING` block which is itself as the module level
1. Explicitly importing / importing from an `__init__.py` is unsupported (weird things happen anyway).

## TYPE_CHECKING
1. The *only* accepted use of `TYPE_CHECKING` is as as the sole condition of an `if` statement, 
at the module level. No code can appear under the condition of `not TYPE_CHECKING`, or the 
else branch, etc.
1. Only imports may appear inside the `if TYPE_CHECKING` block, if aliases were being constructed there as well, move them outside and use quotes (may required explicit typing.TypeAlias annotation), other code doesn't make sense?

## Misc
1. A `typing.Protocol` could be declared (other than as an `ARC4Client`) but it was ignored and never usable, now it will error.
