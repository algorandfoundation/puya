from puyapy import Bytes, UInt64, arc4


class TestContract(arc4.ARC4Contract):
    @arc4.abimethod(allow_actions=["NoOp"], create=True)
    def create(
        self,
        bool_param: bool,
        uint64_param: UInt64,
        bytes_param: Bytes,
        tuple_param: tuple[bool, UInt64, Bytes],
    ) -> tuple[bool, UInt64, Bytes]:
        result = (bool_param, uint64_param, bytes_param)
        assert result == tuple_param
        return result
