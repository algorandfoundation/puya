from algopy import ARC4Contract, TransactionType, Txn, gtxn, public, urange


class VerifierContract(ARC4Contract):
    @public
    def verify(self) -> None:
        for i in urange(Txn.group_index):
            txn = gtxn.Transaction(i)
            assert txn.type == TransactionType.Payment, "Txn must be pay"
