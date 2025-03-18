import typing

from algopy import (
    Account,
    BigUInt,
    Bytes,
    ImmutableArray,
    String,
    Txn,
    UInt64,
    arc4,
    op,
    subroutine,
)


class TestContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_literal_encoding(self) -> None:
        app = arc4.arc4_create(CheckApp).created_app

        # uint64
        arc4.abi_call(CheckApp.check_uint64, 0, op.bzero(8), app_id=app)

        # bytes
        arc4.abi_call(
            CheckApp.check_dynamic_bytes, b"Hello World", b"\x00\x0bHello World", app_id=app
        )

        # string
        arc4.abi_call(CheckApp.check_string, "Hello World", b"\x00\x0bHello World", app_id=app)

        # biguint
        arc4.abi_call(CheckApp.check_biguint, BigUInt(), op.bzero(64), app_id=app)

        # bool
        arc4.abi_call(CheckApp.check_bool, True, b"\x80", app_id=app)

        arc4.abi_call(CheckApp.delete_application, app_id=app)

    @arc4.abimethod()
    def test_native_encoding(self) -> None:
        app = arc4.arc4_create(CheckApp).created_app

        # uint64
        arc4.abi_call(CheckApp.check_uint64, Txn.num_app_args - 1, op.bzero(8), app_id=app)

        # bytes
        arc4.abi_call(
            CheckApp.check_dynamic_bytes,
            Txn.application_args(0),
            b"\x00\x04" + Txn.application_args(0),
            app_id=app,
        )

        # bytes
        arc4.abi_call(
            CheckApp.check_string, String("Hello World"), b"\x00\x0bHello World", app_id=app
        )

        # biguint
        arc4.abi_call(CheckApp.check_biguint, BigUInt(), op.bzero(64), app_id=app)

        # bool
        arc4.abi_call(CheckApp.check_bool, Txn.num_app_args == 1, b"\x80", app_id=app)

        arc4.abi_call(CheckApp.delete_application, app_id=app)

    @arc4.abimethod()
    def test_arc4_encoding(self) -> None:
        app = arc4.arc4_create(CheckApp).created_app

        # uint64
        arc4.abi_call(CheckApp.check_uint64, arc4.UInt64(), op.bzero(8), app_id=app)

        # bytes
        arc4.abi_call(
            CheckApp.check_dynamic_bytes,
            arc4.DynamicBytes(Txn.application_args(0)),
            b"\x00\x04" + Txn.application_args(0),
            app_id=app,
        )

        # bytes
        arc4.abi_call(
            CheckApp.check_string, arc4.String("Hello World"), b"\x00\x0bHello World", app_id=app
        )

        # biguint
        arc4.abi_call(CheckApp.check_biguint, arc4.UInt512(), op.bzero(64), app_id=app)

        # bool
        arc4.abi_call(CheckApp.check_bool, arc4.Bool(Txn.num_app_args == 1), b"\x80", app_id=app)

        arc4.abi_call(CheckApp.delete_application, app_id=app)

    @arc4.abimethod()
    def test_array_uint64_encoding(self) -> None:
        app = arc4.arc4_create(CheckApp).created_app

        arr = ImmutableArray(Txn.num_app_args, Txn.num_app_args + 1, Txn.num_app_args + 2)
        expected_bytes = (
            b"\x00\x03" + op.bzero(7) + b"\x01" + op.bzero(7) + b"\x02" + op.bzero(7) + b"\x03"
        )
        arc4.abi_call(CheckApp.check_dyn_array_uin64, arr, expected_bytes, app_id=app)
        arc4.abi_call(
            CheckApp.check_dyn_array_uin64,
            (Txn.num_app_args, Txn.num_app_args + 1, Txn.num_app_args + 2),
            expected_bytes,
            app_id=app,
        )
        arc4.abi_call(
            CheckApp.check_static_array_uin64_3,
            (Txn.num_app_args, Txn.num_app_args + 1, Txn.num_app_args + 2),
            expected_bytes[2:],
            app_id=app,
        )

        arc4.abi_call(CheckApp.delete_application, app_id=app)

    @arc4.abimethod()
    def test_array_static_encoding(self) -> None:
        app = arc4.arc4_create(CheckApp).created_app

        arr = ImmutableArray(my_struct(UInt64(1)), my_struct(UInt64(2)), my_struct(UInt64(3)))
        expected_bytes = (
            b"\x00\x03"
            + (op.bzero(7) + b"\x01")
            + Txn.sender.bytes
            + (op.bzero(7) + b"\x02")
            + Txn.sender.bytes
            + (op.bzero(7) + b"\x03")
            + Txn.sender.bytes
        )
        arc4.abi_call(CheckApp.check_dyn_array_struct, arr, expected_bytes, app_id=app)
        arc4.abi_call(
            CheckApp.check_static_array_struct,
            (my_struct(UInt64(1)), my_struct(UInt64(2)), my_struct(UInt64(3))),
            expected_bytes[2:],
            app_id=app,
        )

        arc4.abi_call(CheckApp.delete_application, app_id=app)

    @arc4.abimethod()
    def test_array_dynamic_encoding(self) -> None:
        app = arc4.arc4_create(CheckApp).created_app

        arr = ImmutableArray(
            my_dyn_struct(UInt64(1)), my_dyn_struct(UInt64(2)), my_dyn_struct(UInt64(3))
        )
        expected_bytes = arc4.DynamicArray(
            my_dyn_struct_arc4(UInt64(1)),
            my_dyn_struct_arc4(UInt64(2)),
            my_dyn_struct_arc4(UInt64(3)),
        ).bytes
        arc4.abi_call(CheckApp.check_dyn_array_dyn_struct, arr, expected_bytes, app_id=app)

        expected_bytes = arc4.StaticArray(
            my_dyn_struct_arc4(UInt64(1)),
            my_dyn_struct_arc4(UInt64(2)),
            my_dyn_struct_arc4(UInt64(3)),
        ).bytes
        arc4.abi_call(
            CheckApp.check_static_array_dyn_struct,
            (my_dyn_struct(UInt64(1)), my_dyn_struct(UInt64(2)), my_dyn_struct(UInt64(3))),
            expected_bytes,
            app_id=app,
        )

        arc4.abi_call(CheckApp.delete_application, app_id=app)


