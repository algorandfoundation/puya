from collections.abc import Mapping
from pathlib import Path

import pytest
from algokit_common import public_key_from_address
from algokit_utils import (
    AddressWithSigners,
    AlgoAmount,
    AlgorandClient,
    AssetTransferParams,
    LogicSigAccount,
    PaymentParams,
)
from algokit_utils.transactions.transaction_composer import TransactionComposerError

from puya.compilation_artifacts import CompiledLogicSig
from puyapy.options import PuyaPyOptions
from tests import TEST_CASES_DIR
from tests.utils.compile import compile_src_from_options

pytestmark = pytest.mark.localnet


def compile_logic_sig(
    src_path: Path,
    *,
    name: str | None = None,
    optimization_level: int = 1,
    debug_level: int = 2,
    template_variables: Mapping[str, int | bytes] | None = None,
) -> bytes:
    result = compile_src_from_options(
        PuyaPyOptions(
            paths=(src_path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
            output_bytecode=True,
            cli_template_definitions=template_variables or {},
        )
    )
    if name is None:
        (logic_sig,) = result.teal
    else:
        (logic_sig,) = (
            t for t in result.teal if isinstance(t, CompiledLogicSig) if t.metadata.name == name
        )
    assert isinstance(
        logic_sig, CompiledLogicSig
    ), "Compilation artifact must be a logic signature"
    bytecode = logic_sig.program.bytecode
    assert bytecode is not None
    return bytecode


def test_logic_sig(localnet: AlgorandClient, account: AddressWithSigners) -> None:
    logic_sig_prog = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "always_allow.py",
    )
    logic_sig = LogicSigAccount(logic=logic_sig_prog)
    localnet.account.set_signer(logic_sig.addr, logic_sig.signer)
    localnet.send.payment(
        PaymentParams(
            sender=account.addr,
            receiver=logic_sig.addr,
            amount=AlgoAmount.from_algo(2),
        )
    )

    result = localnet.send.payment(
        PaymentParams(
            sender=logic_sig.addr,
            receiver=account.addr,
            amount=AlgoAmount.from_algo(1),
        )
    )
    assert result.confirmation.confirmed_round is not None

    delegated_logic_sig = LogicSigAccount(logic=logic_sig_prog).delegated_account(account.addr)
    delegated_logic_sig.sign_for_delegation(account)

    localnet.account.set_signer_from_account(delegated_logic_sig)

    result = localnet.send.payment(
        PaymentParams(
            sender=account.addr,
            receiver=delegated_logic_sig.addr,
            amount=AlgoAmount.from_micro_algo(500_000),
        ),
    )
    assert result.confirmation.confirmed_round is not None


@pytest.fixture
def account_2(localnet: AlgorandClient, account: AddressWithSigners) -> AddressWithSigners:
    new_account = localnet.account.random()
    localnet.send.payment(
        PaymentParams(
            sender=account.addr,
            receiver=new_account.addr,
            amount=AlgoAmount.from_algo(500),
        )
    )
    return new_account


def test_pre_approved_sale(
    localnet: AlgorandClient,
    account: AddressWithSigners,
    account_2: AddressWithSigners,
    asset_a: int,
) -> None:
    localnet.send.asset_transfer(
        AssetTransferParams(
            sender=account_2.addr,
            receiver=account_2.addr,
            asset_id=asset_a,
            amount=0,  # Opt in
        )
    )

    logic_sig_prog = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "signature.py",
        template_variables={
            "SELLER": public_key_from_address(account.addr),
            "PRICE": 10_000_000,
            "ASSET_ID": asset_a,
        },
    )
    logic_sig = LogicSigAccount(logic=logic_sig_prog).delegated_account(account.addr)
    logic_sig.sign_for_delegation(account)

    localnet.account.set_signer_from_account(account_2, logic_sig)
    result = (
        localnet.new_group()
        .add_payment(
            PaymentParams(
                sender=account_2.addr,
                receiver=account.addr,
                amount=AlgoAmount.from_algo(10),
            )
        )
        .add_asset_transfer(
            AssetTransferParams(
                sender=account.addr,
                receiver=account_2.addr,
                amount=1,
                asset_id=asset_a,
            )
        )
        .send()
    )

    assert result.confirmations[1].confirmed_round is not None


def _execute_logic_sig(
    localnet: AlgorandClient,
    funder: AddressWithSigners,
    bytecode: bytes,
    args: list[bytes],
) -> None:
    logic_sig = LogicSigAccount(logic=bytecode, args=args)
    localnet.account.set_signer(logic_sig.addr, logic_sig.signer)
    localnet.send.payment(
        PaymentParams(
            sender=funder.addr,
            receiver=logic_sig.addr,
            amount=AlgoAmount.from_algo(2),
        )
    )
    result = localnet.send.payment(
        PaymentParams(
            sender=logic_sig.addr,
            receiver=funder.addr,
            amount=AlgoAmount.from_algo(1),
        )
    )
    assert result.confirmation.confirmed_round is not None


