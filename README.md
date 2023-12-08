# Puya - Algorand TEAL compiler + Python language bindings

```shell
poetry install
poetry shell
python -m src.wyvern
# OR compile all examples
python -m scripts.compile_all_examples
# OR run tests
pytest
```

## Existing README stuff - needs clean up

TODO:
How to handle identity for compound objects i.e. dataclasses so that semantic compatability is retained
    Ideas:
        Enforce value equality (dataclasses implement data equality by default)
        Could carry a unique identifier for the object to represent it's identity

how to handle user libs with type stubs:
    option: don't. only want to handle algopy specific code anyway, which needs
            to be fully typed.


THOUGHTS:
- mypy call expr resolves to full node (ie FuncDef) when not through member ref
- user classes (ie not contracts) can't be allowed to override (maybe not even define??) methods, unless we want to implement vtables..................


we probably want to vendor mypy, for a few reasons:
1) we want to pin to an exact version, without possibly getting in the way of user updating their venv version and/or CI/CD config changes
2) we need to stop mypy from being compiled with mypyc, which I don't think we can do with a wheel package? and
3) even if we can/could stop it being compiled, it slows things down a lot for the user, so that's not a great experience
4) can simplify our debugging/development experience (not really a reason by itself, but a nice bonus)

mypy is MIT licensed, except for some files in mypy/mypyc
git submodules could be one approach here, but we can't point it to a subdirectory (ie mypy/mypy)
we can possibly exclude these after the fact in our build to prevent our package becoming too larg
and/or licensing violations, but the import paths might get a bit verbose (ie wyvern.vendor(?).mypy.mypy).
maybe a manual approach is best, possibly with a script to do the update.
we definitely don't want any alterations to the mypy code base, except perhaps in the most dire of
circumstances where we need to patch a particular bug (but really, even then, we should contribute this back upstream ASAP)



TODOs:
error handling at expression level, needs stub data. current handling could generate spurious extra errors


### Parking lot
- match statements
- efficient compound types including pass-by-ref using bytes[] as scratch pointers with loadss/storess
- type tags at end of bytes[] pointers, allowing union types as args and isinstance checks 
- inlineable functions either via explicit hints or via optimisation
- improved constant folding when encountering a non-literal (e.g UInt64) that wraps a known-constant value
- support properties - probably requires inlining?
- More Pythonic ways of using Txn et al:
  - `for arg in Txna.application_args`
  - `len(Txna.application_args)`
  - `Txna.application_args[0]`
- for functions like `box_get` that return `value, did exist: bool` - translate to `value | None`
- support for user defined Protocols (PEP 544)
- support user reserved scratch slots (and syntax to load / store values)
  -  `gloads` allows an application to query another transaction's scratch space, in order for this to be useful a wyvern built app needs a way to push values to `well known` slots
- on reference to `app_(local|global)_get(_ex)?` et. al. extract keys if literals,
  and if dynamic then warn if storage schema not specified explicitly
- allow overrides of local and global storage keys... somehow. or maybe we allow compacting them
  for more storage space as a compiler flag? this would be less helpful though if you wanted to
  read them off chain directly...
- allow more idiomatic `is not None` for `Local.__getitem__` result rather than returning a tuple
  - similarly, allow global (ie member vars) to be ` | None = None` ??
- default values for subroutine arguments
- optimize large x in (...y) ops to use `match` op
- 
