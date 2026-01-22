from algopy import Account, Contract, log, op


class AddressConstantContract(Contract):
    def approval_program(self) -> bool:
        some_address = Account()
        assert not some_address
        some_address = Account(SOME_ADDRESS)
        assert some_address
        some_address = Account.from_bytes(some_address.bytes)
        some_address = Account(some_address.bytes)

        sender = op.Txn.sender
        sender_bytes = sender.bytes
        log(sender_bytes)
        is_some_address = op.Txn.sender == some_address

        return not is_some_address

    def clear_state_program(self) -> bool:
        return True


SOME_ADDRESS = "VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA"
