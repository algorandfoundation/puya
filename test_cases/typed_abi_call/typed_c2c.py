from algopy import Application, ARC4Contract, Asset, Bytes, Global, arc4, op

from test_cases.typed_abi_call.logger import LOG_METHOD_NAME, Logger, LoggerClient


class Greeter(ARC4Contract):
    @arc4.abimethod()
    def test_method_selector_kinds(self, app: Application) -> None:
        result, _txn = arc4.abi_call(Logger.echo, arc4.String("test1"), app_id=app)
        assert result == "echo: test1"
        result, _txn = arc4.abi_call(LoggerClient.echo, "test2", app_id=app)
        assert result == "echo: test2"
        result, _txn = arc4.abi_call[arc4.String]("echo", "test3", app_id=app)
        assert result == "echo: test3"
        result, _txn = arc4.abi_call[arc4.String]("echo(string)", "test4", app_id=app)
        assert result == "echo: test4"
        result, _txn = arc4.abi_call[arc4.String]("echo(string)string", "test5", app_id=app)
        assert result == "echo: test5"

    @arc4.abimethod()
    def test_method_overload(self, app: Application) -> None:
        arc4.abi_call[arc4.String]("echo(string)string", "typed + ignore", app_id=app)
        assert arc4.String.from_log(op.ITxn.last_log()) == "echo: typed + ignore"

        arc4.abi_call("echo(string)string", "untyped + ignore", app_id=app)
        assert arc4.String.from_log(op.ITxn.last_log()) == "echo: untyped + ignore"

        result = arc4.abi_call[arc4.String]("echo(string)string", "tuple", app_id=app)
        assert result[0] == "echo: tuple"
        assert arc4.String.from_log(result[1].last_log) == "echo: tuple"

        txn_result = arc4.abi_call("echo(string)string", "untyped", app_id=app)
        assert arc4.String.from_log(txn_result.last_log) == "echo: untyped"

    @arc4.abimethod()
    def test_arg_conversion(self, app: Application) -> None:
        txn = arc4.abi_call(Logger.log_string, "converted1", app_id=app)
        assert txn.last_log == b"converted1"

        txn = arc4.abi_call(Logger.log_uint64, 2, app_id=app)
        assert txn.last_log == op.itob(2)

        txn = arc4.abi_call(Logger.log_uint512, 3, app_id=app)
        assert txn.last_log == (op.bzero(56) + op.itob(3))

        txn = arc4.abi_call(Logger.log_bytes, b"4", app_id=app)
        assert txn.last_log == b"4"

        txn = arc4.abi_call(Logger.log_bool, True, app_id=app)
        assert txn.last_log == b"True"

    @arc4.abimethod()
    def test_15plus_args(self, app: Application) -> None:
        result, txn = arc4.abi_call(
            Logger.return_args_after_14th,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            arc4.Tuple((arc4.UInt8(0xDE), arc4.UInt8(0xAD), arc4.UInt8(0xBE), arc4.UInt8(0xEF))),
            20,
            app_id=app,
        )
        assert result.native == Bytes.from_hex("0F101112DEADBEEF14")

    @arc4.abimethod()
    def test_void(self, app: Application) -> None:
        txn = arc4.abi_call(LOG_METHOD_NAME + "(string)void", "World1", app_id=app)
        assert txn.last_log == b"World1"

        txn = arc4.abi_call(LOG_METHOD_NAME + "(string)", "World2", app_id=app)
        assert txn.last_log == b"World2"

        txn = arc4.abi_call(LOG_METHOD_NAME, arc4.String("World3"), app_id=app)
        assert txn.last_log == b"World3"

        txn = arc4.abi_call(Logger.log_string, "World4", app_id=app)
        assert txn.last_log == b"World4"

    @arc4.abimethod()
    def test_ref_types(self, app: Application, asset: Asset) -> None:
        txn = arc4.abi_call(
            Logger.log_asset_account_app,
            asset,
            Global.current_application_address,
            app,
            app_id=app,
        )
        assert (
            txn.last_log
            == asset.name + Global.current_application_address.bytes + app.address.bytes
        )
