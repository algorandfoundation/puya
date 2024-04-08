from algopy import Contract, Global, Txn, arc4

SOME_ADDRESS = "VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA"


class Arc4AddressContract(Contract):
    def approval_program(self) -> bool:
        address = arc4.Address(Txn.sender)
        assert address == Txn.sender
        assert address.length == 32
        assert address.native == Txn.sender

        zero_address = arc4.Address(Global.zero_address.bytes)
        assert zero_address.bytes == Global.zero_address.bytes

        some_address = arc4.Address(SOME_ADDRESS)
        assert some_address == SOME_ADDRESS

        some_address[0] = arc4.Byte(123)
        assert some_address != SOME_ADDRESS
        return True

    def clear_state_program(self) -> bool:
        return True
