# Calling other applications

The preferred way to call other smart contracts is using [`algopy.arc4.abi_call`](#algopyarc4abi_call), [`algopy.arc4.arc4_create`](#algopyarc4arc4_create) or 
[`algopy.arc4.arc4_update`](#algopyarc4arc4_update). These methods support type checking and encoding of arguments, decoding of results, group transactions,
and in the case of `arc4_create` and `arc4_update` automatic inclusion of approval and clear state programs.

## `algopy.arc4.abi_call`

[`algopy.arc4.abi_call`](#algopy.arc4.abi_call) can be used to call other ARC4 contracts, the first argument should refer to
an ARC4 method either by referencing an Algorand Python [`algopy.arc4.ARC4Contract`](#algopy.arc4.ARC4Contract) method,
an [`algopy.arc4.ARC4Client`](#algopy.arc4.ARC4Client) method generated from an ARC-32 app spec, or a string representing
the ARC4 method signature or name.
The following arguments should then be the arguments required for the call, these arguments will be type checked and converted where appropriate.
Any other related transaction parameters such as `app_id`, `fee` etc. can also be provided as keyword arguments.

If the ARC4 method returns an ARC4 result then the result will be a tuple of the ARC4 result and the inner transaction.
If the ARC4 method does not return a result, or if the result type is not fully qualified then just the inner transaction is returned.

```python
from algopy import Application, ARC4Contract, String, arc4, subroutine

class HelloWorld(ARC4Contract):
    
    @arc4.abimethod()
    def greet(self, name: String) -> String:
        return "Hello " + name

@subroutine
def call_existing_application(app: Application) -> None:
    greeting, greet_txn = arc4.abi_call(HelloWorld.greet, "there", app_id=app)
    
    assert greeting == "Hello there"
    assert greet_txn.app_id == 1234
```


### Alternative ways to use `arc4.abi_call`

#### ARC4Client method 

A ARC4Client client represents the ARC4 abimethods of a smart contract and can be used to call abimethods in a type safe way

ARC4Client's can be produced by using `puyapy --output-client=True` when compiling a smart contract 
(this would be useful if you wanted to publish a client for consumption by other smart contracts)
An ARC4Client can also be be generated from an ARC-32 application.json using `puyapy-clientgen` 
e.g. `puyapy-clientgen examples/hello_world_arc4/out/HelloWorldContract.arc32.json`, this would be
the recommended approach for calling another smart contract that is not written in Algorand Python or does not provide the source

```python
from algopy import arc4, subroutine

class HelloWorldClient(arc4.ARC4Client):
    
    def hello(self, name: arc4.String) -> arc4.String: ...

@subroutine
def call_another_contract() -> None:
    # can reference another algopy contract method
    result, txn = arc4.abi_call(HelloWorldClient.hello, arc4.String("World"), app=...)
    assert result == "Hello, World"
```

#### Method signature or name

An ARC4 method selector can be used e.g. `"hello(string)string` along with a type index to specify the return type.
Additionally just a name can be provided and the method signature will be inferred e.g.

```python
from algopy import arc4, subroutine


@subroutine
def call_another_contract() -> None:
    # can reference a method selector
    result, txn = arc4.abi_call[arc4.String]("hello(string)string", arc4.String("Algo"), app=...)
    assert result == "Hello, Algo"
    
    # can reference a method name, the method selector is inferred from arguments and return type
    result, txn = arc4.abi_call[arc4.String]("hello", "There", app=...)
    assert result == "Hello, There"
```


## `algopy.arc4.arc4_create`

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

## `algopy.arc4.arc4_update`

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

## Using `itxn.ApplicationCall`

If the application being called is not an ARC4 contract, or an application specification is not available,
then [`algopy.itxn.ApplicationCall`](#algopy.itxn.ApplicationCall) can be used. This approach is generally more verbose
than the above approaches, so should only be used if required. See [here](./lg-transactions.md#create-an-arc4-application-and-then-call-it) for an example 
