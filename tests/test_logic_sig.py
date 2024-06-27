from pathlib import Path

import algokit_utils
import algosdk
import pytest
from algokit_utils import TransferAssetParameters
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    LogicSigTransactionSigner,
    TransactionWithSigner,
)
from algosdk.transaction import AssetTransferTxn, LogicSigAccount, LogicSigTransaction, PaymentTxn
from algosdk.v2client.algod import AlgodClient
from puya.models import CompiledLogicSig
from puya.options import PuyaOptions

from tests import TEST_CASES_DIR
from tests.utils import compile_src_from_options

pytestmark = pytest.mark.localnet


def compile_logic_sig(
    src_path: Path,
    *,
    optimization_level: int = 1,
    debug_level: int = 2,
    template_variables: dict[str, int | bytes] | None = None,
) -> bytes:
    result = compile_src_from_options(
        PuyaOptions(
            paths=(src_path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
            output_arc32=False,
            output_teal=False,
            output_bytecode=True,
            out_dir=Path("out"),
            template_vars_override=template_variables or {},
        )
    )
    (logic_sig,) = (a for file in result.teal.values() for a in file)
    assert isinstance(
        logic_sig, CompiledLogicSig
    ), "Compilation artifact must be a logic signature"
    bytecode = logic_sig.program.bytecode
    assert bytecode is not None
    return bytecode


def test_logic_sig(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    logic_sig_prog = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "always_allow.py",
    )
    logic_sig = LogicSigAccount(
        program=logic_sig_prog,
    )
    algokit_utils.transfer(
        client=algod_client,
        parameters=algokit_utils.TransferParameters(
            from_account=account,
            to_address=logic_sig.address(),
            micro_algos=2_000_000,
        ),
    )

    paytxn = PaymentTxn(
        sender=logic_sig.address(),
        sp=algod_client.suggested_params(),
        receiver=account.address,
        amt=1_000_000,
    )
    signed_paytxn = LogicSigTransaction(
        transaction=paytxn,
        lsig=logic_sig.lsig,
    )
    algod_client.send_transaction(txn=signed_paytxn)

    delegated_logic_sig = LogicSigAccount(program=logic_sig_prog)
    delegated_logic_sig.sign(account.private_key)

    paytxn = PaymentTxn(
        sender=account.address,
        sp=algod_client.suggested_params(),
        receiver=logic_sig.address(),
        amt=500_000,
    )
    signed_paytxn = algosdk.transaction.LogicSigTransaction(
        transaction=paytxn,
        lsig=delegated_logic_sig.lsig,
    )
    algod_client.send_transaction(txn=signed_paytxn)


@pytest.fixture()
def account_2(algod_client: AlgodClient) -> algokit_utils.Account:
    v = algosdk.account.generate_account()
    account = algokit_utils.Account(private_key=v[0], address=v[1])
    algokit_utils.transfer(
        client=algod_client,
        parameters=algokit_utils.TransferParameters(
            from_account=algokit_utils.get_localnet_default_account(algod_client),
            to_address=account.address,
            micro_algos=500_000_000,
        ),
    )
    return account


def test_pre_approved_sale(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
    account_2: algokit_utils.Account,
    asset_a: int,
) -> None:
    algokit_utils.transfer_asset(
        client=algod_client,
        parameters=TransferAssetParameters(
            from_account=account_2,
            to_address=account_2.address,
            asset_id=asset_a,
            amount=0,  # Opt in
        ),
    )
    logic_sig_prog = compile_logic_sig(
        TEST_CASES_DIR / "logic_signature" / "signature.py",
        template_variables={
            "TMPL_SELLER": algosdk.encoding.decode_address(account.address),
            "TMPL_PRICE": 10_000_000,
            "TMPL_ASSET_ID": asset_a,
        },
    )
    logic_sig = LogicSigAccount(program=logic_sig_prog)
    logic_sig.sign(account.private_key)

    # Payment for the asset
    paytxn = PaymentTxn(
        sender=account_2.address,
        sp=algod_client.suggested_params(),
        receiver=account.address,
        amt=10_000_000,
    )

    # Transfer the asset
    axfertxn = AssetTransferTxn(
        sender=account.address,
        sp=algod_client.suggested_params(),
        receiver=account_2.address,
        amt=1,
        index=asset_a,
    )

    atc = AtomicTransactionComposer()

    atc.add_transaction(TransactionWithSigner(txn=paytxn, signer=account_2.signer))
    atc.add_transaction(
        TransactionWithSigner(txn=axfertxn, signer=LogicSigTransactionSigner(logic_sig))
    )

    atc.execute(algod_client, wait_rounds=5)
