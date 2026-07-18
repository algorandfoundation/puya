from algopy import Account, ARC4Contract, TemplateVar, UInt64, arc4


# example: ACCOUNT_REFERENCE_EXAMPLE
class ReferenceAccount(ARC4Contract):
    """
    Demonstrates accessing properties of an external account. The account is
    either baked into the program via a template variable or supplied as a
    method argument. Either way, it must be present in the transaction's
    reference array at call time (the AlgoKit client typically handles this
    automatically).
    """

    @arc4.abimethod
    def get_account_balance(self) -> UInt64:
        """Read the balance of a well-known account, baked into the program
        when it is compiled/deployed (`TMPL_KNOWN_ACCOUNT`)."""
        account = TemplateVar[Account]("KNOWN_ACCOUNT")
        return account.balance

    @arc4.abimethod
    def get_account_balance_with_arg(self, account: Account) -> UInt64:
        """Same lookup, but with a caller-supplied account reference."""
        return account.balance


# example: ACCOUNT_REFERENCE_EXAMPLE