_VALID_OVERWRITE_STRUCT = b"\x05\x80"
# valid OverwriteStruct(value=5, dont_overwrite_me=True), size of 2 bytes

_INVALID_OVERWRITE_STRUCT = b"\x05\x00\x80"
# Invalid OverwriteStruct, size of 3 bytes.
# This will corrupt the bool field if it goes through (make it false).
# Should not pass encoding validation, and should fly under the radar in `unsafe_disabled`.


def _build_complex_args(*, overwrite_struct: bytes = _VALID_OVERWRITE_STRUCT) -> list[bytes]:
    simple_struct = (1).to_bytes(8, "big") + (2).to_bytes(8, "big")
    nested_struct = b"\x03" + simple_struct
    return [
        (42).to_bytes(8, "big"),  # arg0:  UInt64
        b"test",  # arg1:  Bytes
        (999).to_bytes(2, "big"),  # arg2:  BigUInt
        b"world",  # arg3:  String
        (1).to_bytes(8, "big"),  # arg4:  bool = True
        b"\x05",  # arg5:  arc4.UInt8
        (100).to_bytes(8, "big"),  # arg6:  arc4.UInt64
        (1000).to_bytes(16, "big"),  # arg7:  arc4.UInt128
        b"\x00" * 32,  # arg8:  arc4.Address
        b"\x00",  # arg9:  arc4.Bool = False
        b"\x00\x05hello",  # arg10: arc4.String
        b"\x00\x03abc",  # arg11: arc4.DynamicBytes
        b"\x01\x02\x03\x04",  # arg12: arc4.StaticArray[Byte, 4]
        simple_struct,  # arg13: SimpleStruct
        nested_struct,  # arg14: NestedStruct
        b"\x05" + (2).to_bytes(8, "big"),  # arg15: arc4.Tuple[UInt8, UInt64]
        b"\x0a",  # arg16[0]: NamedTuple.a (arc4.UInt8)
        (20).to_bytes(8, "big"),  # arg16[1]: NamedTuple.b (arc4.UInt64)
        (50).to_bytes(8, "big"),  # arg17[0]: tuple UInt64
        b"tuple_bytes",  # arg17[1]: tuple Bytes
        (60).to_bytes(8, "big"),  # arg18[0]: tuple UInt64
        b"nested",  # arg18[1][0]: nested tuple Bytes
        (70).to_bytes(8, "big"),  # arg18[1][1]: nested tuple UInt64
        overwrite_struct,  # arg19: OverwriteStruct
        b"\x00\x03\x01\x02\x03",  # arg20: arc4.DynamicArray[UInt8] = [1, 2, 3]
    ]


def test_logic_sig_args_simple(localnet: AlgorandClient, account: AddressWithSigners) -> None:
    bytecode = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "lsig_args_simple.py",
    )
    simple_args = [
        (42).to_bytes(8, "big"),  # arg0: UInt64
        b"hello",  # arg1: Bytes
        (1).to_bytes(8, "big"),  # arg2: bool = True
    ]
    _execute_logic_sig(localnet, account, bytecode, simple_args)


def test_logic_sig_args_complex(localnet: AlgorandClient, account: AddressWithSigners) -> None:
    bytecode = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "lsig_args_complex.py",
        name="args_complex",
    )
    _execute_logic_sig(localnet, account, bytecode, _build_complex_args())


def test_logic_sig_args_complex_unsafe_disabled(
    localnet: AlgorandClient, account: AddressWithSigners
) -> None:
    bytecode = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "lsig_args_complex.py",
        name="args_complex_no_validation",
    )
    _execute_logic_sig(localnet, account, bytecode, _build_complex_args())


def test_logic_sig_args_complex_invalid_encoding(
    localnet: AlgorandClient, account: AddressWithSigners
) -> None:
    bytecode = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "lsig_args_complex.py",
        name="args_complex",
    )

    # validated logicsig SHOULD reject oversized OverwriteStruct encoding
    # note utils throws a TransactionComposerError for lsigs, not a LogicError
    # also b.c. we lack a source map, the full error just gives the PC and not much more
    with pytest.raises(TransactionComposerError, match="rejected by logic err=assert failed"):
        _execute_logic_sig(
            localnet,
            account,
            bytecode,
            _build_complex_args(overwrite_struct=_INVALID_OVERWRITE_STRUCT),
        )


def test_logic_sig_args_complex_invalid_encoding_unsafe_disabled(
    localnet: AlgorandClient, account: AddressWithSigners
) -> None:
    bytecode = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "lsig_args_complex.py",
        name="args_complex_no_validation",
    )
    # oversized encoding accepted: bool is "corrupted" but logicsig still succeeds
    _execute_logic_sig(
        localnet,
        account,
        bytecode,
        _build_complex_args(overwrite_struct=_INVALID_OVERWRITE_STRUCT),
    )
