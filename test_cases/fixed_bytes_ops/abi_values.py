import typing

from algopy import Bytes, FixedBytes, arc4


class FixedBytesABI(arc4.ARC4Contract):
    @arc4.abimethod
    def test_passing_fixed_bytes(self) -> None:
        app = arc4.arc4_create(CheckABIApp).created_app

        arc4.abi_call(
            CheckABIApp.check_fixed_bytes,
            FixedBytes[typing.Literal[11]](b"Hello World"),
            b"Hello World",
            app_id=app,
        )


class CheckABIApp(arc4.ARC4Contract):
    @arc4.abimethod
    def check_fixed_bytes(self, value: FixedBytes[typing.Literal[11]], expected: Bytes) -> None:
        assert value.bytes == expected, "expected to encode correctly"
