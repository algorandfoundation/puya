import algopy


class MyContract(algopy.Contract):
    def approval_program(self) -> bool:
        self.case_one = algopy.UInt64(1)
        self.case_two = algopy.UInt64(2)
        self.match_uint64()
        self.match_biguint()
        self.match_bytes()
        self.match_address()
        self.match_attributes()
        self.match_bools()
        return True

    @algopy.subroutine
    def match_uint64(self) -> None:
        n = algopy.op.Txn.num_app_args
        match n:
            case algopy.UInt64(0):
                hello = algopy.Bytes(b"Hello")
                algopy.log(hello)
            case algopy.UInt64(10):
                hello = algopy.Bytes(b"Hello There")
                algopy.log(hello)

    @algopy.subroutine
    def match_bytes(self) -> None:
        n = algopy.op.Txn.application_args(0)
        match n:
            case algopy.Bytes(b""):
                hello = algopy.Bytes(b"Hello bytes")
                algopy.log(hello)
            case algopy.Bytes(b"10"):
                hello = algopy.Bytes(b"Hello There bytes")
                algopy.log(hello)

    @algopy.subroutine
    def match_biguint(self) -> None:
        n = algopy.op.Txn.num_app_args * algopy.BigUInt(10)
        match n:
            case algopy.BigUInt(0):
                hello = algopy.Bytes(b"Hello biguint")
                algopy.log(hello)
            case algopy.BigUInt(10):
                hello = algopy.Bytes(b"Hello There biguint")
                algopy.log(hello)

    @algopy.subroutine
    def match_address(self) -> None:
        n = algopy.op.Txn.sender
        match n:
            case algopy.Account("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"):
                hello = algopy.Bytes(b"Hello address")
                algopy.log(hello)
            case algopy.Account("VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA"):
                hello = algopy.Bytes(b"Hello There address")
                algopy.log(hello)

    @algopy.subroutine
    def match_attributes(self) -> None:
        n = algopy.op.Txn.num_app_args
        match n:
            case self.case_one:
                hello = algopy.Bytes(b"Hello one")
                algopy.log(hello)
            case self.case_two:
                hello = algopy.Bytes(b"Hello two")
                algopy.log(hello)
            case _:
                hello = algopy.Bytes(b"Hello default")
                algopy.log(hello)

    @algopy.subroutine
    def match_bools(self) -> None:
        n = algopy.op.Txn.num_app_args > 0
        match n:
            case True:
                hello = algopy.Bytes(b"Hello True")
                algopy.log(hello)
            case False:
                hello = algopy.Bytes(b"Hello False")
                algopy.log(hello)

    def clear_state_program(self) -> bool:
        return True
