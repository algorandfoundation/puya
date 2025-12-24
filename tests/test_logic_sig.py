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

from puya.compilation_artifacts import CompiledLogicSig
from puyapy.options import PuyaPyOptions
from tests import TEST_CASES_DIR
from tests.utils.compile import compile_src_from_options

pytestmark = pytest.mark.localnet


def compile_logic_sig(
    src_path: Path,
    *,
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
    (logic_sig,) = result.teal
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
