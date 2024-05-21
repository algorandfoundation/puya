import typing

from algopy import Account, Application, ARC4Contract, Asset, Bytes, Txn, arc4, log

LOG_METHOD_NAME = "log"


class Logger(ARC4Contract):
    @arc4.abimethod
    def echo(self, value: arc4.String) -> arc4.String:
        return "echo: " + value

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


class LoggerClient(arc4.ARC4Client, typing.Protocol):
    @arc4.abimethod
    def echo(self, value: arc4.String) -> arc4.String: ...
