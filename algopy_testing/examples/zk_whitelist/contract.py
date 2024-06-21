# Taken from https://github.com/giuliop/whitelist-example-algoplonk

import typing

import algopy as py
from algopy import (
    Account,
    Global,
    LocalState,
    TemplateVar,
    Txn,
    UInt64,
    itxn,
    subroutine,
)
from algopy.arc4 import (
    Address,
    Bool,
    Byte,
    DynamicArray,
    StaticArray,
    String,
    abimethod,
    arc4_signature,
)

Bytes32: typing.TypeAlias = StaticArray[Byte, typing.Literal[32]]

curve_mod = 21888242871839275222246405745257275088548364400416034343698204186575808495617

verifier_budget = 145000


class ZkWhitelistContract(py.ARC4Contract):
    def __init__(self) -> None:
        self.whitelist = LocalState(bool)

    @abimethod(create="require")
    def create(self, name: String) -> None:
        """Create the application"""

        self.app_name = name

    @abimethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def update(self) -> None:
        """Update the application if it is mutable (manager only)"""
        assert Global.creator_address == Txn.sender

    @abimethod(allow_actions=["OptIn", "CloseOut"])
    def opt_in_or_out(self) -> None:
        """Opt in or out of the application"""
        return

    @abimethod
    def add_address_to_whitelist(self, address: Bytes32, proof: DynamicArray[Bytes32]) -> String:
        """Add caller to the whitelist if the zk proof is valid.
        On success, will return an empty string. Otherwise, will return an error
        message."""

        py.ensure_budget(verifier_budget, fee_source=py.OpUpFeeSource.GroupCredit)

        # The verifier expects public inputs to be in the curve field, but an
        # Algorand address might represent a number larger than the field
        # modulus, so to be safe we take the address modulo the field modulus
        address_mod = Bytes32.from_bytes((py.BigUInt.from_bytes(address.bytes) % curve_mod).bytes)

        # Verify the proof by calling the deposit verifier app
        verified = verify_proof(
            TemplateVar[UInt64]("VERIFIER_APP_ID"), proof, DynamicArray(address_mod.copy())
        )
        if not verified:
            return String("Proof verification failed")

        # if successful, add the sender to the whitelist by setting local state
        account = Account.from_bytes(address.bytes)
        if Txn.sender != account:
            return String("Sender address does not match authorized address")

        self.whitelist[account] = True
        return String("")

    @abimethod
    def is_on_whitelist(self, address: Address) -> Bool:
        """Check if an address is on the whitelist"""
        account = address.native
        opted_in = account.is_opted_in(Global.current_application_id)
        if not opted_in:
            return Bool(False)  # noqa: FBT003
        whitelisted = self.whitelist.get(account, False)
        return Bool(whitelisted)


@subroutine
def verify_proof(
    app_id: UInt64, proof: DynamicArray[Bytes32], public_inputs: DynamicArray[Bytes32]
) -> Bool:
    """Verify a proof using the verifier app."""
    verified = (
        itxn.ApplicationCall(
            app_id=app_id,
            fee=0,
            app_args=(
                arc4_signature("verify(byte[32][],byte[32][])bool"),
                proof.copy(),
                public_inputs.copy(),
            ),
            on_completion=py.OnCompleteAction.NoOp,
        )
        .submit()
        .last_log
    )
    return Bool.from_log(verified)
