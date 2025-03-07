from algopy import ARC4Contract, ImmutableArray
from algopy.arc4 import Bool, DynamicArray, abi_call, abimethod, arc4_create

from test_cases.arc4_encode_decode.receiver import Receiver


class Arc4EncodeDecodeContract(ARC4Contract):
    @abimethod
    def test_arc4_bool_array(self) -> None:
        bools = ImmutableArray(Bool(True), Bool(True))
        bools_d = DynamicArray(Bool(True), Bool(True))
        bools_t = Bool(True), Bool(True)

        app_id = arc4_create(Receiver).app_id

        result = abi_call(Receiver.receive_bools, bools, app_id=app_id)
        result = abi_call(Receiver.receive_bools, bools_d, app_id=app_id)
        result = abi_call(Receiver.receive_bools, bools_t, app_id=app_id)
