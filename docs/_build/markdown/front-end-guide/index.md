# Building a front end for Puya

This guide is for those looking to add support for a new front end language to Puya. It makes several assumptions about the reader.

- They are very familiar with building smart contracts and logic signatures on the Algorand Block Chain and are aware of the AVM and Teal op codes
- They are familiar with Puya’s existing front end languages of Algorand Python and Algorand TypeScript
- They understand lexing and parsing, and how that applies to the language they would like to target

Whilst leveraging the Puya back end takes care of a lot of the complexities in lowering a high level front end language to the stack based teal language, adding a new front end is still a significant undertaking.

## Table of contents

* [Introduction](00-introduction.md)
* [Calling puya](01-calling-puya.md)
  * [Installing puya](01-calling-puya.md#installing-puya)
  * [Puya Options](01-calling-puya.md#puya-options)
  * [AWST json](01-calling-puya.md#awst-json)
    * [Source annotations](01-calling-puya.md#source-annotations)
    * [Other options](01-calling-puya.md#other-options)
    * [Putting it all together](01-calling-puya.md#putting-it-all-together)
* [Designing a language](02-designing-a-language.md)
  * [Primitive and compound types](02-designing-a-language.md#primitive-and-compound-types)
  * [Contract and logic signature paradigms](02-designing-a-language.md#contract-and-logic-signature-paradigms)
  * [Other key abstractions](02-designing-a-language.md#other-key-abstractions)
* [Parsing](03-parsing.md)
  * [Generating AST](03-parsing.md#generating-ast)
  * [Visiting the AST](03-parsing.md#visiting-the-ast)
* [AWST build](04-awst-build.md)
  * [Define AWST nodes and WTypes](04-awst-build.md#define-awst-nodes-and-wtypes)
  * [Visit AST and produce AWST](04-awst-build.md#visit-ast-and-produce-awst)
    * [Builder Pattern](04-awst-build.md#builder-pattern)
    * [PyTypes and PTypes](04-awst-build.md#pytypes-and-ptypes)
  * [Serialize to JSON](04-awst-build.md#serialize-to-json)
