from algopy import ARC4Contract, Bytes, UInt64, arc4, log


class MyContract(ARC4Contract):
    @arc4.abimethod
    def call_other(self) -> None:
        arc4.abi_call(Other.call_me, Bytes(), app_id=1234)


class Other(ARC4Contract):
    @arc4.abimethod
    def call_me(self, value: UInt64) -> None:
        log(value)
