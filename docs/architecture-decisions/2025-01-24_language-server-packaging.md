# Language Server Packaging

-   **Status**: Decided
-   **Owner**: Patrick Dinh (MakerX)
-   **Deciders**: Patrick Dinh (MakerX), Neil Campbell (MakerX), Daniel McGregor (MakerX), Adam Chidlow (MakerX)
-   **Date created**: 2025-01-24
-   **Date decided**: 2025-01-24
-   **Date updated**:

## Context

Algorand Python and Algorand TypeScript are semantically compatible implementations of their respective high-level languages that compile to Algorand Virtual Machine (AVM) bytecode. Due to the inherent constraints of the AVM, these implementations support only a subset of the full language features. This creates a disconnect where developers can author syntactically valid Python or TypeScript code that fails to compile as valid Algorand Python or Algorand TypeScript, introducing some friction in the smart contract development process.

Surfacing these compilation results earlier in the development process significantly enhances the contract authoring experience. This is where a language server can be used, allowing developers to receive real-time syntax validation and compilation diagnostics directly within their IDE. Issues can be identified and addressed without explicitly running a compilation step, which results in improved productivity and reduced friction in the contract development workflow.

While the Language Server Protocol (LSP) establishes a standard for a language server implementation, it does not define conventions or standards for packaging and distributing a language server.

This ADR defines the options available to package and distrbute the language server component, which provides the compilation diagnostics to a language client that is enabled using an IDE extension.

## Requirements

-   The language server should be easy to install and configure.
-   A language client should be able to easily discover the language server.
-   The language server should use the same compiler version that a developer is using to compile.
-   Changes to either the language server or compiler should be easy to facilitate.
-   The packaging solution should not significantly impact the performance or startup time of the language server.
-   The chosen options should consider and support future languages that may leverage the Puya compiler.

## Principles

-   [AlgoKit Guiding Principles](https://github.com/algorandfoundation/algokit-cli/blob/main/docs/algokit.md#guiding-principles) - specifically Cohesive developer tool suite, Seamless onramp, Meet developers where they are, Leverage existing ecosystem

## Options

### Option 1. Single Independently Packaged Language Server

This approach involves developing a unified language server that handles both Algorand Python and Algorand TypeScript languages through a single package. The server would be capable of providing LSP services for both languages, with a strategy pattern used to invoke the correct compiler and return applicable results.

**Pros**

-   Only a single language server needs to be maintained.
-   Ensures consistent language server behaviour between languages.

**Cons**

-   Vigilance will be required to ensure compatibility between the language server and compiler.
-   There is potential for needing more inter process calls, as at least one language won't be native.
-   The extension will need to manage installing the language server version.
-   Seamlessly supporting multiple compiler version is difficult.
-   Updates to one language will require releasing a new version for both languages, even if only one is affected.
-   New language features will first need to be released before being incorporated into the language server.

### Option 2. Multiple Independently Packaged Language Servers

This approach involves creating separate language servers for Algorand Python and Algorand TypeScript, each packaged and distributed independently. Each server would be optimized for its specific language with dedicated logic and features and likely would be implemented in the native language.

**Pros**

-   Each server can be fine-tuned for its target language without compromise.
-   Updates to one language server can be released without affecting the other.
-   The language server can be implemented in the native language of the compiler front end, which potentially reduces the need for inter process communications.

**Cons**

-   Does not ensure consistent language server behaviour between languages.
-   A language server per language needs to be maintained.
-   Vigilance will be required to ensure compatibility between the language server and compiler.
-   The extension will need to manage installing the language server version.
-   Seamlessly supporting multiple compiler version is difficult.
-   New language features will first need to be released before being incorporated into the language server.

### Option 3. Multiple Embedded Language Servers

In this approach, language servers for both Algorand Python and Algorand TypeScript would be embedded directly within their respective compiler front end packages. Rather than being distributed as standalone packages, the language server functionality would be bundled and released as part of the compiler itself.

**Pros**

-   Each server can be fine-tuned for its target language without compromise.
-   Updates to one language server can be released without affecting the other.
-   The language server can be implemented in the native language of the compiler front end, which potentially reduces the need for inter process communications.
-   A compatible language server is always available for a given compiler version and the language client can easily discover it.
-   New language features can be added to both the compiler and language server in the same release.
-   Multiple compiler versions are easily supported.

**Cons**

-   Does not ensure consistent language server behaviour between languages.
-   A language server per language needs to be maintained.
-   The compiler front end package will be bigger, as it includes a language server.

## Preferred option

Option 3 provides the most pragmatic solution, which automatically enforces compatibility between the language server and compiler. Additionally it makes it easy for a language client to discover the correct language server for a given compiler version the developer is using.

## Selected option

When have chosen to implement option 3.
