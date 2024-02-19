import puyapy


class MyContract(puyapy.Contract):
    def approval_program(self) -> bool:
        self.case_one = puyapy.UInt64(1)
        self.case_two = puyapy.UInt64(2)
        self.match_uint64()
        self.match_biguint()
        self.match_bytes()
        self.match_address()
        self.match_attributes()
        self.match_bools()
        return True

    @puyapy.subroutine
    def match_uint64(self) -> None:
        n = puyapy.op.Txn.num_app_args
        match n:
            case puyapy.UInt64(0):
                hello = puyapy.Bytes(b"Hello")
                puyapy.log(hello)
            case puyapy.UInt64(10):
                hello = puyapy.Bytes(b"Hello There")
                puyapy.log(hello)

    @puyapy.subroutine
    def match_bytes(self) -> None:
        n = puyapy.op.Txn.application_args(0)
        match n:
            case puyapy.Bytes(b""):
                hello = puyapy.Bytes(b"Hello bytes")
                puyapy.log(hello)
            case puyapy.Bytes(b"10"):
                hello = puyapy.Bytes(b"Hello There bytes")
                puyapy.log(hello)

    @puyapy.subroutine
    def match_biguint(self) -> None:
        n = puyapy.op.Txn.num_app_args * puyapy.BigUInt(10)
        match n:
            case puyapy.BigUInt(0):
                hello = puyapy.Bytes(b"Hello biguint")
                puyapy.log(hello)
            case puyapy.BigUInt(10):
                hello = puyapy.Bytes(b"Hello There biguint")
                puyapy.log(hello)

    @puyapy.subroutine
    def match_address(self) -> None:
        n = puyapy.op.Txn.sender
        match n:
            case puyapy.Account("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"):
                hello = puyapy.Bytes(b"Hello address")
                puyapy.log(hello)
            case puyapy.Account("VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA"):
                hello = puyapy.Bytes(b"Hello There address")
                puyapy.log(hello)

    @puyapy.subroutine
    def match_attributes(self) -> None:
        n = puyapy.op.Txn.num_app_args
        match n:
            case self.case_one:
                hello = puyapy.Bytes(b"Hello one")
                puyapy.log(hello)
            case self.case_two:
                hello = puyapy.Bytes(b"Hello two")
                puyapy.log(hello)
            case _:
                hello = puyapy.Bytes(b"Hello default")
                puyapy.log(hello)

    @puyapy.subroutine
    def match_bools(self) -> None:
        n = puyapy.op.Txn.num_app_args > 0
        match n:
            case True:
                hello = puyapy.Bytes(b"Hello True")
                puyapy.log(hello)
            case False:
                hello = puyapy.Bytes(b"Hello False")
                puyapy.log(hello)

    def clear_state_program(self) -> bool:
        return True
