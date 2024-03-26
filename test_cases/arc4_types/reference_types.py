from algopy import Contract, arc4, op


class Arc4RefTypesContract(Contract):
    def approval_program(self) -> bool:
        # When creating an address from an account no need to check the length as we assume the
        # Account is valid
        sender_address = arc4.Address(op.Txn.sender)
        assert sender_address == op.Txn.sender
        # When creating an address from bytes, we check the length is 32 as we don't know the
        # source of the bytes
        checked_address = arc4.Address(op.Txn.sender.bytes)
        # When using from_bytes, no validation is performed as per all implementations of
        # from_bytes
        unchecked_address = arc4.Address.from_bytes(op.Txn.sender.bytes)
        assert sender_address == checked_address and checked_address == unchecked_address

        assert arc4.Address() == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
        return True

    def clear_state_program(self) -> bool:
        return True
