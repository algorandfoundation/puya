from algopy import Account, ARC4Contract, String, Struct, UInt64, arc4


# example: ARC28_EVENT_STRUCT
class Swapped(arc4.Struct):
    """
    A typed ARC-28 event. The signature emitted on-chain is derived from the
    class name and field types: `Swapped(address,address,uint64,uint64)`.

    The first 4 bytes of the SHA-512/256 of that signature form the event's
    selector; the rest of the log payload is the ARC-4 encoding of the fields.
    Indexers can subscribe to the selector to pick up only this event.
    """

    sender: arc4.Address
    receiver: arc4.Address
    in_amount: arc4.UInt64
    out_amount: arc4.UInt64


class NativeStruct(Struct):
    """
    Native structs can also be directly emitted.
    In this case the equivalent arc4 representation
    of the native types will be used.
    """

    count: UInt64
    message: String


class SwapContract(ARC4Contract):
    @arc4.abimethod
    def swap_emit_struct(
        self, sender: Account, receiver: Account, in_amount: UInt64, out_amount: UInt64
    ) -> None:
        """Emit by passing the Struct instance (recommended form)."""
        event = Swapped(
            sender=arc4.Address(sender),
            receiver=arc4.Address(receiver),
            in_amount=arc4.UInt64(in_amount),
            out_amount=arc4.UInt64(out_amount),
        )
        arc4.emit(event)

        native_event = NativeStruct(count=in_amount, message=String("payment received"))
        arc4.emit(native_event)


# example: ARC28_EVENT_STRUCT


# example: ARC28_EVENT_BY_SIGNATURE
class TransferContract(ARC4Contract):
    @arc4.abimethod
    def transfer_emit_signature(self, sender: Account, receiver: Account, amount: UInt64) -> None:
        """
        Emit using an explicit ARC-28 signature string. The signature must
        match the runtime arg types; puya type-checks the args against it.
        """
        arc4.emit(
            "Transfer(address,address,uint64)",
            arc4.Address(sender),
            arc4.Address(receiver),
            arc4.UInt64(amount),
        )


# example: ARC28_EVENT_BY_SIGNATURE


# example: ARC28_EVENT_BY_NAME
class MintContract(ARC4Contract):
    @arc4.abimethod
    def mint_emit_by_name(self, recipient: Account, amount: UInt64) -> None:
        """
        Emit using only an event *name*; the signature is inferred from the
        types of the following args. Equivalent to the by-signature form when
        the inferred shape matches what off-chain consumers expect.

        Be aware that the inferred ARC-4 types are picked from the runtime arg
        types, so passing native types (e.g. `UInt64`) results in a different
        signature than passing the ARC-4 equivalent (`arc4.UInt64`). Prefer
        the explicit signature form when the shape must be exact.
        """
        arc4.emit("Mint", arc4.Address(recipient), arc4.UInt64(amount))


# example: ARC28_EVENT_BY_NAME
