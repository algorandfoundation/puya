# Building a front end for Puya

**Previous**: [Parsing](./03-parsing.md)

## AWST build

The AWST build phase is where we convert the source language AST to AWST.

### Define AWST nodes and WTypes

The first step to building AWST is to create a local representation of the AWST nodes in your front-end's language. This will also need to include a version of Puya's wtypes. WTypes are attached to every AWST expression and their implementation must match Puya's. 

Puyapy is written in python which means it has the luxury of being able to just reference the types in the `puya` module directly. Puya-ts uses a script to build `nodes.py` from and visits the AST to build equivalent TypeScript definitions which are then written to `nodes.ts`. We are exploring options for generating a JSON schema for the nodes which would make it easier for other front ends to generate compatible node types. Puya-ts hand rolls the wtypes file as there are not that many of them, and it makes it easier to write bespoke constructors for each type.

### Visit AST and produce AWST

Once you have your nodes and wtypes, it's time to start visiting your AST and building AWST nodes. Puya does not have any requirement for how this is done. The rest of this section will discuss the approach used by puyapy and puya-ts.

#### Builder Pattern 

In the context of the AWST build process, the builder pattern refers to the practice of wrapping resolved expressions in a _builder_ class which is then used to build out bigger expression trees, all wrapped in a builder until we reach the statement level where we resolve it to AWST nodes. Take the following code expression as an example.

```ts
123.toString()
```

Represented in AST it might look something like this

```json
{
    "type": "CallExpression",
    "expression": {
        "type": "PropertyAccessExpression",
        "property": {
            "type": "StringLiteral",
            "value": "toString"
        },
        "expression": {
            "type": "NumericLiteral",
            "value": 123
        }
    },
    "args": []
}
```

As we visit this sub-tree, the first node we will visit is the call expression. In order to know what we're calling, we would then visit the `.expression` property which in turn needs to check its `.expression` property to see if the property being accessed exists, and what its value should be and so on. If we were to imagine a naive implementation of this code where we directly return AWST it might look something like.

```ts
class Visitor {
    accept(node) {
        // Implementation
    }

    visitCallExpression(expr) {
        const base = this.accept(expr.expression)
        // What do we even check on base to know if it's callable?
        if (base instanceof ??? ) {
            // And if it's callable, how do we know what it returns?
            return ??? 
        }
    }

    visitPropertyAccessExpression(expr) {
        const base = this.accept(expr.expression)
        const property = this.accept(expr.property)
        
        if(base instanceof IntegerConstant) {
            if(property instanceof StringConstant) {
                switch (property.value) {
                    case "toString":
                        // There's no node to even represent this value as it's only 
                        // valid in the context of being called
                        return ????
                }
            }
        }
    }

    visitStringLiteralExpression(expr) {
        return new StringConstant({
            value: expr.value
        })
    }

    visitNumericLiteralExpression(expr) {
        return new IntegerConstant({
            value: expr.value
        })
    }
}
```

As you can see, many of the AST nodes don't even map to an AWST node, and even if they did - it puts all the complexity of handling different types and what is considered valid to do with those types; in the visitor code which is not scalable. 

The solution is to define an abstract builder class or interface with methods for all the _actions_ that could be valid on an expression, then implement a builder for each of these expression types which implements the actions it supports, and errors on actions it doesn't. 

To revisit the above example, a stripped down implementation might look like this

```ts
abstract class BaseBuilder {
    abstract memberAccess(name: string): BaseBuilder

    abstract call(args: BaseBuilder[]): BaseBuilder
}

class IntegerExpressionBuilder extends BaseBuilder {
    constructor(private value: Expression) {
        super();
    }

    memberAccess(name: string): BaseBuilder {
        switch (name) {
            case 'toString':
                return new IntegerToStringBuilder(this.value)
        }
    }

    call(args: BaseBuilder[]): BaseBuilder {
        throw new Error('Integer does not support calling')
    }

}

class IntegerToStringBuilder extends BaseBuilder {
    constructor(base: Expression) {
        super();
    }

    memberAccess(name: string): BaseBuilder {
        throw new Error(`Not supported: Accessing member ${name} on method`)
    }

    call(args: BaseBuilder[]): BaseBuilder {
        if (args.length !== 0) throw new Error(`Invalid arg count ${args.length}`)
        return new StringExpressionBuilder(new ItoA({
            expression: base
        }))
    }
}

class StringExpressionBuilder extends BaseBuilder {
    constructor(value: Expression) {
        super();
    }
    
    memberAccess(name: string): BaseBuilder {
        throw new Error(`Not supported: Accessing member ${name} on method`)
    }
    call(args: BaseBuilder[]): BaseBuilder {
        throw new Error('String does not support calling')
    }
}
```

With this, our visitor now starts to look a lot simpler and the complexity is constrained to the builders where it is tightly coupled with the type the builder is representing.

```ts
class Visitor {
    accept(node) {
        // Implementation
    }

    visitCallExpression(expr) {
        const base = this.accept(expr.expression)
        return base.call(expr.args.map(a => this.accept(a)))
    }

    visitPropertyAccessExpression(expr) {
        const base = this.accept(expr.expression)
        const property = this.accept(expr.property)
        const propertyName = requireStringLiteral(property)
        return base.memberAccess(propertyName)
    }

    visitStringLiteralExpression(expr) {
        return new StringExpressionBuilder(new StringConstant({
            value: expr.value
        }))
    }

    visitNumericLiteralExpression(expr) {
        return new IntegerExpressionBuilder(new IntegerConstant({
            value: expr.value
        }))
    }
}
```

In practice the builders will need more than just call and member access, but hopefully this demonstrates the power of the pattern. You review the Python implementation of this patten in src/puyapy/awst_build/eb or the TypeScript implementation in `src/awst_build/eb` in the puya-ts repository.  

#### PyTypes and PTypes

Whilst the aforementioned WTypes are enough to accurately describe all the expression types that are supported in AWST; you will likely find they are insufficient for describing all the possible types in your front end language. For this reason, puyapy introduces the concept of a `PyType` which is a largely a superset of WTypes. Many of the PyTypes map directly to an equivalent WType - such as strings, uints, bytes, and arrays; but other PyTypes represent concepts that only exist in Algorand Python - such as a Box proxy. A box proxy is clearly a type in the front end, but it has no representation in AWST. What would it mean to return `self.my_box` from an ABI method for example? `self.my_box.value` however, would map to an `AppStateExpression`. PyTypes allow you to describe these front end only types. 

In puya-ts, the equivalent concept is a `PType` - because `TsType` was already taken by the `typescript` namespace and [naming things is hard](https://martinfowler.com/bliki/TwoHardThings.html). 

### Serialize to JSON

The last step once you have built your AWST tree is to produce the two required artifacts discussed [earlier](01-calling-puya.md) and then invoke puya. 

For the most part the AWST should be serialized as a standard JSON - but there are a couple of quirks to be aware of.

 - Property names must be in snake_case to match the python properties
 - Binary data (eg. anything that is of type `bytes`) should be base-85 encoded. There are a number of variants of base-85 encoding; Python uses the character set of rfc1924 but supports arbitrary sized input. You can see an implementation of this in puya-ts under [src/util/base-85.ts](https://github.com/algorandfoundation/puya-ts/blob/main/src/util/base-85.ts)
 - Nodes must include the name of their type under a `_type` property. Eg. `{ "_type": "IntegerConstant", ... }`




