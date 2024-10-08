# Compiling to AVM bytecode

The PuyaPy compiler can compile Algorand Python smart contracts directly into AVM bytecode. 
Once compiled, this bytecode can be utilized to construct AVM Application Call transactions both on and off chain.

## Outputting AVM bytecode from CLI

The `--output-bytecode` option can be used to generate `.bin` files for smart contracts and logic signatures, producing an approval and clear program for each smart contract.

```{note}
The Puya compiler incorporates several optimizations that are not present in the bytecode output generated by the 
[`/v2/teal/compile`](https://developer.algorand.org/docs/rest-apis/algod/#post-v2tealcompile) endpoint.
When comparing the outputs of PuyaPy and Algod these differences may be observed. 
To disable these optimizations and produce bytecode identical to Algod use the `--match-algod-bytecode` option.  
```

## Obtaining bytecode within other contracts

The [`compile_contract`](#algopy.compile_contract) function takes an Algorand Python smart contract class and returns a [`CompiledContract`](#algopy.CompiledContract),
The global state, local state and program pages allocation parameters are derived from the contract by default, but can be overridden.
This compiled contract can then be used to create an [`algopy.itxn.ApplicationCall`](#algopy.itxn.ApplicationCall) transaction or used with the [ARC4](#arc4-contracts) functions.  

The [`compile_logicsig`](#algopy.compile_logicsig) takes an Algorand Python logic signature and returns a [`CompiledLogicSig`](#algopy.CompiledLogicSig), which can be used to
verify if a transaction has been signed by a particular logic signature.

## ARC4 contracts

Additional functions are available for [creating](lg-compile.md#create) and [updating](lg-compile.md#update) ARC4 applications on-chain via an inner transaction.

### Create

[`algopy.arc4.arc4_create`](#algopy.arc4.arc4_create) can be used to create ARC4 applications, and will automatically populate required fields for app creation (such as approval program, clear state program, and global/local state allocation).

Like [`algopy.arc4.abi_call`](lg-transactions.md#arc4-application-calls) it handles ARC4 arguments and provides ARC4 return values.

If the compiled programs and state allocation fields need to be customized (for example due to [template variables](#within-other-contracts)), 
this can be done by passing a [`algopy.CompiledContract`](#algopy.CompiledContract) via the `compiled` keyword argument.

```python
from algopy import ARC4Contract, String, arc4, subroutine

class HelloWorld(ARC4Contract):
    
    @arc4.abimethod()
    def greet(self, name: String) -> String:
        return "Hello " + name

@subroutine
def create_new_application() -> None:
    hello_world_app = arc4.arc4_create(HelloWorld).created_app

    greeting, _txn = arc4.abi_call(HelloWorld.greet, "there", app_id=hello_world_app)
    
    assert greeting == "Hello there"
```

### Update

[`algopy.arc4.arc4_update`](#algopy.arc4.arc4_update) is used to update an existing ARC4 application and will automatically populate the required approval and clear state program fields.

Like [`algopy.arc4.abi_call`](lg-transactions.md#arc4-application-calls) it handles ARC4 arguments and provides ARC4 return values.

If the compiled programs need to be customized (for example due to (for example due to [template variables](#within-other-contracts)), 
this can be done by passing a [`algopy.CompiledContract`](#algopy.CompiledContract) via the `compiled` keyword argument.

```python
from algopy import Application, ARC4Contract, String, arc4, subroutine

class NewApp(ARC4Contract):
    
    @arc4.abimethod()
    def greet(self, name: String) -> String:
        return "Hello " + name

@subroutine
def update_existing_application(existing_app: Application) -> None:
    hello_world_app = arc4.arc4_update(NewApp, app_id=existing_app)
    
    greeting, _txn = arc4.abi_call(NewApp.greet, "there", app_id=hello_world_app)
    
    assert greeting == "Hello there"
```

## Template variables
Algorand Python supports defining [`algopy.TemplateVar`](#algopy.TemplateVar) variables that can be substituted during compilation.

For example, the following contract has `UInt64` and `Bytes` template variables.
```{code-block} python
:caption: templated_contract.py
from algopy import ARC4Contract, Bytes, TemplateVar, UInt64, arc4


class TemplatedContract(ARC4Contract):

    @arc4.abimethod
    def my_method(self) -> UInt64:
        return TemplateVar[UInt64]("SOME_UINT")

    @arc4.abimethod
    def my_other_method(self) -> Bytes:
        return TemplateVar[Bytes]("SOME_BYTES")
```

When compiling to bytecode, the values for these template variables must be provided. These values can be provided via the CLI, 
or through the `template_vars` parameter of the [`compile_contract`](#algopy.compile_contract) and [`compile_logicsig`](#algopy.compile_logicsig) functions.

### CLI

The `--template-var` option can be used to [define](compiler.md#defining-template-values) each variable.

For example to provide the values for the above example contract the following command could be used
`puyapy --template-var SOME_UINT=123 --template-var SOME_BYTES=0xABCD templated_contract.py`

### Within other contracts

The functions [`compile_contract`](#algopy.compile_contract) and [`compile_logicsig`](#algopy.compile_logicsig) both have an optional `template_vars` parameter
which can be used to define template variables. Variables defined in this manner take priority over variables defined on the CLI.

```python
from algopy import Bytes, UInt64, arc4, compile_contract, subroutine

from templated_contract import TemplatedContract

@subroutine
def create_templated_contract() -> None:
    compiled = compile_contract(
        TemplatedContract,
        global_uints=2, # customize allocated global uints
        template_vars={ # provide template vars
            "SOME_UINT": UInt64(123),
            "SOME_BYTES": Bytes(b"\xAB\xCD")
        },
    )
    arc4.arc4_create(TemplatedContract, compiled=compiled)
```
