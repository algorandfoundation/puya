from algopy import Account, Contract, Transaction, log

SOME_ADDRESS = "VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA"


class AddressConstantContract(Contract):
    def approval_program(self) -> bool:
        some_address = Account(SOME_ADDRESS)
        some_address = Account.from_bytes(some_address.bytes)

        sender = Transaction.sender()
        sender_bytes = sender.bytes
        log(sender_bytes)
        is_some_address = Transaction.sender() == some_address

        return not is_some_address

    def clear_state_program(self) -> bool:
        return True
