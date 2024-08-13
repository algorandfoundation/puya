## Architecture

- no dependency on mypy past this point. We are insulated from either changes in mypy or changing to another parser
- Validate as much as possible during conversion - most source information at this point & early validation means less error compounding causing confusion. 
- This means fully normalised, and only what is required remains. Much easier to reason about this new ast when converting to ir
- No python peculiarities eg a < b < c (which is the same as ((a < b) and (b < c)) _except_ that b is only evaluated once)
  - e.g. a < func_with_side_effects() < c would be equivalent to (tmp = func_with_side_effects(); a < tmp and tmp < c)
  - e.g., a and b and c *_returns_* the first one of (a, b, c) that is falsy or if all are truthy returns c, whilst only evaluating each of a, b, and c at most once (ie still short circuiting) 
- Still high level though eg if else, not branch + go to 
- All stubs fully resolved, ie no further dependence on “puyapy” component. This further insulates from python specifics. Maybe this ast can be target for other languages? Note: this includes any necessary ast code generation eg approval program for arc4
- All types fully resolved & checked


