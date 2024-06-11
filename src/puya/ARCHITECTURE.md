## Layers

In top-down order:

-   src/algopy-stubs/
-   src/puya/
    -   parse.py
    -   awst/
    -   awst_build/
    -   ir/
    -   mir/
    -   teal/
    -   ussemble/
    -   compile.py

Dependencies across layer boundaries should only be to something higher in the list.

The data model flows from higher to lower levels like:

    Python AST -> MyPy AST -> AWST -> IR -> MIR -> TEAL -> AVM bytecode

## FAQ

### There are too many things named "context"!?

Yes
