# PuyaPy migration from 5.x to 6.0

TODO: flesh this out before merging!

Breaking changes due to "fast parsing" work:
1. Python code must have lowercase extension `.py`. Module init must be lowercase `__init__.py`.
1. Explicitly importing / importing from an `__init__.py` is unsupported (weird things happen anyway). 
1. No implicit namespace packages (was previously supported in third party packages):
   1. However, can still omit `__init__.py` in sub-packages of explicit sources
1. No directory / py-file shadowing, even that which would be supported by Python.
1. import cycles that would've failed in Python no longer supported, use deferred imports or TYPE_CHECKING instead
1. restrictions on statements supported inside TYPE_CHECKING blocks:
   1. Only imports, if aliases were being constructed there as well, move them outside and use quotes (may required explicit typing.TypeAlias annotation), other code doesn't make sense?
   1. no star imports - in case of import cycle only? or at all, for consistency?
1. no code can appear under the condition of `not TYPE_CHECKING`
1. a `typing.Protocol` could be declared (other than as an `ARC4Client`) but it was ignored and never usable, now it will error.
