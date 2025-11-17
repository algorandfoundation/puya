import typing

from algopy import Application, Bytes, FixedBytes, arc4

FixedBytes11 = FixedBytes[typing.Literal[11]]


class FixedBytesABI(arc4.ARC4Contract):
    @arc4.abimethod(resource_encoding="index")
    def test_itxn_validate_caller_bytes(self, checker: Application, val: Bytes) -> None:
        # this be validated in the caller as it will attempt to encode val to FixedBytes11
        arc4.abi_call(
            CheckABIApp.manual_validate,
            val,
            app_id=checker,
        )

    @arc4.abimethod(resource_encoding="index")
    def test_itxn_validate_callee_manual(self, checker: Application, val: Bytes) -> None:
        fb = FixedBytes11.from_bytes(val)
        # this will be validated in the callee method as types match
        arc4.abi_call(
            CheckABIApp.manual_validate,
            fb,
            app_id=checker,
        )

    @arc4.abimethod(resource_encoding="index")
    def test_itxn_validate_callee_router(self, checker: Application, val: Bytes) -> None:
        fb = FixedBytes11.from_bytes(val)
        # this will be validated in the callee router as types match
        arc4.abi_call(
            CheckABIApp.router_validate,
            fb,
            app_id=checker,
        )

    @arc4.abimethod(resource_encoding="index")
    def test_static_to_dynamic_encoding(self, checker: Application) -> None:
        fb = FixedBytes11(b"hello world")
        arc4.abi_call(
            CheckABIApp.i_am_a_dynamic_personality,
            fb,
            app_id=checker,
        )


class CheckABIApp(arc4.ARC4Contract):
    @arc4.abimethod(validate_encoding="unsafe_disabled")
    def manual_validate(self, value: FixedBytes11) -> None:
        assert value.bytes.length == 11, "callee method check failed"

    @arc4.abimethod(validate_encoding="args")
    def router_validate(self, value: FixedBytes11) -> None:
        assert value.bytes.length == 11, "callee method check failed"

    @arc4.abimethod
    def i_am_a_dynamic_personality(self, value: arc4.DynamicBytes) -> None:
        assert value.native == b"hello world"
