# Principles & Background
## Background

**Smart contracts** on the Algorand blockchain run on the Algorand Virtual Machine ([AVM](https://developer.algorand.org/docs/get-details/dapps/avm/)).
This is a stack based virtual machine, which executes AVM bytecode as part of an [Application Call transaction](https://developer.algorand.org/docs/get-details/transactions/#application-call-transaction).
The official mechanism for generating this bytecode is by submitting TEAL (Transaction Execution Approval Language) to 
an Algorand Node to compile.

**Smart signatures** have the same basis in the AVM and TEAL, but have a different execution model, one not involving 
Application Call transactions. Our focus will primarily be on smart contracts, since they are strictly more powerful
in terms of available AVM functions.

TEAL is a [non-structured](https://en.wikipedia.org/wiki/Non-structured_programming) 
[imperative language](https://en.wikipedia.org/wiki/Procedural_programming#Imperative_programming) 
(albeit one with support for procedure calls that can isolate stack changes since v8 with `proto`). Writing TEAL is very
similar to writing assembly code. It goes without saying that this is a particularly common or well-practiced model for 
programming these days.

As it stands today, developers wanting to write smart contracts specifically for Algorand have the option of writing 
TEAL directly, or using some other mechanism of generating TEAL such as the officially supported [PyTEAL](https://pyteal.readthedocs.io/en/stable/) 
or the community supported [tealish](https://tealish.tinyman.org/en/latest/).

PyTEAL follows a [generative programming](https://en.wikipedia.org/wiki/Automatic_programming#Generative_programming) paradigm,
which is a form of metaprogramming. Naturally, writing programs to generate programs presents an additional hurdle for 
developers looking to pick up smart contract development. Tooling support for this is also suboptimal, for example, many
classes of errors resulting from the interaction between the procedural elements of the Python language and the PyTEAL
expression-building framework go unnoticed until the point of TEAL generation, or worse go completely unnoticed, and even
when PyTEAL can/does provide an error it can be difficult to understand.

Tealish provides a higher level procedural language, bearing a passing resemblance to Python, than compiles down to TEAL.
However, it's still lower level than most developers are used to. 
For example, the expression `1 + 2 + 3`is [not valid in tealish](https://tealish.tinyman.org/en/latest/language.html#math-logic).
Another difference vs a higher level language such as Python is that [functions can only be declared after the program
entry point logic](https://tealish.tinyman.org/en/latest/language.html#functions). 
In essence, tealish abstracts away many difficulties with writing plain TEAL, 
but it is still essentially more of a transpiler than a compiler. 
Furthermore, whilst appearing to have syntax inspired by Python, it both adds and removes many fundamental syntax elements,
presenting an additional learning curve to developers looking to learn blockchain development on Algorand.
Being a bespoke language also means it has a much smaller ecosystem of tooling built around it compared to languages like
Python or JavaScript.

To most developers, the Python programming language needs no introduction. First released in 1991, it's popularity has 
grown steadily over the decades, and as of June 2023 it is consistently ranked as either the most popular langauge, 
or second most popular following JavaScript:

- [GitHub 2022](https://octoverse.github.com/2022/top-programming-languages)
- [StackOverflow 2023](https://stackoverflow.blog/2023/06/13/developer-survey-results-are-in/)
- [Tiobe](https://www.tiobe.com/tiobe-index/)
- [PYPL](https://pypl.github.io/PYPL.html)

The AlgoKit project is an Algorand Foundation initiative to improve the developer experience on Algorand. Within this
broad remit, two of the key [principles](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/algokit.md#guiding-principles) 
are to "meet developers where they are" and "leverage existing ecosystem".
Building a compiler that allows developers to write smart contracts using an idiomatic subset of a high level language 
such as Python would make great strides towards both of these goals.

Wyvern was the original internal code name for just such a compiler (now called Puya), one that will transform Python code into valid TEAL 
smart contracts. In line with the principle of meeting developers where they are, and recognising the popularity of 
JavaScript and TypeScript, a parallel initiative to build a TypeScript to TEAL compiler is [also underway](https://tealscript.netlify.app).

## Principles

The principles listed here should form the basis of our decision-making, both in the design and implementation.

### Least surprise

Our primary objective is to assist developers in creating accurate smart contracts right from the 
start. The often immutable nature of these contracts - although not always the case - and the 
substantial financial value they frequently safeguard, underlines the importance of this goal.

This principle ensures that the code behaves as anticipated by the developer. Specifically, if 
you're a Python developer writing Python smart contract code, you can expect the code to behave 
identically to its execution in a standard Python environment.

Furthermore, we believe in promoting explicitness and correctness in contract code and its 
associated typing. This approach reduces potential errors and enhances the overall integrity of our
smart contracts. Our commitment is to provide a user-friendly platform that aligns with the 
developer's intuition and experience, ultimately simplifying their work and minimizing the
potential for mistakes.

### Inherited from AlgoKit

As a part of the AlgoKit project, the principles outlined [there](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/algokit.md#guiding-principles) 
also apply - to the extent that this project is just one component of AlgoKit. 

#### "Leverage existing ecosystem"

> AlgoKit functionality gets into the hands of Algorand developers quickly by building on top of the 
> existing ecosystem wherever possible and aligned to these principles.

In order to leverage as much existing Python tooling as possible, we should strive to maintain the highest level of 
compatibility with the Python language (and the reference implementation: CPython). 

#### "Meet developers where they are"

> Make Blockchain development mainstream by giving all developers an idiomatic development experience in the operating 
> system, IDE and language they are comfortable with so they can dive in quickly and have less they need to learn before 
> being productive.

Python is a very idiomatic language. We should embrace accepted patterns and practices as much as possible,
such as those listed in [PEP-20](https://peps.python.org/pep-0020/) (aka "The Zen of Python").

#### "Extensible"

> Be extensible for community contribution rather than stifling innovation, bottle-necking all changes through the 
> Algorand Foundation and preventing the opportunity for other ecosystems being represented (e.g. Go, Rust, etc.). 
> This helps make developers feel welcome and is part of the developer experience, plus it makes it easier to add 
> features sustainably

One way to support this principle in the broader AlgoKit context is by building in a mechanism for reusing 
common code between smart contracts, to allow the community to build their own Python packages.

#### "Sustainable"

> AlgoKit should be built in a flexible fashion with long-term maintenance in mind. Updates to latest patches in 
> dependencies, Algorand protocol development updates, and community contributions and feedback will all feed in to the 
> evolution of the software.

Taking this principle further, ensuring the compiler is well-designed (e.g. frontend backend separation, 
with a well-thought-out IR) will help with maintaining and improving the implementation over time. For example,
adding in new TEAL language features will be easier, same for implementing new optimisation strategies.

Looking to the future, best practices for smart contract development are rapidly evolving. We shouldn't tie the 
implementation too tightly to a current standard such as ARC-4 - although in that specific example, we would still
aim for first class support, but it shouldn't be assumed as the only way to write smart contracts.


#### "Modular components"

> Solution components should be modular and loosely coupled to facilitate efficient parallel development by small, 
> effective teams, reduced architectural complexity and allowing developers to pick and choose the specific tools and 
> capabilities they want to use based on their needs and what they are comfortable with.

We will focus on the language and compiler design itself.

An example of a very useful feature, that is strongly related but could be implemented separately instead, 
is the ability to run the users code in a unit-testing context, without compilation+deployment first. 
This would require implementing in Python some level of simulation of Algorand Nodes / AVM behaviour. 

#### "Secure by default"

> Include defaults, patterns and tooling that help developers write secure code and reduce the likelihood of security 
> incidents in the Algorand ecosystem. This solution should help Algorand be the most secure Blockchain ecosystem.

Enforcing security (which is multi-faceted) at a compiler level is difficult, and is some cases impossible. 
The best application of this principle here is to support auditing, which is important and nuanced enough to be 
listed below as a separate principle.

#### "Cohesive developer tool suite" + "Seamless onramp"

> Cohesive developer tool suite: Using AlgoKit should feel professional and cohesive, like it was designed to work 
> together, for the developer; not against them. Developers are guided towards delivering end-to-end, high quality 
> outcomes on MainNet so they and Algorand are more likely to be successful.
 
> Seamless onramp: New developers have a seamless experience to get started and they are guided into a pit of success 
> with best practices, supported by great training collateral; you should be able to go from nothing to debugging code 
> in 5 minutes.

These principles relate more to AlgoKit as a whole, so we can respect them by considering the impacts of our decisions
there more broadly.

### Abstraction without obfuscation

Algorand Python is a high level language, with support for things such as branching logic, operator precedence, etc., 
and not a set of "macros" for generating TEAL. As such, developers will not be able to directly influence specific TEAL 
output, if this is desirable a language such as [Tealish](https://tealish.tinyman.org) is more appropriate.

Whilst this will abstract away certain aspects of the underlying TEAL language, there are certain AVM concerns 
(such as op code budgets) that should not be abstracted away. That said, we should strive to generate code this is
cost-effective and unsurprising. Python mechanisms such as dynamic (runtime) dispatch, and also many of its builtin
functions on types such as `str` that are taken for granted, would require large amounts of ops compared to the
Python code it represents.

### Support auditing

Auditing is a critical part of the security process for deploying smart contracts. We want to support this function,
and can do so in two ways:

1. By ensuring the same Python code as input generates identical output each time the compiler 
is run regardless of the system it's running on. This is what might be termed [Output stability](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/articles/output_stability.md).
Ensuring a consistent output regardless of the system it's run on (assuming the same compiler version), means that
auditing the lower level (ie TEAL) code is possible. 

2. Although auditing the TEAL code should be possible, being able to easily identify and relate it back to the higher level
code can make auditing the contract logic simpler and easier. 

### Revolution, not evolution

This is a new and groundbreaking way of developing for Algorand, and not a continuation of the PyTEAL/Beaker approach. 
By allowing developers to write procedural code, as opposed to constructing an expression tree, 
we can (among other things) significantly reduce the barrier to entry for developing smart contracts for the Algorand platform.

Since the programming paradigm will be fundamentally different, providing a smooth migration experience from PyTEAL 
to this new world is not an intended goal, and shouldn't be a factor in our decisions. For example, it is not a goal of
this project to produce a step-by-step "migrating from PyTEAL" document, as it is not a requirement for users to
switch to this new paradigm in the short to medium term - support for PyTEAL should continue in parallel.
