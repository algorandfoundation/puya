# Language Guide

Algorand Python is conceptually two things:

1. A partial implementation of the Python programming language that runs on the AVM.
2. A statically typed framework for development of Algorand smart contracts and logic
   signatures, with Pythonic interfaces to underlying AVM functionality.

As a partial implementation of the Python programming language, it maintains the syntax and
semantics of Python. The subset of the language that is supported will grow over time, but it will
never be a complete implementation due to the restricted nature of the AVM as an execution
environment. As a trivial example, the `async` and `await` keywords, and all associated features,
do not make sense to implement.

TODO(@achidlow): finish the below
As a framework, provide contract, types, etc. Lower level ops. Framework is interfaces (stubs),
but because of semantic compatibility, an implementation of those interfaces could be used/developed
and Algorand Python code runnable with CPython.

Why why? [Project background and guiding principles](principles.md).

If you aren't familiar with Python, a good place to start is https://docs.python.org/3/tutorial/index.html,
just beware that as mentioned above, [not all features are supported](./lg-unsupported-python-features.md).

```{toctree}
---
maxdepth: 3
---

lg-structure
lg-types
lg-control
lg-modules
lg-builtins
lg-errors
lg-storage
lg-code-reuse
lg-logs
lg-transactions
lg-ops
lg-arc4
lg-arc28
lg-unsupported-python-features
```

TODO: sections for boolean or/and expressions, no function pointers -> no OOP example.
