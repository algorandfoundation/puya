# Language Server

This document outline the architecture of the Puya Language Server capability.

```mermaid
sequenceDiagram
  actor D as Developer
  participant IDE as IDE
  participant LC as Language Client
  participant LS as Language Server
  participant PF as Puya Frontend
  participant PB as Puya Backend
  D ->> IDE: keystroke
  D ->> IDE: vcsoperations
  IDE ->> LC: documentOpened (triggers init when not started)
  IDE ->> LC: configurationChanged (triggers reinit)
  IDE ->> LC: restartLanguageServer (triggers reinit)
  LC ->>+ LS: initialise()
  LS -->>- LC: initialised
  IDE ->> LC: documentChanged
  LC ->>+ LS: documentChanged
  LS ->>+ PF: compile(project)
  PF -->> LS: diagnostics
  PF -->>- LS: awst
  LS ->>+ PB: compile(awst)
  PB -->>- LS: diagnostics
  LS -->>- LC: diagnostics
```

## Algorand Python Language Server

The Python implementation of the Puya language server directly interacts with the Puya compiler components in the same Python process.

```mermaid
flowchart TB
    subgraph "VSCode IDE"
        Developer["Developer"]
        VSCodeExt["VSCode Extension"]
    end
    
    subgraph "Python Process"
        PuyaPyLSP["PuyaPy Language Server (puyapy.lsp)"]
        
        subgraph "PuyaPy Frontend"
            PyParser["Python Parser"]
            AWSBuilder["AWST Builder (transform_ast)"]
        end
        
        subgraph "Puya Core Compiler"
            AWSTProcF["AWST Processor"]
            TealCompiler["TEAL Compiler (awst_to_teal)"]
            LogContext["Logging Context"]
        end
    end
    
    Developer -->|keystroke| VSCodeExt
    VSCodeExt -->|stdio/tcp| PuyaPyLSP
    
    PuyaPyLSP -->|document changes| PyParser
    PyParser -->|Python AST| AWSBuilder
    AWSBuilder -->|AWST nodes| AWSTProcF
    AWSTProcF -->|processed AWST| TealCompiler
    
    LogContext -.->|diagnostics| PuyaPyLSP
    AWSTProcF -->|validation results| LogContext
    TealCompiler -->|compilation results| LogContext
    
    PuyaPyLSP -->|diagnostics| VSCodeExt
    VSCodeExt -->|diagnostics| Developer
    
    class Developer,VSCodeExt vscode
    class PuyaPyLSP pyProcess
    class PyParser,AWSBuilder frontend
    class AWSTProcF,TealCompiler,LogContext coreComp
```

## Algorand TypeScript Language Server

The TypeScript implementation runs the Puya service as a separate process and communicates with it via JSON-RPC over stdin/stdout.

```mermaid
flowchart TB
    subgraph "VSCode IDE"
        Developer["Developer"]
        VSCodeExt["VSCode Extension"]
    end
    
    subgraph "NodeJS Process"
        PuyaTsLSP["PuyaTS Language Server"]
        PuyaServiceClient["Puya Service Client"]
        
        subgraph "PuyaTs Frontend"
            TsParser["TypeScript Parser"]
            TsAWSTBuilder["AWST Builder (buildAwst)"]
        end
    end
    
    subgraph "Python Process (subprocess)"
        PuyaService["Puya Service (puya serve)"]
        
        subgraph "Puya Core Compiler"
            AWST["AWST Processor"]
            TealCompiler["TEAL Compiler (awst_to_teal)"]
            LogContext["Logging Context"]
        end
    end
    
    Developer -->|keystroke| VSCodeExt
    VSCodeExt -->|stdio/tcp| PuyaTsLSP
    
    PuyaTsLSP -->|document changes| TsParser
    TsParser -->|TypeScript AST| TsAWSTBuilder
    TsAWSTBuilder -->|AWST nodes| PuyaServiceClient
    PuyaServiceClient -->|downloads puya binary, starts & manages| PuyaService
    
    PuyaServiceClient -->|JSON-RPC: serialized AWST| PuyaService
    PuyaService -->|deserialized AWST| AWST
    AWST -->|processed AWST| TealCompiler
    TealCompiler -->|compilation results| LogContext
    AWST -->|validation results| LogContext
    
    LogContext -.->|diagnostics| PuyaService
    PuyaService -->|JSON-RPC: diagnostics| PuyaServiceClient
    PuyaServiceClient -->|diagnostics| PuyaTsLSP
    PuyaTsLSP -->|diagnostics| VSCodeExt
    VSCodeExt -->|diagnostics| Developer
    
    class Developer,VSCodeExt vscode
    class PuyaTsLSP,PuyaServiceClient nodeProc
    class TsParser,TsAWSTBuilder frontend
    class PuyaService pyProc
    class AWST,TealCompiler,LogContext coreComp
```
