# Building a front end for Puya

This guide is for those looking to add support for a new front end language to Puya. It makes several assumptions about the reader.

 - They are very familiar with building smart contracts and logic signatures on the Algorand Block Chain and are aware of the AVM and Teal op codes
 - They are familiar with Puya's existing front end languages of Algorand Python and Algorand TypeScript
 - They understand lexing and parsing, and how that applies to the language they would like to target

Whilst leveraging the Puya back end takes care of a lot of the complexities in lowering a high level front end language to the stack based teal language, adding a new front end is still a significant undertaking. 

## Table of contents

```{toctree}
---
maxdepth: 3
---

00-introduction
01-calling-puya
02-designing-a-language
03-parsing
04-awst-build
```






