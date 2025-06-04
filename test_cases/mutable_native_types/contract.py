import typing

from algopy import (
    Account,
    Asset,
    Box,
    BoxMap,
    Bytes,
    FixedArray,
    GlobalState,
    LocalState,
    NativeArray,
    OnCompleteAction,
    String,
    Struct,
    TransactionType,
    Txn,
    UInt64,
    arc4,
    subroutine,
    zero_bytes,
)

BigBytes = FixedArray[arc4.Byte, typing.Literal[2048]]


FixedUInt64Of3 = FixedArray[UInt64, typing.Literal[3]]


class FixedStruct(Struct, frozen=True, kw_only=True):
    a: UInt64
    b: UInt64


class Payment(Struct):
    receiver: Account
    asset: Asset
    amt: UInt64


class NamedTup(typing.NamedTuple):
    a: UInt64
    b: UInt64


class NestedStruct(Struct):
    fixed_a: FixedStruct
    fixed_b: FixedStruct
    tup: NamedTup


class LargeFixedStruct(Struct):
    fixed_a: FixedStruct
    big_bytes: BigBytes
    # TODO: add c once boxes support mutating values > 4k
    # c: BigBytes


class DynamicStruct(Struct):
    a: UInt64
    b: UInt64
    c: Bytes
    d: String
    e: NativeArray[arc4.Byte]


class Contract(arc4.ARC4Contract):
    def __init__(self) -> None:
        # storage
        self.nested = NestedStruct(
            FixedStruct(a=Txn.num_app_args, b=Txn.num_app_args),
            FixedStruct(a=Txn.num_app_args + 1, b=Txn.num_app_args + 1),
            NamedTup(a=Txn.num_app_args + 1, b=Txn.num_app_args + 1),
        )
        self.nested_proxy = GlobalState(NestedStruct, key=b"p", description="some documentation")
        self.nested_local = LocalState(NestedStruct, key=b"l")
        self.box = Box(LargeFixedStruct)
        self.box_map = BoxMap(UInt64, LargeFixedStruct)

        self.dyn = DynamicStruct(
            a=Txn.num_app_args,
            b=Txn.num_app_args,
            c=Bytes(),
            d=String(),
            e=NativeArray[arc4.Byte](),
        )

        self.num_payments = UInt64(0)
        self.payments = zero_bytes(FixedArray[Payment, typing.Literal[8]])

    @arc4.abimethod()
    def fixed_initialize(self) -> None:
        arr_3 = zero_bytes(FixedUInt64Of3)
        arr_3[0] = UInt64(0)
        arr_3[1] = UInt64(1)
        arr_3[2] = UInt64(2)

        arr_3_from_tuple = FixedUInt64Of3(
            (UInt64(0), UInt64(1), UInt64(2)),
        )
        assert arr_3 == arr_3_from_tuple, "should be the same"

        arr_3_from_full = FixedUInt64Of3.full(UInt64(1))
        assert arr_3_from_full[0] == 1
        assert arr_3_from_full[1] == 1
        assert arr_3_from_full[2] == 1

        arr_3_from_fixed = FixedUInt64Of3(arr_3)
        assert arr_3 == arr_3_from_fixed, "should be the same"

        dynamic_arr = NativeArray((UInt64(0), UInt64(1), UInt64(2)))
        assert arr_3 == FixedUInt64Of3(dynamic_arr)

    @arc4.abimethod()
    def add_payment(self, pay: Payment) -> None:
        assert self.num_payments < self.payments.length, "too many payments"
        self.payments[self.num_payments] = pay.copy()
        self.num_payments += 1

    @arc4.abimethod()
    def increment_payment(self, index: UInt64, amt: UInt64) -> None:
        assert index < self.num_payments, "invalid payment index"
        self.payments[index].amt += amt

    @arc4.abimethod()
    def create_storage(self, box_key: UInt64) -> None:
        self.nested_proxy.value = self.nested.copy()
        self.nested_local[Txn.sender] = self.nested.copy()
        assert self.box.create(), "expected box to not exist"
        self.box_map[box_key].fixed_a = self.nested.fixed_a.copy()

    @arc4.abimethod()
    def local_struct(self) -> Payment:
        a = Payment(Txn.sender, Asset(1234), UInt64(567))
        # python equivalent to typescript destructuring e.g.
        # { foo, bar, baz } = a
        (foo, bar, baz) = (a.receiver, a.asset, a.amt)
        assert foo, "use foo"
        assert bar, "use bar"
        assert baz, "use baz"
        do_something(a)
        return a

    @arc4.abimethod()
    def delete_storage(self, box_key: UInt64) -> None:
        del self.nested_proxy.value
        del self.nested_local[Txn.sender]
        del self.box.value
        del self.box_map[box_key]

    # TODO: add FixedArray and NativeArray args

    @arc4.abimethod()
    def struct_arg(self, box_key: UInt64, a: FixedStruct) -> None:
        self.nested.fixed_a = a
        self.nested_proxy.value.fixed_a = a
        self.nested_local[Txn.sender].fixed_a = a
        self.box.value.fixed_a = a
        self.box_map[box_key].fixed_a = a

    # TODO: query other storage types?

    @arc4.abimethod()
    def struct_return(self) -> FixedStruct:
        return self.nested.fixed_a

    @arc4.abimethod()
    def tup_return(self) -> NamedTup:
        return self.nested.tup

    @arc4.abimethod()
    def calculate_sum(self) -> UInt64:
        fixed_a = self.nested.fixed_a
        fixed_b = self.nested.fixed_b
        result = add(fixed_a) + add(fixed_b)
        if result < 100:
            c, d = self.nested.tup
            result += c
            result += d
        return result


@subroutine()
def add(val: FixedStruct) -> UInt64:
    return val.a + val.b


@subroutine(inline=False)
def do_something(pay: Payment) -> None:
    pass


@subroutine
def tuple_conversion() -> None:
    arr3 = FixedUInt64Of3((UInt64(1), UInt64(2), UInt64(3)))
    tup3 = tuple(arr3)
    assert (tup3[0] + tup3[1] + tup3[2]) == (1 + 2 + 3)


@subroutine
def argument_subtype() -> None:
    arr3 = FixedUInt64Of3((OnCompleteAction.NoOp, UInt64(2), TransactionType.Payment))
    assert arr3[1] == 2
