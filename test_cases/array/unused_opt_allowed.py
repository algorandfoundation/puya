# this test case contains code that requires the remove_unused_variables optimization
from algopy import Application, ImmutableArray, UInt64, arc4


class AbiCallContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_implicit_conversion_abi_call(
        self, arr: ImmutableArray[UInt64], app: Application
    ) -> None:
        # itxn requires remove_unused_variables
        arc4.abi_call("dont_call(uint64[])uint64", arr, app_id=app)
