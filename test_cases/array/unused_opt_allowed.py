# this test case contains code that requires the remove_unused_variables optimization
import typing

from algopy import Application, ImmutableArray, UInt64, arc4


class MyTuple(typing.NamedTuple):
    foo: ImmutableArray[UInt64]
    bar: UInt64


class AbiCallContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_implicit_conversion_abi_call(
        self, arr: ImmutableArray[UInt64], app: Application
    ) -> None:
        # itxn requires remove_unused_variables
        arc4.abi_call("dont_call(uint64[])uint64", arr, app_id=app)

        nested_arr = ImmutableArray[ImmutableArray[UInt64]]()
        nested_arr = nested_arr.append(arr)
        arc4.abi_call("dont_call(uint64[][])uint64", nested_arr, app_id=app)

        indirect_nested_arr = ImmutableArray[MyTuple]()
        indirect_nested_arr.append(MyTuple(foo=arr, bar=arr.length))
        arc4.abi_call("dont_call((uint64[],uint64)[])uint64", indirect_nested_arr, app_id=app)
