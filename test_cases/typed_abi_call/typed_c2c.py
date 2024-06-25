from algopy import (
    Application,
    ARC4Contract,
    Asset,
    BigUInt,
    Bytes,
    Global,
    String,
    UInt64,
    arc4,
    op,
)

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

    @arc4.abimethod()
    def test_native_string(self, app: Application) -> None:
        result1, _txn = arc4.abi_call(Logger.echo_native_string, "s", app_id=app)
        assert result1 == "echo: s"

        result2, _txn = arc4.abi_call(Logger.echo_native_string, String("s"), app_id=app)
        assert result2 == result1

        result3, _txn = arc4.abi_call(Logger.echo_native_string, arc4.String("s"), app_id=app)
        assert result3 == result1

    @arc4.abimethod()
    def test_native_bytes(self, app: Application) -> None:
        result1, _txn = arc4.abi_call(Logger.echo_native_bytes, b"b", app_id=app)
        assert result1 == b"echo: b"

        result2, _txn = arc4.abi_call(Logger.echo_native_bytes, Bytes(b"b"), app_id=app)
        assert result2 == result1

        result3, _txn = arc4.abi_call(
            Logger.echo_native_bytes, arc4.DynamicBytes(b"b"), app_id=app
        )
        assert result3 == result1

    @arc4.abimethod()
    def test_native_uint64(self, app: Application) -> None:
        result1, _txn = arc4.abi_call(Logger.echo_native_uint64, 1, app_id=app)
        assert result1 == 2

        result2, _txn = arc4.abi_call(Logger.echo_native_uint64, UInt64(1), app_id=app)
        assert result2 == result1

        result3, _txn = arc4.abi_call(Logger.echo_native_uint64, arc4.UInt64(1), app_id=app)
        assert result3 == result1

    @arc4.abimethod()
    def test_native_biguint(self, app: Application) -> None:
        result1, _txn = arc4.abi_call(Logger.echo_native_biguint, 2, app_id=app)
        assert result1 == 3

        result2, _txn = arc4.abi_call(Logger.echo_native_biguint, BigUInt(2), app_id=app)
        assert result2 == result1

        result3, _txn = arc4.abi_call(Logger.echo_native_biguint, arc4.UInt512(2), app_id=app)
        assert result3 == result1

    @arc4.abimethod()
    def test_native_tuple(self, app: Application) -> None:
        # python literals

        # NOTE: the following uses method selectors to work around having nested tuples
        txn = arc4.abi_call(
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            "s1",
            b"b1",
            1,
            2,
            app_id=app,
        )
        result1 = arc4.Tuple[arc4.String, arc4.DynamicBytes, arc4.UInt64, arc4.UInt512].from_log(
            txn.last_log
        )
        s, b, u, bu = result1.native
        assert s.native == "echo: s1"
        assert b.native == b"echo: b1"
        assert u.native == 2
        assert bu.native == 3

        # test again using native types in arguments
        txn = arc4.abi_call(
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            String("s1"),
            Bytes(b"b1"),
            UInt64(1),
            BigUInt(2),
            app_id=app,
        )
        result2 = arc4.Tuple[arc4.String, arc4.DynamicBytes, arc4.UInt64, arc4.UInt512].from_log(
            txn.last_log
        )
        assert result1 == result2

        # test again using arc4 types in arguments
        txn = arc4.abi_call(
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            arc4.String("s1"),
            arc4.DynamicBytes(b"b1"),
            arc4.UInt64(1),
            arc4.UInt512(2),
            app_id=app,
        )
        result3 = arc4.Tuple[arc4.String, arc4.DynamicBytes, arc4.UInt64, arc4.UInt512].from_log(
            txn.last_log
        )
        assert result1 == result3
