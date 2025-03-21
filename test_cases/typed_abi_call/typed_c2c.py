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

from test_cases.typed_abi_call.logger import (
    LOG_METHOD_NAME,
    Logger,
    LoggerClient,
    LogMessage,
    LogStruct,
)


class Greeter(ARC4Contract):
    @arc4.abimethod
    def test_is_a_b(self, a: Bytes, b: Bytes, app: Application) -> None:
        arc4.abi_call(
            "is_a_b(byte[],byte[])void",
            a,
            b,
            app_id=app,
        )

    @arc4.abimethod()
    def test_method_selector_kinds(self, app: Application) -> None:
        assert arc4.arc4_signature(Logger.echo) == arc4.arc4_signature("echo(string)string")
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
    def test_account_to_address(self, app: Application) -> None:
        txn = arc4.abi_call(
            Logger.log_address,
            Global.current_application_address,
            app_id=app,
        )
        assert txn.last_log == Global.current_application_address.bytes

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
        result1, txn = arc4.abi_call[
            arc4.Tuple[arc4.String, arc4.DynamicBytes, arc4.UInt64, arc4.UInt512]
        ](
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            "s1",
            b"b1",
            1,
            2,
            app_id=app,
        )
        s, b, u, bu = result1.native
        assert s.native == "echo: s1"
        assert b.native == b"echo: b1"
        assert u.native == 2
        assert bu.native == 3

        # test again using native types in arguments
        result2, txn = arc4.abi_call[
            arc4.Tuple[arc4.String, arc4.DynamicBytes, arc4.UInt64, arc4.UInt512]
        ](
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            String("s1"),
            Bytes(b"b1"),
            UInt64(1),
            BigUInt(2),
            app_id=app,
        )
        assert result1 == result2

        # test again using arc4 types in arguments
        result3, txn = arc4.abi_call[
            arc4.Tuple[arc4.String, arc4.DynamicBytes, arc4.UInt64, arc4.UInt512]
        ](
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            arc4.String("s1"),
            arc4.DynamicBytes(b"b1"),
            arc4.UInt64(1),
            arc4.UInt512(2),
            app_id=app,
        )
        assert result1 == result3

        # test again using native result type
        result_native, txn = arc4.abi_call[tuple[String, Bytes, UInt64, BigUInt]](
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            arc4.String("s1"),
            arc4.DynamicBytes(b"b1"),
            arc4.UInt64(1),
            arc4.UInt512(2),
            app_id=app,
        )
        assert result1.native[0].native == result_native[0]
        assert result1.native[1].native == result_native[1]
        assert result1.native[2].native == result_native[2]
        assert result1.native[3].native == result_native[3]

    @arc4.abimethod()
    def test_native_tuple_method_ref(self, app: Application) -> None:
        # test with literal args
        result, txn = arc4.abi_call(
            Logger.echo_native_tuple,
            "s1",
            b"b1",
            1,
            2,
            app_id=app,
        )
        (s, b, u, bu) = result
        assert s == "echo: s1"
        assert b == b"echo: b1"
        assert u == 2
        assert bu == 3

        # test with native args
        result_2, txn = arc4.abi_call(
            Logger.echo_native_tuple,
            String("s1"),
            Bytes(b"b1"),
            UInt64(1),
            BigUInt(2),
            app_id=app,
        )
        assert result_2 == result, "expected native arguments to give the same result"

        # test with arc4 args
        result_3, txn = arc4.abi_call(
            Logger.echo_native_tuple,
            arc4.String("s1"),
            arc4.DynamicBytes(b"b1"),
            arc4.UInt64(1),
            arc4.UInt512(2),
            app_id=app,
        )
        assert result_3 == result, "expected arc4 arguments to give the same result"

        # test again using native result type
        result_native, txn = arc4.abi_call[tuple[String, Bytes, UInt64, BigUInt]](
            "echo_native_tuple(string,byte[],uint64,uint512)(string,byte[],uint64,uint512)",
            arc4.String("s1"),
            arc4.DynamicBytes(b"b1"),
            arc4.UInt64(1),
            arc4.UInt512(2),
            app_id=app,
        )
        assert result_native == result

    @arc4.abimethod()
    def test_nested_tuples(self, app: Application) -> None:
        # literal args
        result, txn = arc4.abi_call(
            Logger.echo_nested_tuple,
            (("s1", "s2"), (1, 2, b"3")),
            app_id=app,
        )
        ((s1, s2), (u64_1, u64_2, bytez)) = result
        assert s1 == "echo: s1"
        assert s2 == "echo: s2"
        assert u64_1 == 2
        assert u64_2 == 3
        assert bytez == b"echo: 3"

        # native args
        result, txn = arc4.abi_call(
            Logger.echo_nested_tuple,
            ((String("s1"), arc4.String("s2")), (UInt64(1), arc4.UInt64(2), Bytes(b"3"))),
            app_id=app,
        )
        ((s1, s2), (u64_1, u64_2, bytez)) = result
        assert s1 == "echo: s1"
        assert s2 == "echo: s2"
        assert u64_1 == 2
        assert u64_2 == 3
        assert bytez == b"echo: 3"

        # arc4 args
        result, txn = arc4.abi_call(
            Logger.echo_nested_tuple,
            arc4.Tuple(
                (
                    arc4.Tuple((arc4.String("s1b"), arc4.String("s2b"))),
                    arc4.Tuple((arc4.UInt64(11), arc4.UInt64(21), arc4.DynamicBytes(b"3b"))),
                )
            ),
            app_id=app,
        )
        ((s1, s2), (u64_1, u64_2, bytez)) = result
        assert s1 == "echo: s1b"
        assert s2 == "echo: s2b"
        assert u64_1 == 12
        assert u64_2 == 22
        assert bytez == b"echo: 3b"

    @arc4.abimethod()
    def test_no_args(self, app: Application) -> None:
        result, _txn = arc4.abi_call(Logger.no_args, app_id=app)
        assert result == 42
        arc4_result, _txn = arc4.abi_call[arc4.UInt64]("no_args()uint64", app_id=app)
        assert arc4_result == 42

        arc4.abi_call(Logger.no_args, app_id=app)
        assert arc4.UInt64.from_log(op.ITxn.last_log()) == 42

    @arc4.abimethod()
    def test_named_tuples(self, app: Application) -> None:
        result, _txn = arc4.abi_call(
            Logger.logs_are_equal,
            (UInt64(1), String("log 1")),
            LogMessage(level=UInt64(1), message=String("log 1")),
            app_id=app,
        )
        assert result
        result, _txn = arc4.abi_call(
            Logger.logs_are_equal,
            (UInt64(2), String("log 2")),
            LogMessage(level=UInt64(1), message=String("log 1")),
            app_id=app,
        )
        assert not result

    @arc4.abimethod()
    def test_arc4_struct(self, app: Application) -> None:
        log = LogStruct(level=arc4.UInt64(1), message=arc4.String("log 1"))
        result, txn = arc4.abi_call(
            Logger.echo_log_struct,
            log,
            app_id=app,
        )
        assert result == log, "expected output to match input"
        assert LogStruct.from_log(txn.last_log) == log, "expected output to match input"
