# FAQ

### There are too many things named "context"!
Yes

# Other

## Layers

In top-down order: 

- puya/
  - compile.py
  - codegen/ 
  - ir/
  - awst/
  - metadata.py
  - parse.py
  - errors.py 
- puyapy/

Nothing should ever import from something higher in the list.


## IR Ops

TEAL spec doesn't have "types" for immediate args
(ie literal values that end up in the TEAL source)
This diverges from mypyc Value, which has an rtype always on the Value
class, even if that rtype is void.

We might not even be able to resolve the type of an int literal in the Python source,
until it's used in context with an actual AVM Type, eg:

    UInt64(1) + 2
vs

    UInt512(1) + 2

we don't know the "runtime type" of "2" until we expand the binary operation,
(we probably don't even know the type of "1" unless we handle the compound CallExpr and
IntLiteral together, which has some downsides).

Option 1: parallel hierarchies

    ImmediateValue(ctx: mypy.nodes.Context)
        -> IntLiteral
        -> BytesLiteral
    AVMValue(ctx: mypy.nodes.Context, rtype: RType)
        -> Ops
        -> ...

Option 2: one hierarchy, rtype not defined on Value
    
    Value(ctx: mypy.nodes.Context)
        -> ImmediateValue
            -> IntLiteral
            -> BytesLiteral
        -> AVMValue(rtype: RType)
            -> Ops
            -> ...

Option 3: one hierarchy, rtype defined on Value but is optional

    Value(ctx: mypy.nodes.Context, rtype: RType | None)
        -> IntLiteral
        -> BytesLiteral
        -> Ops
        -> ...


Option 1 is annoying dealing with unions everywhere, too much typing.

Out of Option 2 and Option 3, mishandling is probably more obvious in 2.

Selecting Option 2.


## Puya AST

- no dependency on mypy past this point. We are insulated from either changes in mypy or changing to another parser
- Validate as much as possible during conversion - most source information at this point & early validation means less error compounding causing confusion. 
- This means fully normalised, and only what is required remains. Much easier to reason about this new ast when converting to ir
- No python peculiarities eg a < b < c (which is the same as ((a < b) and (b < c)) _except_ that b is only evaluated once)
  - e.g. a < func_with_side_effects() < c would be equivalent to (tmp = func_with_side_effects(); a < tmp and tmp < c)
  - e.g., a and b and c *_returns_* the first one of (a, b, c) that is falsy or if all are truthy returns c, whilst only evaluating each of a, b, and c at most once (ie still short circuiting) 
- Still high level though eg if else, not branch + go to 
- All stubs fully resolved, ie no further dependence on “puyapy” component. This further insulates from python specifics. Maybe this ast can be target for other languages? Note: this includes any necessary ast code generation eg approval program for arc4
- All types fully resolved & checked


