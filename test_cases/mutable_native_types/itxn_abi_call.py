from algopy import (
    Array as NativeArray,
    Bytes,
    String,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
    size_of,
    zero_bytes,
)

from test_cases.mutable_native_types.abi_call import (
    CallMe,
    DynamicStruct,
    FixedStruct,
    FixedStruct3,
    NestedStruct,
)


class TestItxnAbiCall(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_fixed_struct(self) -> None:
        create_txn = arc4.arc4_create(CallMe)
        app = create_txn.created_app

        # fixed struct - typed
        fixed_struct = FixedStruct(a=Txn.num_app_args + 1, b=Txn.num_app_args + 2)
        itxn.abi_call(CallMe.fixed_struct_arg, fixed_struct, app_id=app).submit()
        res = itxn.abi_call(CallMe.fixed_struct_ret, app_id=app).submit().result
        assert res == fixed_struct, "should be the same"

        # fixed struct - arc4 signature
        fixed_struct = FixedStruct(a=Txn.num_app_args + 2, b=Txn.num_app_args + 3)
        itxn.abi_call("fixed_struct_arg((uint64,uint64))void", fixed_struct, app_id=app).submit()
        res = (
            itxn.abi_call[FixedStruct]("fixed_struct_ret()(uint64,uint64)", app_id=app)
            .submit()
            .result
        )
        assert res == fixed_struct, "should be the same"

        itxn.abi_call(CallMe.delete, app_id=app).submit()

    @arc4.abimethod()
    def test_nested_struct(self) -> None:
        create_txn = arc4.arc4_create(CallMe)
        app = create_txn.created_app

        # nested struct - typed
        nested_struct = NestedStruct(
            fixed=FixedStruct(a=Txn.num_app_args + 1, b=Txn.num_app_args + 2),
            c=Txn.num_app_args + 3,
        )
        itxn.abi_call(CallMe.nested_struct_arg, nested_struct, app_id=app).submit()
        res = itxn.abi_call(CallMe.nested_struct_ret, app_id=app).submit().result
        assert res == nested_struct, "should be the same"

        # nested struct - arc4 signature
        nested_struct = NestedStruct(
            fixed=FixedStruct(a=Txn.num_app_args + 2, b=Txn.num_app_args + 3),
            c=Txn.num_app_args + 4,
        )
        itxn.abi_call(
            "nested_struct_arg(((uint64,uint64),uint64))void", nested_struct, app_id=app
        ).submit()
        res = (
            itxn.abi_call[NestedStruct]("nested_struct_ret()((uint64,uint64),uint64)", app_id=app)
            .submit()
            .result
        )
        assert res == nested_struct, "should be the same"

        itxn.abi_call(CallMe.delete, app_id=app).submit()

    @arc4.abimethod()
    def test_dynamic_struct(self) -> None:
        create_txn = arc4.arc4_create(CallMe)
        app = create_txn.created_app

        fixed_struct = FixedStruct(a=Txn.num_app_args + 1, b=Txn.num_app_args + 2)

        # dynamic struct - typed
        dynamic_struct = DynamicStruct(
            a=Txn.num_app_args + 1,
            b=Txn.num_app_args + 2,
            c=op.itob(Txn.num_app_args + 3),
            d=String("Hello"),
            e=NativeArray((fixed_struct,)),
        )
        itxn.abi_call(CallMe.dynamic_struct_arg, dynamic_struct, app_id=app).submit()
        res = itxn.abi_call(CallMe.dynamic_struct_ret, app_id=app).submit().result
        assert res == dynamic_struct, "should be the same"

        # dynamic struct - arc4 signature
        dynamic_struct = DynamicStruct(
            a=Txn.num_app_args + 2,
            b=Txn.num_app_args + 3,
            c=op.itob(Txn.num_app_args + 4),
            d=String("Hello"),
            e=NativeArray((fixed_struct,)),
        )
        itxn.abi_call(
            "dynamic_struct_arg((uint64,uint64,byte[],string,(uint64,uint64)[]))void",
            dynamic_struct,
            app_id=app,
        ).submit()
        res = (
            itxn.abi_call[DynamicStruct](
                "dynamic_struct_ret()(uint64,uint64,byte[],string,(uint64,uint64)[])", app_id=app
            )
            .submit()
            .result
        )
        assert res == dynamic_struct, "should be the same"

        itxn.abi_call(CallMe.delete, app_id=app).submit()

    @arc4.abimethod()
    def test_fixed_array(self) -> None:
        create_txn = arc4.arc4_create(CallMe)
        app = create_txn.created_app

        fixed_struct = FixedStruct(a=Txn.num_app_args + 1, b=Txn.num_app_args + 2)
        fixed_arr = FixedStruct3((fixed_struct, fixed_struct, fixed_struct))

        # fixed array - typed
        itxn.abi_call(CallMe.fixed_arr_arg, fixed_arr, app_id=app).submit()
        res = itxn.abi_call(CallMe.fixed_arr_ret, app_id=app).submit().result
        assert res == fixed_arr, "should be the same"

        # fixed array - arc4 signature
        fixed_struct = FixedStruct(a=Txn.num_app_args + 2, b=Txn.num_app_args + 3)
        fixed_arr = FixedStruct3((fixed_struct, fixed_struct, fixed_struct))
        itxn.abi_call(
            "fixed_arr_arg((uint64,uint64)[3])void",
            fixed_arr,
            app_id=app,
        ).submit()
        res = (
            itxn.abi_call[FixedStruct3]("fixed_arr_ret()(uint64,uint64)[3]", app_id=app)
            .submit()
            .result
        )
        assert res == fixed_arr, "should be the same"

        itxn.abi_call(CallMe.delete, app_id=app).submit()

    @arc4.abimethod()
    def test_native_array(self) -> None:
        create_txn = arc4.arc4_create(CallMe)
        app = create_txn.created_app

        fixed_struct = FixedStruct(a=Txn.num_app_args + 1, b=Txn.num_app_args + 2)
        native_arr = NativeArray((fixed_struct, fixed_struct, fixed_struct))

        # native array - typed
        itxn.abi_call(CallMe.native_arr_arg, native_arr, app_id=app).submit()
        res = itxn.abi_call(CallMe.native_arr_ret, app_id=app).submit().result
        assert res == native_arr, "should be the same"

        # native array - arc4 signature
        fixed_struct = FixedStruct(a=Txn.num_app_args + 2, b=Txn.num_app_args + 3)
        native_arr = NativeArray((fixed_struct, fixed_struct, fixed_struct))
        itxn.abi_call(
            "native_arr_arg((uint64,uint64)[])void",
            native_arr,
            app_id=app,
        ).submit()
        res = (
            itxn.abi_call[NativeArray[FixedStruct]](
                "native_arr_ret()(uint64,uint64)[]", app_id=app
            )
            .submit()
            .result
        )
        assert res == native_arr, "should be the same"

        itxn.abi_call(CallMe.delete, app_id=app).submit()

    @arc4.abimethod()
    def test_log(self) -> None:
        create_txn = arc4.arc4_create(CallMe)
        app = create_txn.created_app

        # fixed struct
        fixed_struct = zero_bytes(FixedStruct)
        itxn.abi_call(CallMe.fixed_struct_arg, fixed_struct, app_id=app).submit()

        # nested struct
        nested_struct = zero_bytes(NestedStruct)
        itxn.abi_call(CallMe.nested_struct_arg, nested_struct, app_id=app).submit()

        # dynamic struct
        dynamic_struct = DynamicStruct(
            a=UInt64(), b=UInt64(), c=Bytes(), d=String(), e=NativeArray[FixedStruct]()
        )
        itxn.abi_call(CallMe.dynamic_struct_arg, dynamic_struct, app_id=app).submit()

        # fixed array
        fixed_arr = zero_bytes(FixedStruct3)
        itxn.abi_call(CallMe.fixed_arr_arg, fixed_arr, app_id=app).submit()

        # native array
        native_arr = NativeArray[FixedStruct]()
        itxn.abi_call(CallMe.native_arr_arg, native_arr, app_id=app).submit()
        txn = itxn.abi_call(CallMe.log_it, app_id=app).submit()
        assert txn.num_logs == 5, "expected 5 logs"
        assert txn.logs(0) == op.bzero(size_of(FixedStruct)), "expected fixed struct"
        assert txn.logs(1) == op.bzero(size_of(NestedStruct)), "expected nested struct"
        dynamic_struct_len = size_of(UInt64) * 2  # a + b
        dynamic_struct_len += 2 * 3  # head for c, d, e
        dynamic_struct_len += 2 * 3  # tail for c, d, e
        assert txn.logs(2).length == dynamic_struct_len, "expected dynamic struct"
        assert txn.logs(3) == op.bzero(size_of(FixedStruct3)), "expected fixed array"
        assert txn.logs(4) == op.bzero(2), "expected fixed array"

        itxn.abi_call(CallMe.delete, app_id=app).submit()
