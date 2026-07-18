import algokit_utils as au
from algokit_common import public_key_from_address

from puya.utils import sha512_256_hash
from tests import EXAMPLES_DIR
from tests.utils import arc4_encode
from tests.utils.deployer import Deployer

_EVENTS = EXAMPLES_DIR / "devportal" / "events"


def _event_log(signature: str, *values: object) -> bytes:
    """Expected ARC-28 log: 4-byte selector (SHA-512/256 of the event
    signature) followed by the ARC-4 tuple encoding of the values."""
    selector = sha512_256_hash(signature.encode("utf8"))[:4]
    arg_types = signature[signature.index("(") :]
    return selector + arc4_encode(arg_types, values)


def test_swap_emit_struct_emits_arc28_events(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = deployer.create((_EVENTS, "SwapContract")).client
    result = client.send.call(
        au.AppClientMethodCallParams(
            method="swap_emit_struct",
            args=[account.addr, account.addr, 100, 90],
        )
    )
    # two arc4.emit calls -> two ARC-28 event logs
    pk = public_key_from_address(account.addr)
    assert result.confirmation.logs == [
        _event_log("Swapped(address,address,uint64,uint64)", pk, pk, 100, 90),
        # the native struct is emitted using the equivalent ARC-4 types
        _event_log("NativeStruct(uint64,string)", 100, "payment received"),
    ]


def test_transfer_emit_signature(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = deployer.create((_EVENTS, "TransferContract")).client
    result = client.send.call(
        au.AppClientMethodCallParams(
            method="transfer_emit_signature",
            args=[account.addr, account.addr, 50],
        )
    )
    pk = public_key_from_address(account.addr)
    assert result.confirmation.logs == [_event_log("Transfer(address,address,uint64)", pk, pk, 50)]


def test_mint_emit_by_name(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = deployer.create((_EVENTS, "MintContract")).client
    result = client.send.call(
        au.AppClientMethodCallParams(
            method="mint_emit_by_name",
            args=[account.addr, 25],
        )
    )
    # the signature (and thus the selector) is inferred from the arg types
    pk = public_key_from_address(account.addr)
    assert result.confirmation.logs == [_event_log("Mint(address,uint64)", pk, 25)]
