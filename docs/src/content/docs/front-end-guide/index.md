---
title: Front-End Guide
description: Guide for implementing a Puya front-end compiler
sidebar:
  order: 0
---

This guide is for those looking to add support for a new front end language to Puya. It makes several assumptions about the reader.

 - They are very familiar with building smart contracts and logic signatures on the Algorand Block Chain and are aware of the AVM and Teal op codes
 - They are familiar with Puya's existing front end languages of Algorand Python and Algorand TypeScript
 - They understand lexing and parsing, and how that applies to the language they would like to target

Whilst leveraging the Puya back end takes care of a lot of the complexities in lowering a high level front end language to the stack based teal language, adding a new front end is still a significant undertaking.

## Table of contents

- [Introduction](introduction/)
- [Calling Puya](calling-puya/)
- [Designing a Language](designing-a-language/)
- [Parsing](parsing/)
- [AWST Build](awst-build/)