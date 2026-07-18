from algopy import (
    ARC4Contract,
    Bytes,
    GlobalState,
    StateTotals,
    Txn,
    UInt64,
    arc4,
    op,
    urange,
)


# example: CONTRACT_NAME
class ContractWithCustomName(ARC4Contract, name="OnChainName"):
    """
    `name=` on the class kwargs serves two purposes:
      * It overrides the output TEAL file name when multiple non-abstract
        contracts share a source file.
      * For `ARC4Contract` subclasses, it sets the contract name in the
        published ARC-32 application.json (and ARC-56), decoupling the
        on-chain identity from the Python class name.

    Useful for renaming the implementation class without breaking client
    code that pins to the published name.
    """

    @arc4.abimethod
    def hello(self) -> arc4.String:
        return arc4.String("hello")


# example: CONTRACT_NAME


# example: CONTRACT_STATE_TOTALS
class ContractWithStateReservation(
    ARC4Contract,
    state_totals=StateTotals(global_uints=16, global_bytes=8, local_uints=4),
):
    """
    `state_totals=` declares the total state slots the application requires,
    overriding the automatic calculation from `self.` declarations.

    Required when:
      * The contract reads or writes state via dynamic keys (`op.AppGlobal.put(...)`
        etc.) that puya can't see by inspecting `self.` assignments.
      * You want to reserve extra slots for future upgrades. However, the AVM
        now does allow updates to state totals after creation.
    """

    def __init__(self) -> None:
        # Puya sees these two `self.` assignments and would auto-compute
        # `global_uints=1`, `global_bytes=1`. The explicit `state_totals=`
        # above reserves 16 + 8 instead, leaving room for upgrades.
        self.counter = GlobalState(UInt64(0))
        self.label = GlobalState(Bytes(b""))

    @arc4.abimethod
    def increment(self) -> UInt64:
        self.counter.value += 1
        return self.counter.value


# example: CONTRACT_STATE_TOTALS


# example: CONTRACT_SCRATCH_SLOTS
class ContractWithScratchReservation(
    ARC4Contract,
    # `urange(200, 256)` reserves slots 200..255 for non-puya use (e.g.
    # `op.Scratch.store`, `op.Scratch.load`, and ReferenceArray usage).
    scratch_slots=urange(200, 256),
):
    """
    `scratch_slots=` reserves AVM scratch slots so puya won't try to use
    them for compiler-managed values. Pass a `urange`, a tuple of ints, or
    a list of ints/uranges.
    """

    @arc4.abimethod
    def echo(self, x: UInt64) -> UInt64:
        # write to the reserved slots 200..255 directly; puya will avoid
        # internally placing any values there under any circumstance
        for i in urange(200, 256):
            op.Scratch.store(i, x)
        return x


# example: CONTRACT_SCRATCH_SLOTS


# example: CONTRACT_AVM_VERSION
class ContractWithAvmVersion(ARC4Contract, avm_version=12):
    """
    `avm_version=` pins the contract to a specific AVM version. The compiler
    allows opcodes available in that version, rejects ones introduced later,
    and the produced bytecode declares the version at the top.
    Using the default (latest) version is recommended, use this only if needed.
    """

    @arc4.abimethod
    def caller_pin(self) -> UInt64:
        """`Txn.reject_version` is a transaction field introduced in
        AVM 12, so reading it compiles because of the `avm_version=12`
        declaration above; on an older target version the compiler rejects
        it."""
        return Txn.reject_version


# example: CONTRACT_AVM_VERSION
