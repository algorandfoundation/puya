import typing

from algopy import Application, ARC4Contract, String, UInt64, arc4


# example: ARC4_CLIENT_PROTOCOL
class HelloWorldClient(arc4.ARC4Client, typing.Protocol):
    """
    A typed client for an *external* ARC-4 contract.
    It subclasses both `arc4.ARC4Client` and `typing.Protocol` and describes
    the methods we want to call by their signatures with stubbed bodies
    (`...`).

    A client like this can be generated from a compiled contract by
    passing the `--output-client` option to the PuyaPy compiler.

    The signatures match the on-chain contract's published ABI; puya
    uses them to:
      * derive the correct ABI selector for each call,
      * type-check the args we pass,
      * type the return value.

    A typed client is preferable to passing a method-name string to
    `arc4.abi_call` because mistakes (wrong arg type, missing arg, etc.)
    are caught at compile time rather than as on-chain failures.
    """

    @arc4.abimethod
    def hello(self, name: String) -> String: ...

    @arc4.abimethod
    def add(self, a: UInt64, b: UInt64) -> UInt64: ...


# example: ARC4_CLIENT_PROTOCOL


# example: ARC4_ABI_CALL_CLIENT
class ClientConsumer(ARC4Contract):
    """
    Calls into an external contract via the typed `HelloWorldClient`. Each
    `arc4.abi_call(HelloWorldClient.method, ...)` returns a
    `(result, inner_txn)` tuple where `result` has the type declared in
    the protocol.
    """

    @arc4.abimethod
    def call_hello(self, app: Application, name: String) -> String:
        """Call `hello(string)string` on the target app. The return type is
        inferred as `String` from the client protocol."""
        result, _txn = arc4.abi_call(
            HelloWorldClient.hello,
            name,
            app_id=app,
            # fee=0 means the outer transaction must cover the inner fee
            fee=0,
        )
        return result

    @arc4.abimethod
    def call_add(self, app: Application, a: UInt64, b: UInt64) -> UInt64:
        """Call `add(uint64,uint64)uint64`. Arg types are checked against
        the protocol method signature at compile time.

        The second tuple element is the inner transaction handle.
        It's useful when you want to inspect the call after the fact (e.g.
        confirm which app id was hit, read emitted logs, etc.)."""
        result, txn = arc4.abi_call(
            HelloWorldClient.add,
            a,
            b,
            app_id=app,
            fee=0,
        )
        assert txn.num_logs == 1, "only the return log was emitted by the app"
        return result


# example: ARC4_ABI_CALL_CLIENT
