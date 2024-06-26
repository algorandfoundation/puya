from algopy import BigUInt, Bytes, String, UInt64, arc4


class TestContract(arc4.ARC4Contract):
    @arc4.abimethod(allow_actions=["NoOp"], create="require")
    def create(
        self,
        bool_param: bool,
        uint64_param: UInt64,
        bytes_param: Bytes,
        biguint_param: BigUInt,
        string_param: String,
        tuple_param: tuple[bool, UInt64, Bytes, BigUInt, String],
    ) -> tuple[bool, UInt64, Bytes, BigUInt, String]:
        result = (bool_param, uint64_param, bytes_param, biguint_param, string_param)
        assert result == tuple_param
        return result

    @arc4.abimethod
    def tuple_of_arc4(
        self, args: tuple[arc4.UInt8, arc4.Address]
    ) -> tuple[arc4.UInt8, arc4.Address]:
        assert args[0].bytes.length == 1
        assert args[1].bytes.length == 32
        return args
