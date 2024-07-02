# Compilation of Algorand TEAL Programs into AVM Bytecode

- **Status**: Proposed
- **Owner**: Daniel McGregor (MakerX)
- **Deciders**: Rob Moore (MakerX), Adam Chidlow (MakerX), Alessandro Cappellato (Algorand Foundation)
- **Date created**: 2024-05-22
- **Date decided**: 
- **Date updated**: 

## Context

The Puya compiler needs to assemble valid Algorand TEAL (Transaction Execution Approval Language) programs into AVM (Algorand Virtual Machine) bytecode 
so the bytecode can be used within inner transactions that need to create applications.

There are several potential solutions to achieve this compilation, each with its own advantages and trade-offs.

## Requirements

* The solution works cross-platform (i.e. works on Windows, Mac and Linux)
* The solution is fast
* The solution is correct

## Options

### Option 1. Use Algod Compile Endpoint

Utilize the Algorand algod `/v2/teal/compile` endpoint to compile TEAL programs into AVM bytecode.

**Pros**

* Ensures compatibility with the latest Algorand protocol updates.
* Existing solution

**Cons**

* Requires network connectivity to the Algorand API
* Potential latency due to network requests.

### Option 2. Use Goal CLI to Compile

Utilize the Algorand goal command-line interface to compile TEAL programs locally.

**Pros**

* Local compilation without the need for network connectivity.
* Directly supported by Algorand, ensuring compatibility.

**Cons**

* Requires installation of the goal CLI
* No native windows binary of goal is available


### Option 3: Integrate TEAL to AVM Bytecode Assembly into Puya Compiler

Extend the existing Puya compiler to directly convert TEAL programs into AVM bytecode.

**Pros**

* Full Control Over Compilation Process: By integrating the assembly within the Puya compiler, we maintain full control and can tailor the process to fit specific use cases and workflows.
* No External Dependencies: This approach eliminates reliance on external tools or services, ensuring the compilation process is self-contained and not affected by network issues or external updates.
* Additional optimizations: We can introduce additional optimizations, if desired these could be upstreamed to the algod implementation
* Simpler Implementation: Given that Puya already handles well-structured TEAL, extending it to assemble bytecode is relatively straightforward and does not require complex parsing.

**Cons**

* Potential for Bugs and Inconsistencies: There is a risk of introducing bugs or deviations from Algorand's official compiler, which could lead to compatibility issues.
* Ongoing Maintenance: We will need to continuously update our compiler to ensure it remains aligned with any changes or updates to the Algorand protocol.

## Decision


## Preferred option

Option 3: Implement Assembly of TEAL to Bytecode in the Puya Compiler

The preferred solution is to extend the existing Puya compiler to directly convert TEAL programs into AVM bytecode. 
This approach offers several key advantages, including full control over the compilation process and independence from external tools or services. 

To provide consistency with algod, we will introduce a flag that enables the generation of bytecode matching the results produced by algod. 
Additionally, to mitigate any potential risks, we will implement comprehensive tests to verify that our output consistently 
aligns with algod compilation results.

## Selected option
