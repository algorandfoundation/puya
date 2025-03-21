import typing

from algopy import (
    Account,
    Application,
    ARC4Contract,
    Asset,
    BigUInt,
    Bytes,
    String,
    Txn,
    UInt64,
    arc4,
    log,
)

LOG_METHOD_NAME = "log"


class LogMessage(typing.NamedTuple):
    level: UInt64
    message: String


class LogStruct(arc4.Struct):
    level: arc4.UInt64
    message: arc4.String


class Logger(ARC4Contract):
    @arc4.abimethod
    def is_a_b(self, a: Bytes, b: Bytes) -> None:
        assert a == b"a", "a is not a"
        assert b == b"b", "b is not b"

    @arc4.abimethod
    def echo(self, value: arc4.String) -> arc4.String:
        return "echo: " + value

    @arc4.abimethod
    def no_args(self) -> UInt64:
        return UInt64(42)

    @arc4.abimethod(name=LOG_METHOD_NAME)
    def log_uint64(self, value: arc4.UInt64) -> None:
        log(value)

    @arc4.abimethod(name=LOG_METHOD_NAME)
    def log_uint512(self, value: arc4.UInt512) -> None:
        log(value)

    @arc4.abimethod(name=LOG_METHOD_NAME)
    def log_string(self, value: arc4.String) -> None:
        log(value.native)  # decode to remove header

    @arc4.abimethod(name=LOG_METHOD_NAME)
    def log_bool(self, value: arc4.Bool) -> None:
        log(Bytes(b"True") if value.native else Bytes(b"False"))

    @arc4.abimethod(name=LOG_METHOD_NAME)
    def log_bytes(self, value: arc4.DynamicBytes) -> None:
        log(value.native)

    @arc4.abimethod(name=LOG_METHOD_NAME)
    def log_asset_account_app(self, asset: Asset, account: Account, app: Application) -> None:
        log(asset.name, account.bytes, app.address)

    @arc4.abimethod(name=LOG_METHOD_NAME)
    def log_address(self, address: arc4.Address) -> None:
        log(address)

    @arc4.abimethod
    def echo_native_string(self, value: String) -> String:
        return "echo: " + value

    @arc4.abimethod
    def echo_native_bytes(self, value: Bytes) -> Bytes:
        return b"echo: " + value

    @arc4.abimethod
    def echo_native_uint64(self, value: UInt64) -> UInt64:
        return value + 1

    @arc4.abimethod
    def echo_native_biguint(self, value: BigUInt) -> BigUInt:
        return value + 1

    @arc4.abimethod
    def echo_native_tuple(
        self, s: String, b: Bytes, u: UInt64, bu: BigUInt
    ) -> tuple[String, Bytes, UInt64, BigUInt]:
        return "echo: " + s, b"echo: " + b, u + 1, bu + 1

    @arc4.abimethod
    def echo_nested_tuple(
        self, tuple_of_tuples: tuple[tuple[String, arc4.String], tuple[UInt64, arc4.UInt64, Bytes]]
    ) -> tuple[tuple[String, arc4.String], tuple[UInt64, arc4.UInt64, Bytes]]:
        (string, arc4_string), (u64, arc4_u64, bytez) = tuple_of_tuples
        return ("echo: " + string, "echo: " + arc4_string), (
            u64 + 1,
            arc4.UInt64(arc4_u64.native + 1),
            b"echo: " + bytez,
        )

    @arc4.abimethod
    def return_args_after_14th(
        self,
        _a1: arc4.UInt64,
        _a2: arc4.UInt64,
        _a3: arc4.UInt64,
        _a4: arc4.UInt64,
        _a5: arc4.UInt64,
        _a6: arc4.UInt64,
        _a7: arc4.UInt64,
        _a8: arc4.UInt64,
        _a9: arc4.UInt64,
        _a10: arc4.UInt64,
        _a11: arc4.UInt64,
        _a12: arc4.UInt64,
        _a13: arc4.UInt64,
        _a14: arc4.UInt64,
        a15: arc4.UInt8,
        a16: arc4.UInt8,
        a17: arc4.UInt8,
        a18: arc4.UInt8,
        a19: arc4.Tuple[arc4.UInt8, arc4.UInt8, arc4.UInt8, arc4.UInt8],
        a20: arc4.UInt8,
    ) -> arc4.DynamicBytes:
        last_arg = arc4.Tuple((a15, a16, a17, a18, a19, a20))
        assert Txn.application_args(15) == last_arg.bytes
        return arc4.DynamicBytes(last_arg.bytes)

    @arc4.abimethod
    def logs_are_equal(self, log_1: LogMessage, log_2: LogMessage) -> bool:
        return log_1 == log_2

    @arc4.abimethod
    def echo_log_struct(self, log: LogStruct) -> LogStruct:
        return log


class LoggerClient(arc4.ARC4Client, typing.Protocol):
    @arc4.abimethod
    def echo(self, value: arc4.String) -> arc4.String: ...
