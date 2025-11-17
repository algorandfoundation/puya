import typing

from algopy import Bytes, FixedBytes, arc4

FixedBytes11 = FixedBytes[typing.Literal[11]]


class FixedBytesABI(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_itxn_validate_caller_bytes(self, val: Bytes) -> None:
        app = arc4.arc4_create(CheckABIApp).created_app

        # this be validated in the caller as it will attempt to encode val to FixedBytes11
        arc4.abi_call(
            CheckABIApp.manual_validate,
            val,
            app_id=app,
        )

        arc4.abi_call(CheckABIApp.delete, app_id=app)

    @arc4.abimethod()
    def test_itxn_validate_callee_manual(self, val: Bytes) -> None:
        app = arc4.arc4_create(CheckABIApp).created_app

        fb = FixedBytes11.from_bytes(val)
        # this will be validated in the callee method as types match
        arc4.abi_call(
            CheckABIApp.manual_validate,
            fb,
            app_id=app,
        )

        arc4.abi_call(CheckABIApp.delete, app_id=app)

    @arc4.abimethod()
    def test_itxn_validate_callee_router(self, val: Bytes) -> None:
        app = arc4.arc4_create(CheckABIApp).created_app

        fb = FixedBytes11.from_bytes(val)
        # this will be validated in the callee router as types match
        arc4.abi_call(
            CheckABIApp.router_validate,
            fb,
            app_id=app,
        )

        arc4.abi_call(CheckABIApp.delete, app_id=app)


class CheckABIApp(arc4.ARC4Contract):
    @arc4.abimethod(validate_encoding="unsafe_disabled")
    def manual_validate(self, value: FixedBytes11) -> None:
        assert value.bytes.length == 11, "callee method check failed"

    @arc4.abimethod(validate_encoding="args")
    def router_validate(self, value: FixedBytes11) -> None:
        assert value.bytes.length == 11, "callee method check failed"

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        pass
