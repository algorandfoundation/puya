# Building a front end for Puya

## Introduction

Puya is a multi-stage compiler designed from the start to support multiple source languages. The first supported language was Algorand Python, the second was Algorand TypeScript. We refer to the code used to support these languages as a 'front end'. The job of a front end is to parse a source language, then respecting the relevant syntactical and semantic rules of that source language, convert it into a common AST which is used as an input into the later stages of the puya compiler. This AST is referred to as AWST (Abstract Wyvern Syntax Tree) after the code name for the compiler (Wyvern). 

> See the [Puya architecture](../../ARCHITECTURE.md) documentation for more on the different stages of the Puya compiler. This document will focus only on the parts relevant to the front end.

AWST strives to represent the AST of a generic c-like language, cutting back on nodes that represent a language's syntactic sugar in favour of supporting the minimum nodes required to support semantic compatability. As an example, there is no node to represent a `for(i = 0; i < x; i++)` style loop available in many languages as this can be adequately represented using a while loop. 

```ts
for (let i = 0; i < 10; i++) {
    // loop body
}

let i = 0
while(i < 10) {
    // loop body
    i++
}
```

The caveat here being special handling of `break` and `continue` statements. 

The available AWST nodes may change over time as the capabilities of the underlying compiler and AVM evolve, or to support new front end language syntax that can't be represented using the current set of nodes; however the goal should always be to minimize the number of nodes we support as this directly impacts the complexity of the compiler and the surface area for potential bugs. 

As an example, Algorand Python makes use of Python's `assert <condition>` statement for asserts resulting in an initial `AssertStatement` node. When support was added for Algorand TypeScript, there is no such statement available and asserts were implemented by a function call expression `assert(<condition>)`. Since this is an expression, this code could appear anywhere expressions are valid - not just at the statement level. As a result, the `AssertStatement` node was converted to an `AssertExpression` and Algorand Python was updated to use `ExpressionStatement(AssertExpression)`. 

**Next up**: [Calling puya](./01-calling-puya.md)
