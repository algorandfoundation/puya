---
title: Unsupported Python Features
description: Python language features not supported in Algorand Python
---

## raise, try/except/finally

Exception raising and exception handling constructs are not supported.

Supporting user exceptions would be costly to implement in terms of op codes.

Furthermore, AVM errors and exceptions are not "catch-able", they immediately terminate the
program.

Therefore, there is very little to no benefit of supporting exceptions and exception handling.

The preferred method of raising an error that terminates is through the use of
[assert statements](/puya/language-guide/errors/).

## with

Context managers are redundant without exception handling support.

## async

The AVM is not just single threaded, but all operations are effectively "blocking", rendering
asynchronous programming effectively useless.

## closures & lambdas

Without the support of function pointers, or other methods of invoking an arbitrary function,
it's not possible to return a function as a closure.

Nested functions/lambdas as a means of repeating common operations within a given function may be
supported in the future.

## global keyword

Module level values are only allowed to be [constants](/puya/language-guide/modules/#module-constants). No
rebinding of module constants is allowed. It's not clear what the meaning here would be, since
there's no real arbitrary means of storing state without associating it with a particular contract.
If you do have need of such a thing, take a look at [gload_bytes](/puya/api/algopy/algopyop/#gload-bytes-a-uint64-int-b-uint64-int-bytes)
or [gload_uint64](/puya/api/algopy/algopyop/#gload-uint64-a-uint64-int-b-uint64-int-uint64) if the contracts are within the same transaction,
otherwise [AppGlobal.get_ex_bytes](/puya/api/algopy/algopyop/#class-appglobal)
and [AppGlobal.get_ex_uint64](/puya/api/algopy/algopyop/#class-appglobal).

## Inheritance (outside of contract classes)

Polymorphism is also impossible to support without function pointers, so data classes (such as
[arc4.Struct](/puya/api/algopy/algopyarc4/#class-struct)) don't currently allow for inheritance. Member functions there
are not supported because we're not sure yet whether it's better to not have inheritance but allow
functions on data classes, or to allow inheritance and disallow member functions.

Contract inheritance is a special case, since each concrete contract is compiled separately, true
polymorphism isn't required as all references can be resolved at compile time.