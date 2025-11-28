# PuyaPy migration from 5.x to 6.0

TODO: flesh this out before merging!

Breaking changes due to "fast parsing" work:
1. import cycles that would've failed in Python no longer supported, use deferred imports or TYPE_CHECKING instead
2. only import statements supported inside TYPE_CHECKING blocks, if aliases were being constructed there as well, move them outside and use quotes (may required explicit typing.TypeAlias annotation).
3. no code can appear under the condition of `not TYPE_CHECKING`
4. a `typing.Protocol` could be declared (other than as an `ARC4Client`) but it was ignored and never usable, now it will error.