class MyStruct(typing.NamedTuple):
    num: UInt64
    acc: Account


class MyStructARC4(arc4.Struct):
    num: arc4.UInt64
    acc: arc4.Address


@subroutine
def my_struct(value: UInt64) -> MyStruct:
    return MyStruct(value, Txn.sender)


class MyDynStruct(typing.NamedTuple):
    num: UInt64
    acc: Account
    bites: Bytes


class MyDynStructARC4(arc4.Struct):
    num: arc4.UInt64
    acc: arc4.Address
    bites: arc4.DynamicBytes


@subroutine
def my_dyn_struct(value: UInt64) -> MyDynStruct:
    return MyDynStruct(value, Txn.sender, Txn.sender.bytes)


@subroutine
def my_dyn_struct_arc4(value: UInt64) -> MyDynStructARC4:
    return MyDynStructARC4(
        arc4.UInt64(value), arc4.Address(Txn.sender), arc4.DynamicBytes(Txn.sender.bytes)
    )


class CheckApp(arc4.ARC4Contract):
    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete_application(self) -> None:
        pass

    @arc4.abimethod
    def check_uint64(self, value: arc4.UInt64, expected: Bytes) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_dynamic_bytes(self, value: arc4.DynamicBytes, expected: Bytes) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_string(self, value: arc4.String, expected: Bytes) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_biguint(self, value: arc4.UInt512, expected: Bytes) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_bool(self, value: arc4.Bool, expected: Bytes) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_dyn_array_uin64(
        self, value: arc4.DynamicArray[arc4.UInt64], expected: Bytes
    ) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_static_array_uin64_3(
        self, value: arc4.StaticArray[arc4.UInt64, typing.Literal[3]], expected: Bytes
    ) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_dyn_array_struct(
        self, value: arc4.DynamicArray[MyStructARC4], expected: Bytes
    ) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_static_array_struct(
        self, value: arc4.StaticArray[MyStructARC4, typing.Literal[3]], expected: Bytes
    ) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_dyn_array_dyn_struct(
        self, value: arc4.DynamicArray[MyDynStructARC4], expected: Bytes
    ) -> None:
        assert value.bytes == expected, "expected to encode correctly"

    @arc4.abimethod
    def check_static_array_dyn_struct(
        self, value: arc4.StaticArray[MyDynStructARC4, typing.Literal[3]], expected: Bytes
    ) -> None:
        assert value.bytes == expected, "expected to encode correctly"
