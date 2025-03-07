from algopy import ARC4Contract, Array, ImmutableArray
from algopy.arc4 import Bool, DynamicArray, abi_call, abimethod, arc4_create

from test_cases.arc4_encode_decode.receiver import Receiver


class Arc4EncodeDecodeContract(ARC4Contract):
    @abimethod
    def test_arc4_bool_array(self) -> None:
        app_id = arc4_create(Receiver).created_app

        imm_arc4 = ImmutableArray(Bool(True), Bool(True))
        abi_call(Receiver.receive_bools, imm_arc4, app_id=app_id)

        imm_nat = ImmutableArray(True, True)
        abi_call(Receiver.receive_bools, imm_nat, app_id=app_id)

        arc4_arc4 = DynamicArray(Bool(True), Bool(True))
        abi_call(Receiver.receive_bools, arc4_arc4, app_id=app_id)

        # delete app so we don't need to worry about MBR in test suite
        abi_call(Receiver.delete, app_id=app_id)

    @abimethod
    def test_arc4_bool_array_not_working(self) -> None:
        app_id = arc4_create(Receiver).created_app

        # these currently fail with a compilation error
        # tup_native = True, True
        # abi_call(Receiver.receive_bools, tup_native, app_id=app_id)

        #arr_arc4 = Array(Bool(True), Bool(True))
        #abi_call(Receiver.receive_bools, arr_arc4.freeze(), app_id=app_id)

        #arr_nat = Array(True, True)
        #abi_call(Receiver.receive_bools, arr_nat.freeze(), app_id=app_id)

        # this fails on execution
        tup_arc4 = Bool(True), Bool(True)
        abi_call(Receiver.receive_bools, tup_arc4, app_id=app_id)

        # delete app so we don't need to worry about MBR in test suite
        abi_call(Receiver.delete, app_id=app_id)
