# Building a front end for Puya

This guide is for those looking to add support for a new front end language to Puya. It makes several assumptions about the reader.

 - They are very familiar with building smart contracts and logic signatures on the Algorand Block Chain and are aware of the AVM and Teal op codes
 - They are familiar with Puya's existing front end languages of Algorand Python and Algorand TypeScript
 - They understand lexing and parsing, and how that applies to the language they would like to target

Whilst making use of Puya's back end abstracts away the worst of the complexities in lowering a high level front end language to the stack based teal, adding a new front end is still a significant undertaking. 

## Table of contents

1. [Introduction](./00-introduction.md)
2. [Calling puya](./01-calling-puya.md)
3. [Designing a langauge](./02-designing-a-language.md)
4. [Parsing](./03-parsing.md)
5. [AWST build](./04-awst-build.md)
