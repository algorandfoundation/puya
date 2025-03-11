import base64
import math
import random
from collections.abc import Sequence
from pathlib import Path

import algokit_utils
import algokit_utils.config
import algosdk
import pytest
from algokit_utils import ApplicationClient, LogicError, OnCompleteCallParametersDict
from algosdk import abi, constants, transaction
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    SimulateAtomicTransactionResponse,
    TransactionWithSigner,
)
from algosdk.transaction import OnComplete
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.models import SimulateRequest, SimulateTraceConfig
from nacl.signing import SigningKey

from puya.arc32 import create_arc32_json
from puya.compilation_artifacts import CompiledContract
from puyapy.options import PuyaPyOptions
from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.test_execution import decode_logs
from tests.utils import compile_src_from_options
from tests.utils.merkle_tree import MerkleTree, sha_256_raw

pytestmark = pytest.mark.localnet


def compile_arc32(
    src_path: Path,
    *,
    optimization_level: int = 1,
    debug_level: int = 2,
    file_name: str | None = None,
    disabled_optimizations: Sequence[str] = (),
) -> str:
    result = compile_src_from_options(
        PuyaPyOptions(
            paths=(src_path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
            disabled_optimizations=disabled_optimizations,
        )
    )
    if file_name is None:
        (contract,) = result.teal
    else:
        (contract,) = (
            t
            for t in result.teal
            if isinstance(t, CompiledContract)
            if (
                t.source_location
                and t.source_location.file
                and t.source_location.file.name == file_name
            )
        )

    assert isinstance(contract, CompiledContract), "Compilation artifact must be a contract"
    return create_arc32_json(
        contract.approval_program.teal_src,
        contract.clear_program.teal_src,
        contract.metadata,
    )


def token_balances(
    app_client: algokit_utils.ApplicationClient,
    account: algokit_utils.Account,
    pool_token: int,
    asset_a: int,
    asset_b: int,
) -> dict[str, dict[str, int] | int]:
    account_info = app_client.algod_client.account_info(account.address)
    assert isinstance(account_info, dict)

    account_balances = {}
    for asset in account_info["assets"]:
        if asset["asset-id"] == pool_token:
            account_balances["pool"] = asset["amount"]
        if asset["asset-id"] == asset_a:
            account_balances["asset_a"] = asset["amount"]
        if asset["asset-id"] == asset_b:
            account_balances["asset_b"] = asset["amount"]

    app_account_info = app_client.algod_client.account_info(app_client.app_address)
    assert isinstance(app_account_info, dict)

    app_balances = {}
    for asset in app_account_info["assets"]:
        if asset["asset-id"] == pool_token:
            app_balances["pool"] = asset["amount"]
        if asset["asset-id"] == asset_a:
            app_balances["asset_a"] = asset["amount"]
        if asset["asset-id"] == asset_b:
            app_balances["asset_b"] = asset["amount"]

    state = app_client.get_global_state()
    ratio = state["ratio"]
    assert isinstance(ratio, int)
    return {"account": account_balances, "app": app_balances, "ratio": ratio}


def test_amm(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
    asset_a: int,
    asset_b: int,
) -> None:
    example = EXAMPLES_DIR / "amm"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create
    create_response = app_client.create()
    assert create_response.confirmed_round

    pay_txn = TransactionWithSigner(
        transaction.PaymentTxn(
            sender=account.address,
            receiver=app_client.app_address,
            amt=int(1e7),
            sp=algod_client.suggested_params(),
        ),
        signer=account.signer,
    )
    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 4_000

    # bootstrap
    bootstrap_response = app_client.call(
        "bootstrap",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(suggested_params=sp),
        seed=pay_txn,
        a_asset=asset_a,
        b_asset=asset_b,
    )
    pool_token = bootstrap_response.return_value
    assert token_balances(app_client, account, pool_token, asset_a, asset_b) == {
        "account": {
            "asset_a": 10_000_000,
            "asset_b": 10_000_000,
        },
        "app": {
            "asset_a": 0,
            "asset_b": 0,
            "pool": 10_000_000_000,
        },
        "ratio": 0,
    }

    # pool_id should be newer than asset a + b
    assert pool_token > asset_a
    assert pool_token > asset_b

    # opt user into tokens
    # fund user account with assets a & b
    sp = algod_client.suggested_params()
    atc = AtomicTransactionComposer()
    atc.add_transaction(
        TransactionWithSigner(
            txn=transaction.AssetTransferTxn(account.address, sp, account.address, 0, asset_a),
            signer=account.signer,
        )
    )
    atc.add_transaction(
        TransactionWithSigner(
            txn=transaction.AssetTransferTxn(account.address, sp, account.address, 0, asset_b),
            signer=account.signer,
        )
    )
    atc.add_transaction(
        TransactionWithSigner(
            txn=transaction.AssetTransferTxn(account.address, sp, account.address, 0, pool_token),
            signer=account.signer,
        )
    )
    atc.execute(algod_client, wait_rounds=1)

    # mint
    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 3_000

    app_client.call(
        "mint",
        a_xfer=TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                account.address, sp, app_client.app_address, 10_000, asset_a
            ),
            signer=account.signer,
        ),
        b_xfer=TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                account.address, sp, app_client.app_address, 3000, asset_b
            ),
            signer=account.signer,
        ),
        transaction_parameters=algokit_utils.OnCompleteCallParameters(suggested_params=sp),
    )
    assert token_balances(app_client, account, pool_token, asset_a, asset_b) == {
        "account": {
            "asset_a": 9_990_000,
            "asset_b": 9_997_000,
            "pool": 4_477,
        },
        "app": {
            "asset_a": 10_000,
            "asset_b": 3_000,
            "pool": 9_999_995_523,
        },
        "ratio": 3_333,
    }

    app_client.call(
        "mint",
        a_xfer=TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                account.address, sp, app_client.app_address, 100_000, asset_a
            ),
            signer=account.signer,
        ),
        b_xfer=TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                account.address, sp, app_client.app_address, 1_000, asset_b
            ),
            signer=account.signer,
        ),
        transaction_parameters=algokit_utils.OnCompleteCallParameters(suggested_params=sp),
    )
    assert token_balances(app_client, account, pool_token, asset_a, asset_b) == {
        "account": {
            "asset_a": 9_890_000,
            "asset_b": 9_996_000,
            "pool": 5_967,
        },
        "app": {
            "asset_a": 110_000,
            "asset_b": 4_000,
            "pool": 9_999_994_033,
        },
        "ratio": 27_500,
    }

    # swap
    app_client.call(
        "swap",
        swap_xfer=TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                account.address, sp, app_client.app_address, 500, asset_a
            ),
            signer=account.signer,
        ),
    )
    assert token_balances(app_client, account, pool_token, asset_a, asset_b) == {
        "account": {
            "asset_a": 9_903_252,
            "asset_b": 9_996_000,
            "pool": 5_967,
        },
        "app": {
            "asset_a": 96_748,
            "asset_b": 4_000,
            "pool": 9_999_994_033,
        },
        "ratio": 24_187,
    }

    app_client.call(
        "swap",
        swap_xfer=TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                account.address, sp, app_client.app_address, 500, asset_b
            ),
            signer=account.signer,
        ),
    )
    assert token_balances(app_client, account, pool_token, asset_a, asset_b) == {
        "account": {
            "asset_a": 9_903_252,
            "asset_b": 9_995_523,
            "pool": 5_967,
        },
        "app": {
            "asset_a": 96_748,
            "asset_b": 4_477,
            "pool": 9_999_994_033,
        },
        "ratio": 21_610,
    }

    # burn
    app_client.call(
        "burn",
        pool_xfer=TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                account.address, sp, app_client.app_address, 100, pool_token
            ),
            signer=account.signer,
        ),
    )
    assert token_balances(app_client, account, pool_token, asset_a, asset_b) == {
        "account": {
            "asset_a": 9_904_929,
            "asset_b": 9_995_600,
            "pool": 5_867,
        },
        "app": {
            "asset_a": 95_071,
            "asset_b": 4_400,
            "pool": 9_999_994_133,
        },
        "ratio": 21_607,
    }


@pytest.fixture
def voter_account(algod_client: AlgodClient) -> algokit_utils.Account:
    v = algosdk.account.generate_account()
    voter_account = algokit_utils.Account(private_key=v[0], address=v[1])
    algokit_utils.transfer(
        client=algod_client,
        parameters=algokit_utils.TransferParameters(
            from_account=algokit_utils.get_localnet_default_account(algod_client),
            to_address=voter_account.address,
            micro_algos=10000000,
        ),
    )
    return voter_account


def suggested_params(
    *, algod_client: AlgodClient, fee: int | None = None, flat_fee: bool | None = None
) -> algosdk.transaction.SuggestedParams:
    sp = algod_client.suggested_params()

    if fee is not None:
        sp.fee = fee
    if flat_fee is not None:
        sp.flat_fee = flat_fee

    return sp


def payment_transaction(
    *,
    algod_client: AlgodClient,
    amount: int,
    receiver: str,
    sender: algokit_utils.Account,
    note: bytes | None = None,
) -> TransactionWithSigner:
    return TransactionWithSigner(
        txn=algosdk.transaction.PaymentTxn(
            sender=sender.address,
            receiver=receiver,
            amt=amount,
            note=note,
            sp=suggested_params(algod_client=algod_client),
        ),
        signer=sender.signer,
    )


def test_voting_app(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
    voter_account: algokit_utils.Account,
) -> None:
    creator_account = account

    private_key = SigningKey.generate()

    example = EXAMPLES_DIR / "voting"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=creator_account)

    quorum = math.ceil(random.randint(1, 9) * 1000)
    question_counts = [1] * 10

    health = algod_client.status()
    assert isinstance(health, dict)
    response = algod_client.block_info(health["last-round"])
    assert isinstance(response, dict)
    block = response["block"]
    block_ts = block["ts"]
    app_client.create(
        "create",
        vote_id="1",
        metadata_ipfs_cid="cid",
        start_time=int(block_ts),
        end_time=int(block_ts) + 1000,
        quorum=quorum,
        snapshot_public_key=private_key.verify_key.encode(),
        nft_image_url="ipfs://cid",
        option_counts=question_counts,
    )

    app_client.call(
        call_abi_method="bootstrap",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(boxes=[(0, "V")]),
        fund_min_bal_req=payment_transaction(
            algod_client=algod_client,
            amount=(100000 * 2) + 1000 + 2500 + 400 * (1 + 8 * 10),
            sender=creator_account,
            note=b"Bootstrap payment",
            receiver=app_client.app_address,
        ),
    )

    def get_account_signature(voter_public_key: bytes) -> bytes:
        signed = private_key.sign(voter_public_key)
        return signed.signature

    pre_conditions = app_client.call(
        call_abi_method="get_preconditions",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            sender=voter_account.address,
            signer=voter_account.signer,
            boxes=[(0, voter_account.public_key)],
            suggested_params=suggested_params(algod_client=algod_client, fee=4000),
        ),
        signature=get_account_signature(voter_account.public_key),
    )
    (is_open, can_vote, has_voted, _time) = pre_conditions.return_value
    assert is_open
    assert can_vote
    assert not has_voted

    app_client.call(
        call_abi_method="vote",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[(0, "V"), (0, voter_account.public_key)],
            sender=voter_account.address,
            signer=voter_account.signer,
            suggested_params=suggested_params(algod_client=algod_client, fee=12000, flat_fee=True),
        ),
        answer_ids=[0] * 10,
        fund_min_bal_req=payment_transaction(
            algod_client=algod_client,
            amount=400 * (32 + 2 + 10) + 2500,
            sender=voter_account,
            note=b"Vote payment",
            receiver=app_client.app_address,
        ),
        signature=get_account_signature(voter_account.public_key),
    )

    pre_conditions = app_client.call(
        call_abi_method="get_preconditions",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            sender=voter_account.address,
            signer=voter_account.signer,
            boxes=[(0, voter_account.public_key)],
            suggested_params=suggested_params(algod_client=algod_client, fee=4000),
        ),
        signature=get_account_signature(voter_account.public_key),
    )
    (is_open, can_vote, has_voted, _time) = pre_conditions.return_value
    assert is_open
    assert can_vote
    assert has_voted

    app_client.call(
        call_abi_method="close",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[(0, "V")],
            sender=creator_account.address,
            signer=creator_account.signer,
            suggested_params=suggested_params(
                algod_client=algod_client, fee=1000000, flat_fee=True
            ),
        ),
    )

    pre_conditions = app_client.call(
        call_abi_method="get_preconditions",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[(0, account.public_key)],
            suggested_params=suggested_params(algod_client=algod_client, fee=4000),
        ),
        signature=get_account_signature(voter_account.public_key),
    )
    (is_open, _can_vote, _has_voted, _time) = pre_conditions.return_value
    assert not is_open


def test_arc4_routing(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(TEST_CASES_DIR / "abi_routing" / "contract.py")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create
    create_response = app_client.create()
    assert create_response.confirmed_round

    response = app_client.opt_in("opt_in", uint=42, bites=b"43")
    assert response.confirmed_round

    app_client.call("method_with_default_args")

    hello_result = app_client.call("hello_with_algopy_string", name="Algopy")
    assert hello_result.return_value == "Hello Algopy!"


def test_arc4_routing_with_many_params(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
    asset_a: int,
    asset_b: int,
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(TEST_CASES_DIR / "abi_routing" / "contract.py")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create
    create_response = app_client.create()
    assert create_response.confirmed_round

    result = app_client.call(
        "method_with_more_than_15_args",
        a=1,
        b=1,
        c=1,
        d=1,
        e=1,
        f=1,
        g=1,
        h=1,
        i=1,
        j=1,
        k=1,
        l=1,
        m=1,
        n=1,
        o=1,
        p=1,
        q=1,
        r=1,
        s=b"a",
        t=b"b",
        u=1,
        v=1,
        pay=payment_transaction(
            algod_client=algod_client,
            amount=100000,
            sender=account,
            note=b"Test 1",
            receiver=app_client.app_address,
        ),
        pay2=payment_transaction(
            algod_client=algod_client,
            amount=200000,
            sender=account,
            note=b"Test 2",
            receiver=app_client.app_address,
        ),
        asset=asset_a,
        asset2=asset_b,
    )
    assert result.return_value == 20

    (logged_string,) = decode_logs(result.tx_info["logs"][:-1], "u")
    assert logged_string == "ab"

    result2 = app_client.call(
        "method_with_15_args",
        one=1,
        two=1,
        three=1,
        four=1,
        five=1,
        six=1,
        seven=1,
        eight=1,
        nine=1,
        ten=1,
        eleven=1,
        twelve=1,
        thirteen=1,
        fourteen=1,
        fifteen=b"fifteen",
    )
    assert result2.return_value == list(b"fifteen")


def test_transaction(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(TEST_CASES_DIR / "transaction")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create
    create_response = app_client.create()
    assert create_response.confirmed_round

    # ensure app meets minimum balance requirements
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=100_000,
        ),
    )

    app_client.call(
        "pay",
        txn=TransactionWithSigner(
            transaction.PaymentTxn(
                sender=account.address,
                receiver=app_client.app_address,
                amt=1001,
                sp=algod_client.suggested_params(),
            ),
            signer=account.signer,
        ),
    )

    # TODO: call remaining transaction methods


def test_dynamic_array_of_string(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(TEST_CASES_DIR / "arc4_types/dynamic_string_array.py")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    create_response = app_client.create()
    assert create_response.confirmed_round

    xyz_result = app_client.call("xyz")
    assert xyz_result.return_value == list("XYZ")

    xyz_raw_result = app_client.call("xyz_raw")
    assert xyz_raw_result.return_value == list("XYZ")


def test_array_rebinding(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(TEST_CASES_DIR / "arc4_types/mutable_params2.py")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    create_response = app_client.create()
    assert create_response.confirmed_round

    app_client.call("test_array_rebinding")


def test_avm_types_in_abi(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    example = TEST_CASES_DIR / "avm_types_in_abi" / "contract.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    max_biguint = 2**512 - 1
    result = app_client.create(
        "create",
        bool_param=True,
        uint64_param=45,
        bytes_param=b"Hello world!",
        biguint_param=max_biguint,
        string_param="Hi again",
        tuple_param=(True, 45, b"Hello world!", max_biguint, "Hi again"),
    )

    mapped_return = (
        result.return_value[0],
        result.return_value[1],
        bytes(result.return_value[2]),
        result.return_value[3],
        result.return_value[4],
    )

    assert mapped_return == (True, 45, b"Hello world!", max_biguint, "Hi again")

    result2 = app_client.call(call_abi_method="tuple_of_arc4", args=(255, account.address))

    assert result2.return_value[0] == 255
    assert result2.return_value[1] == account.address


def test_inner_transactions_c2c(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    example = TEST_CASES_DIR / "inner_transactions" / "c2c.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))

    # deploy greeter
    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 2
    app_client = algokit_utils.ApplicationClient(
        algod_client, app_spec, signer=account, suggested_params=increased_fee
    )
    app_client.create()

    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=100_000,
        ),
    )
    inner_app_id = app_client.call("bootstrap").return_value
    assert isinstance(inner_app_id, int)

    result = app_client.call(
        "log_greetings",
        name="There",
        transaction_parameters={"foreign_apps": [inner_app_id]},
    )
    assert decode_logs(result.tx_info["logs"], "b") == [b"HelloWorld returned: Hello, There"]


def test_inner_transactions_array_access(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> None:
    example = TEST_CASES_DIR / "inner_transactions" / "array_access.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))

    # deploy greeter
    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 2
    app_client = algokit_utils.ApplicationClient(
        algod_client, app_spec, signer=account, suggested_params=increased_fee
    )
    app_client.create()

    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=200_000,
        ),
    )

    app_client.call("test_branching_array_call", maybe=True)
    app_client.call("test_branching_array_call", maybe=False)


def test_inner_transactions_tuple(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> None:
    example = TEST_CASES_DIR / "inner_transactions" / "field_tuple_assignment.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))

    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 7
    app_client = algokit_utils.ApplicationClient(
        algod_client, app_spec, signer=account, suggested_params=increased_fee
    )
    app_client.create()

    app_client.call("test_assign_tuple")
    app_client.call("test_assign_tuple_mixed")


def test_inner_transactions_asset_transfer(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> None:
    example = TEST_CASES_DIR / "inner_transactions" / "asset_transfer.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))

    # deploy
    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 3
    app_client = algokit_utils.ApplicationClient(
        algod_client, app_spec, signer=account, suggested_params=increased_fee
    )
    app_client.create()

    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=200_000,
        ),
    )

    app_client.call("create_and_transfer")


def test_inner_transactions_assignment(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> None:
    example = TEST_CASES_DIR / "inner_transactions_assignment"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))

    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 8
    app_client = algokit_utils.ApplicationClient(
        algod_client, app_spec, signer=account, suggested_params=increased_fee
    )
    app_client.create()

    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=400_000,
        ),
    )

    app_client.call("test_itxn_slice")
    app_client.call("test_itxn_nested")


def test_state_proxies(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    example = TEST_CASES_DIR / "state_proxies" / "contract.py"

    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    app_client.create(transaction_parameters={"on_complete": OnComplete.OptInOC})
    assert app_client.get_global_state() == {"g1": 1, "g2": 0, "funky": 123}
    assert app_client.get_local_state(account.address) == {"l1": 2, "l2": 3}


def test_template_variables(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    example = TEST_CASES_DIR / "template_variables"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
        template_values={
            "SOME_BYTES": b"Hello I'm a variable",
            "SOME_BIG_UINT": (1337).to_bytes(length=2),
            "UPDATABLE": 1,
            "DELETABLE": 1,
        },
    )

    app_client.create()

    get_bytes = app_client.call(
        call_abi_method="get_bytes",
    )
    assert bytes(get_bytes.return_value) == b"Hello I'm a variable"

    get_uint = app_client.call(
        call_abi_method="get_big_uint",
    )

    assert get_uint.return_value == 1337

    app_client = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
        app_id=app_client.app_id,
        template_values={
            "SOME_BYTES": b"Updated variable",
            "SOME_BIG_UINT": (0).to_bytes(length=2),
            "UPDATABLE": 0,
            "DELETABLE": 1,
        },
    )

    app_client.update()

    get_bytes = app_client.call(
        call_abi_method="get_bytes",
    )
    assert bytes(get_bytes.return_value) == b"Updated variable"

    get_uint = app_client.call(
        call_abi_method="get_big_uint",
    )

    assert get_uint.return_value == 0

    try:
        app_client.update()
        raise AssertionError("Update should fail")
    except LogicError:
        pass

    app_client.delete()


def test_merkle(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    example = EXAMPLES_DIR / "merkle"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
    )

    test_tree = MerkleTree(
        [
            b"a",
            b"b",
            b"c",
            b"d",
            b"e",
        ]
    )
    app_client.create(call_abi_method="create", root=test_tree.root)

    assert app_client.call(
        call_abi_method="verify",
        leaf=sha_256_raw(b"a"),
        proof=test_tree.get_proof(b"a"),
    ).return_value


def test_typed_abi_call(
    algod_client: AlgodClient, account: algokit_utils.Account, asset_a: int
) -> None:
    logger = algokit_utils.ApplicationClient(
        algod_client,
        algokit_utils.ApplicationSpecification.from_json(
            compile_arc32(TEST_CASES_DIR / "typed_abi_call" / "logger.py")
        ),
        signer=account,
    )
    logger.create()

    example = TEST_CASES_DIR / "typed_abi_call" / "typed_c2c.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))

    # deploy greeter
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 6
    txn_params = algokit_utils.OnCompleteCallParameters(suggested_params=increased_fee)

    app_client.call(
        "test_method_selector_kinds",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_arg_conversion",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_method_overload",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_15plus_args",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_void",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_ref_types",
        transaction_parameters=txn_params,
        app=logger.app_id,
        asset=asset_a,
    )

    app_client.call(
        "test_account_to_address",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_native_tuple",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_native_tuple_method_ref",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_nested_tuples",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_native_string",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_native_bytes",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_native_uint64",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_native_biguint",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_no_args",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_is_a_b",
        transaction_parameters=txn_params,
        a=b"a",
        b=b"b",
        app=logger.app_id,
    )

    app_client.call(
        "test_named_tuples",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )


def test_arc28(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        algokit_utils.ApplicationSpecification.from_json(compile_arc32(EXAMPLES_DIR / "arc_28")),
        signer=account,
    )
    app_client.create()

    a = 42
    b = 12
    result = app_client.call(
        "emit_swapped",
        a=a,
        b=b,
    )
    logs = result.tx_info["logs"]
    events = decode_logs(logs, "bbb")
    for event in events:
        assert isinstance(event, bytes)
        event_sig = event[:4]
        event_data = event[4:]
        assert event_sig == bytes.fromhex("1ccbd925")
        assert event_data == b.to_bytes(length=8) + a.to_bytes(length=8)


@pytest.fixture
def other_account(algod_client: AlgodClient) -> algokit_utils.Account:
    v = algosdk.account.generate_account()
    voter_account = algokit_utils.Account(private_key=v[0], address=v[1])
    algokit_utils.transfer(
        client=algod_client,
        parameters=algokit_utils.TransferParameters(
            from_account=algokit_utils.get_localnet_default_account(algod_client),
            to_address=voter_account.address,
            micro_algos=10000000,
        ),
    )
    return voter_account


def test_tictactoe(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
    other_account: algokit_utils.Account,
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(EXAMPLES_DIR / "tictactoe" / "tictactoe.py")
    )
    client_host = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
    )

    client_host.create(call_abi_method="new_game", move=(0, 0))
    turn_result = client_host.call("whose_turn")
    assert turn_result.return_value == 2
    # no one has joined, can start a new game
    client_host.call(call_abi_method="new_game", move=(1, 1))

    with pytest.raises(algokit_utils.logic_error.LogicError) as exc_info:
        client_host.call(call_abi_method="play", move=(0, 0))
    assert exc_info.value.line_no is not None
    assert "It is the challenger's turn" in exc_info.value.lines[exc_info.value.line_no]

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "- - -",
        "- X -",
        "- - -",
    ]
    assert winner is None

    client_challenger = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        app_id=client_host.app_id,
        signer=other_account,
    )

    client_challenger.call(call_abi_method="join_game", move=(0, 0))

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O - -",
        "- X -",
        "- - -",
    ]
    assert winner is None

    turn_result = client_challenger.call("whose_turn")
    assert turn_result.return_value == 1

    with pytest.raises(algokit_utils.logic_error.LogicError) as exc_info:
        client_host.call(call_abi_method="new_game", move=(2, 2))
    assert exc_info.value.line_no is not None
    assert "Game isn't over" in exc_info.value.lines[exc_info.value.line_no]

    client_host.call(call_abi_method="play", move=(0, 1))

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O - -",
        "X X -",
        "- - -",
    ]
    assert winner is None

    client_challenger.call(call_abi_method="play", move=(1, 0))

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O O -",
        "X X -",
        "- - -",
    ]
    assert winner is None

    client_host.call(call_abi_method="play", move=(2, 1))

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O O -",
        "X X X",
        "- - -",
    ]
    assert winner == "Host"

    client_host.call(call_abi_method="new_game", move=(1, 1))
    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "- - -",
        "- X -",
        "- - -",
    ]
    assert winner is None


def _get_tic_tac_toe_game_status(
    client_host: algokit_utils.ApplicationClient,
) -> tuple[list[str], str | None]:
    state = client_host.get_global_state(raw=True)
    game = state[b"game"]
    assert isinstance(game, bytes)
    chars = ["X" if b == 1 else "O" if b == 2 else "-" for b in game]
    board = [" ".join(chars[:3]), " ".join(chars[3:6]), " ".join(chars[6:])]

    winner_index = state.get(b"winner")
    assert isinstance(winner_index, bytes | None)
    winner = {
        None: None,
        b"\01": "Host",
        b"\02": "Challenger",
        b"\03": "Draw",
    }[winner_index]
    return board, winner


@pytest.fixture(scope="module")
def dynamic_app_client(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> algokit_utils.ApplicationClient:
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        algokit_utils.ApplicationSpecification.from_json(
            compile_arc32(TEST_CASES_DIR / "arc4_dynamic_arrays")
        ),
        signer=account,
    )
    app_client.create()
    return app_client


def test_dynamic_arrays_static_element(
    dynamic_app_client: algokit_utils.ApplicationClient,
) -> None:
    static_struct_t = abi.ABIType.from_string("(uint64,byte[2])")
    static_arr_t = abi.ArrayDynamicType(static_struct_t)
    static_struct0 = (3, bytes((4, 5)))
    static_struct1 = (2**42, bytes((42, 255)))

    static_result = dynamic_app_client.call("test_static_elements")
    (static_arr_bytes, static_0_bytes, static_1_bytes) = decode_logs(
        static_result.tx_info["logs"], "bbb"
    )

    assert static_arr_bytes == static_arr_t.encode([static_struct0, static_struct1])
    assert static_0_bytes == static_struct_t.encode(static_struct0)
    assert static_1_bytes == static_struct_t.encode(static_struct1)


def test_dynamic_arrays_dynamic_element(
    dynamic_app_client: algokit_utils.ApplicationClient,
) -> None:
    dynamic_struct_t = abi.ABIType.from_string("(string,string)")
    dynamic_arr_t = abi.ABIType.from_string("(string,string)[]")
    dynamic_struct0 = ("a", "bee")
    dynamic_struct1 = ("Hello World", "a")

    dynamic_result = dynamic_app_client.call("test_dynamic_elements")
    (
        dynamic_arr_bytes,
        dynamic_0_bytes,
        dynamic_1_bytes,
        dynamic_2_bytes,
        dynamic_arr_bytes_01,
        dynamic_arr_bytes_0,
        empty_arr,
    ) = decode_logs(dynamic_result.tx_info["logs"], "b" * 7)

    assert dynamic_arr_bytes == dynamic_arr_t.encode(
        [dynamic_struct0, dynamic_struct1, dynamic_struct0]
    )
    assert dynamic_0_bytes == dynamic_struct_t.encode(dynamic_struct0)
    assert dynamic_1_bytes == dynamic_struct_t.encode(dynamic_struct1)
    assert dynamic_2_bytes == dynamic_struct_t.encode(dynamic_struct0)
    assert dynamic_arr_bytes_01 == dynamic_arr_t.encode([dynamic_struct0, dynamic_struct1])
    assert dynamic_arr_bytes_0 == dynamic_arr_t.encode([dynamic_struct0])
    assert empty_arr == dynamic_arr_t.encode([])


def test_dynamic_arrays_mixed_single_dynamic(
    dynamic_app_client: algokit_utils.ApplicationClient,
) -> None:
    mixed1_struct_t = abi.ABIType.from_string("(uint64,string,uint64)")
    mixed1_arr_t = abi.ArrayDynamicType(mixed1_struct_t)
    mixed1_struct0 = (3, "a", 2**42)
    mixed1_struct1 = (2**42, "bee", 3)

    mixed_single_result = dynamic_app_client.call("test_mixed_single_dynamic_elements")
    (mixed1_arr_bytes, mixed1_0_bytes, mixed1_1_bytes) = decode_logs(
        mixed_single_result.tx_info["logs"], "bbb"
    )

    assert mixed1_arr_bytes == mixed1_arr_t.encode([mixed1_struct0, mixed1_struct1])
    assert mixed1_0_bytes == mixed1_struct_t.encode(mixed1_struct0)
    assert mixed1_1_bytes == mixed1_struct_t.encode(mixed1_struct1)


def test_dynamic_arrays_mixed_multiple_dynamic(
    dynamic_app_client: algokit_utils.ApplicationClient,
) -> None:
    mixed2_struct_t = abi.ABIType.from_string("(uint64,string,uint64,uint16[],uint64)")
    mixed2_arr_t = abi.ArrayDynamicType(mixed2_struct_t)
    mixed2_struct0 = (3, "a", 2**42, (2**16 - 1, 0, 42), 3)
    mixed2_struct1 = (2**42, "bee", 3, (1, 2, 3, 4), 2**42)

    mixed_multiple_result = dynamic_app_client.call("test_mixed_multiple_dynamic_elements")
    (mixed2_arr_bytes, mixed2_0_bytes, mixed2_1_bytes) = decode_logs(
        mixed_multiple_result.tx_info["logs"], "bbb"
    )

    assert mixed2_arr_bytes == mixed2_arr_t.encode([mixed2_struct0, mixed2_struct1])
    assert mixed2_0_bytes == mixed2_struct_t.encode(mixed2_struct0)
    assert mixed2_1_bytes == mixed2_struct_t.encode(mixed2_struct1)


def test_nested_struct(
    dynamic_app_client: algokit_utils.ApplicationClient,
) -> None:
    dynamic_app_client.call("test_nested_struct_replacement")


def test_nested_tuple(
    dynamic_app_client: algokit_utils.ApplicationClient,
) -> None:
    dynamic_app_client.call("test_nested_tuple_modification")


def test_struct_in_box(
    algod_client: AlgodClient, account: algokit_utils.Account, asset_a: int
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(EXAMPLES_DIR / "struct_in_box" / "contract.py")
    )
    client = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
    )

    # Create the application
    client.create()

    # Fund the application (so it can have boxes)
    algokit_utils.transfer(
        algod_client,
        algokit_utils.TransferParameters(
            to_address=client.app_address, from_account=account, micro_algos=10_000_000
        ),
    )

    user_1 = {"id": 1, "name": "Bob", "asset": 0}
    user_2 = {"id": 2, "name": "Jane", "asset": 0}

    client.call(
        "add_user",
        user=user_1,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[
                (0, (1).to_bytes(8)),
            ]
        ),
    )

    client.call(
        "add_user",
        user=user_2,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[
                (0, (2).to_bytes(8)),
            ]
        ),
    )

    client.call(
        "attach_asset_to_user",
        user_id=user_1["id"],
        asset=asset_a,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[
                (0, (1).to_bytes(8)),
            ]
        ),
    )

    user_1_result = client.call(
        "get_user",
        user_id=1,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[
                (0, (1).to_bytes(8)),
            ]
        ),
    )
    assert user_1_result.return_value == ["Bob", 1, asset_a]
    user_2_result = client.call(
        "get_user",
        user_id=2,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            boxes=[
                (0, (2).to_bytes(8)),
            ]
        ),
    )
    assert user_2_result.return_value == ["Jane", 2, 0]


_ADDITIONAL_BOX_REF = (0, b"")


@pytest.fixture
def box_client(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> algokit_utils.ApplicationClient:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(EXAMPLES_DIR / "box_storage" / "contract.py")
    )
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=account, min_spending_balance_micro_algos=20_000_000
        ),
    )
    client = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
    )

    client.create()

    algokit_utils.transfer(
        algod_client,
        algokit_utils.TransferParameters(
            to_address=client.app_address, from_account=account, micro_algos=10_000_000
        ),
    )
    return client


def _params_with_boxes(
    *keys: str | bytes | int, additional_refs: int = 0
) -> algokit_utils.OnCompleteCallParameters:
    return algokit_utils.OnCompleteCallParameters(
        boxes=[(0, key.to_bytes(8) if isinstance(key, int) else key) for key in keys]
        + [_ADDITIONAL_BOX_REF] * additional_refs
    )


def test_box(box_client: algokit_utils.ApplicationClient) -> None:
    box_c = b"BOX_C"
    transaction_parameters = _params_with_boxes("box_a", "b", box_c, "box_d")

    (a_exist, b_exist, c_exist) = box_client.call(
        call_abi_method="boxes_exist",
        transaction_parameters=transaction_parameters,
    ).return_value
    assert not a_exist
    assert not b_exist
    assert not c_exist

    box_client.call(
        call_abi_method="set_boxes",
        a=56,
        b=b"Hello",
        c="World",
        transaction_parameters=transaction_parameters,
    )

    (a_exist, b_exist, c_exist) = box_client.call(
        call_abi_method="boxes_exist",
        transaction_parameters=transaction_parameters,
    ).return_value
    assert a_exist
    assert b_exist
    assert c_exist

    box_client.call("check_keys", transaction_parameters=transaction_parameters)

    (a, b, c) = box_client.call(
        call_abi_method="read_boxes",
        transaction_parameters=transaction_parameters,
    ).return_value

    assert (a, bytes(b), c) == (59, b"Hello", "World")

    box_client.call("delete_boxes", transaction_parameters=transaction_parameters)

    (a_exist, b_exist, c_exist) = box_client.call(
        call_abi_method="boxes_exist",
        transaction_parameters=transaction_parameters,
    ).return_value
    assert not a_exist
    assert not b_exist
    assert not c_exist

    box_client.call(
        call_abi_method="slice_box",
        transaction_parameters=_params_with_boxes(b"0", box_c),
    )

    box_client.call(call_abi_method="arc4_box", transaction_parameters=_params_with_boxes(b"d"))


def test_box_ref(box_client: algokit_utils.ApplicationClient) -> None:
    box_client.call(
        call_abi_method="test_box_ref",
        transaction_parameters=_params_with_boxes("box_ref", b"blob", additional_refs=6),
    )


def test_box_map(box_client: algokit_utils.ApplicationClient) -> None:
    box_client.call(
        call_abi_method="box_map_test",
        transaction_parameters=_params_with_boxes(0, 1),
    )

    key = 2
    transaction_parameters = _params_with_boxes(key)
    assert not box_client.call(
        call_abi_method="box_map_exists",
        key=key,
        transaction_parameters=transaction_parameters,
    ).return_value, "Box does not exist (yet)"
    box_client.call(
        call_abi_method="box_map_set",
        key=key,
        value="Hello 123",
        transaction_parameters=transaction_parameters,
    )
    assert (
        box_client.call(
            call_abi_method="box_map_get",
            key=key,
            transaction_parameters=transaction_parameters,
        ).return_value
        == "Hello 123"
    ), "Box value is what was set"

    assert box_client.call(
        call_abi_method="box_map_exists",
        key=key,
        transaction_parameters=transaction_parameters,
    ).return_value, "Box exists"

    box_client.call(
        call_abi_method="box_map_del",
        key=key,
        transaction_parameters=transaction_parameters,
    )

    assert not box_client.call(
        call_abi_method="box_map_exists",
        key=key,
        transaction_parameters=transaction_parameters,
    ).return_value, "Box does not exist after deletion"


def test_compile(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(TEST_CASES_DIR / "compile", file_name="factory.py")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    app_client.create()

    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 6
    txn_params = algokit_utils.OnCompleteCallParameters(suggested_params=increased_fee)
    algokit_utils.config.config.configure(debug=True, trace_all=True)
    app_client.call("test_compile_contract", transaction_parameters=txn_params)
    app_client.call("test_compile_contract_tmpl", transaction_parameters=txn_params)
    app_client.call("test_compile_contract_prfx", transaction_parameters=txn_params)
    app_client.call("test_compile_contract_large", transaction_parameters=txn_params)

    app_client.call("test_arc4_create", transaction_parameters=txn_params)
    app_client.call("test_arc4_create_tmpl", transaction_parameters=txn_params)
    app_client.call("test_arc4_create_prfx", transaction_parameters=txn_params)
    app_client.call("test_arc4_create_large", transaction_parameters=txn_params)
    app_client.call("test_arc4_create_modified_compiled", transaction_parameters=txn_params)
    app_client.call("test_arc4_update", transaction_parameters=txn_params)
    app_client.call("test_other_constants", transaction_parameters=txn_params)
    app_client.call("test_abi_call_create_params", transaction_parameters=txn_params)


def test_nested_tuples(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    example = TEST_CASES_DIR / "tuple_support" / "nested_tuples.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create
    app_client.create()

    app_client.call("run_tests")

    response = app_client.call("nested_tuple_params", args=("Hello", (b"World", (123,))))

    assert bytes(response.return_value[0]) == b"World"
    assert response.return_value[1][0] == "Hello"
    assert response.return_value[1][1] == 123

    response = app_client.call("named_tuple", args=(1, b"2", "3"))
    assert response.return_value == [1, [50], "3"]

    response = app_client.call("nested_named_tuple_params", args=(1, 2, (3, b"4", "5")))
    assert response.return_value == [1, 2, [3, [52], "5"]]


def test_named_tuples(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    example = TEST_CASES_DIR / "named_tuples" / "contract.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create
    app_client.create()

    result = app_client.call("build_tuple", a=12, b=343459043, c="hello 123", d=account.public_key)

    (a, b, c, d) = result.return_value

    app_client.call("test_tuple", value=(a, b, c, d))

    app_client.call(
        "test_tuple",
        value={"a": 34, "b": 53934433, "c": "hmmmm", "d": account.public_key},
    )


def test_group_side_effects(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    test_dir = TEST_CASES_DIR / "group_side_effects"
    other_app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(test_dir / "other.py")
    )
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(test_dir / "contract.py")
    )
    other_app_client = algokit_utils.ApplicationClient(
        algod_client, other_app_spec, signer=account
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create app
    app_client.create()
    sp = algod_client.suggested_params()

    # compose group with asset and app create txns
    asset_create_txn = TransactionWithSigner(
        transaction.AssetCreateTxn(
            account.address,
            sp,
            10_000_000,
            0,
            default_frozen=False,
            asset_name="asset group",
            unit_name="AGRP",
        ),
        signer=account.signer,
    )
    atc = AtomicTransactionComposer()
    other_app_client.compose_create(atc)
    app_create_txn = atc.txn_list[-1]

    # call app with create txns
    response = app_client.call(
        "create_group", asset_create=asset_create_txn, app_create=app_create_txn
    )
    asset_id, other_app_id = response.return_value

    # compose group with app call
    other_app_client.app_id = other_app_id
    atc = AtomicTransactionComposer()
    other_app_client.compose_call(atc, "some_value")
    app_call_txn = atc.txn_list[-1]
    app_client.call("log_group", app_call=app_call_txn)


def test_state_mutations(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    test_dir = TEST_CASES_DIR / "state_mutations"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(test_dir))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create app
    app_client.create()
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=200_000,
        ),
    )
    box_key = b"box"
    map_key = b"map" + account.public_key
    txn_params: algokit_utils.OnCompleteCallParametersDict = {
        "boxes": [(0, box_key), (0, map_key)]
    }
    app_client.opt_in(transaction_parameters=txn_params)
    response = app_client.call("get", transaction_parameters=txn_params)
    assert response.return_value == []

    # append
    app_client.call("append", transaction_parameters=txn_params)
    response = app_client.call("get", transaction_parameters=txn_params)
    assert response.return_value == [[1, "baz"]]

    # modify
    app_client.call("modify", transaction_parameters=txn_params)
    response = app_client.call("get", transaction_parameters=txn_params)
    assert response.return_value == [[1, "modified"]]

    # append
    app_client.call("append", transaction_parameters=txn_params)
    response = app_client.call("get", transaction_parameters=txn_params)
    assert response.return_value == [[1, "modified"], [1, "baz"]]


@pytest.mark.parametrize(
    ("file_name", "expected_init_log", "expected_method_log"),
    [
        (
            "base1",
            ["base1.__init__", "gp.__init__"],
            ["base1.method", "gp.method"],
        ),
        (
            "base2",
            ["base2.__init__", "gp.__init__"],
            ["base2.method", "gp.method"],
        ),
        (
            "derived",
            ["derived.__init__", "base1.__init__", "base2.__init__", "gp.__init__"],
            ["derived.method", "base1.method", "base2.method", "gp.method"],
        ),
    ],
)
def test_diamond_mro(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
    file_name: str,
    expected_init_log: list[str],
    expected_method_log: list[str],
) -> None:
    example = TEST_CASES_DIR / "diamond_mro" / f"{file_name}.py"

    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    init_response = app_client.create(call_abi_method=True)
    init_logs_raw = init_response.tx_info["logs"]
    init_logs = decode_logs(init_logs_raw, len(init_logs_raw) * "u")
    assert init_logs == expected_init_log

    method_response = app_client.call(call_abi_method="method")
    method_logs_raw = method_response.tx_info["logs"]
    method_logs = decode_logs(method_logs_raw, len(method_logs_raw) * "u")
    assert method_logs == expected_method_log


@pytest.mark.parametrize("optimization_level", [0, 1])
def test_array_uint64(
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
) -> None:
    example = TEST_CASES_DIR / "array" / "uint64.py"

    app_spec = _get_app_spec(example, optimization_level)
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    simulate_call(app_client, "test_array")
    simulate_call(app_client, "test_array_extend")
    simulate_call(app_client, "test_array_multiple_append")
    simulate_call(app_client, "test_iteration")
    simulate_call(app_client, "test_array_copy_and_extend")
    simulate_call(app_client, "test_array_evaluation_order")

    simulate_call(app_client, "test_allocations", num=255)
    with pytest.raises(LogicError, match="no available slots\t\t<-- Error"):
        simulate_call(app_client, "test_allocations", num=256)

    with pytest.raises(LogicError, match="max array length exceeded\t\t<-- Error"):
        simulate_call(app_client, "test_array_too_long")

    simulate_call(app_client, "test_quicksort")


@pytest.mark.parametrize("optimization_level", [0, 1])
def test_array_static_size(
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
) -> None:
    example = TEST_CASES_DIR / "array" / "static_size.py"

    app_spec = _get_app_spec(example, optimization_level)
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()
    # ensure app meets minimum balance requirements
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=200_000,
        ),
    )

    x1, y1 = 3, 4
    x2, y2 = 6, 8
    sender = account.public_key[:32]
    response = simulate_call(app_client, "test_array", x1=x1, y1=y1, x2=x2, y2=y2)
    assert response.abi_results[0].return_value == 15
    assert _get_box_state(response, b"a") == _get_arc4_bytes(
        "(uint64,uint64,(uint64,uint64,address,(uint64,uint64),uint512))[]",
        [
            (0, 0, (5, 1, sender, (2, 1), 1)),
            (x1, y1, (5, 2, sender, (3, 4), 2)),
            (x2, y2, (5, 3, sender, (4, 9), 3)),
        ],
    )

    response = simulate_call(app_client, "test_arc4_conversion", length=5)
    assert response.abi_results[0].return_value == [1, 2, 3, 4, 5]

    response = simulate_call(app_client, "sum_array", arc4_arr=[1, 2, 3, 4, 5])
    assert response.abi_results[0].return_value == 15

    response = simulate_call(app_client, "test_bool_array", length=5)
    assert response.abi_results[0].return_value == 2
    response = simulate_call(app_client, "test_bool_array", length=4)
    assert response.abi_results[0].return_value == 2
    response = simulate_call(app_client, "test_bool_array", length=6)
    assert response.abi_results[0].return_value == 3

    response = simulate_call(app_client, "test_bool_array", length=5)
    assert response.abi_results[0].return_value == 2

    response = simulate_call(app_client, "test_extend_from_tuple", some_more=[[1, 2], [3, 4]])
    assert response.abi_results[0].return_value == [[1, 2], [3, 4]]

    response = simulate_call(app_client, "test_extend_from_arc4_tuple", some_more=[[1, 2], [3, 4]])
    assert response.abi_results[0].return_value == [[1, 2], [3, 4]]

    response = simulate_call(app_client, "test_arc4_bool")
    assert response.abi_results[0].return_value == [False, True]


@pytest.mark.parametrize("optimization_level", [0, 1])
def test_immutable_array(
    algod_client: AlgodClient, optimization_level: int, account: algokit_utils.Account
) -> None:
    immutable_array_app = _get_immutable_array_app(algod_client, optimization_level, account)

    response = simulate_call(immutable_array_app, "test_uint64_array")
    assert _get_global_state(response, b"a") == _get_arc4_bytes(
        "uint64[]", [42, 0, 23, 2, *range(10), 44]
    )

    response = simulate_call(immutable_array_app, "test_biguint_array")
    assert _get_box_state(response, b"biguint") == _get_arc4_bytes(
        "uint512[]", [0, *range(5), 2**512 - 2, 2**512 - 1]
    )

    response = simulate_call(immutable_array_app, "test_fixed_size_tuple_array")
    assert _get_global_state(response, b"c") == _get_arc4_bytes(
        "(uint64,uint64)[]", [(i + 1, i + 2) for i in range(4)]
    )

    response = simulate_call(immutable_array_app, "test_fixed_size_named_tuple_array")
    assert _get_global_state(response, b"d") == _get_arc4_bytes(
        "(uint64,bool,bool)[]", [(i, i % 2 == 0, i * 3 % 2 == 0) for i in range(5)]
    )

    response = simulate_call(immutable_array_app, "test_dynamic_sized_tuple_array")
    assert _get_global_state(response, b"e") == _get_arc4_bytes(
        "(uint64,byte[])[]", [(i + 1, b"\x00" * i) for i in range(4)]
    )

    response = simulate_call(immutable_array_app, "test_dynamic_sized_named_tuple_array")
    assert _get_global_state(response, b"f") == _get_arc4_bytes(
        "(uint64,string)[]", [(i + 1, " " * i) for i in range(4)]
    )

    response = simulate_call(immutable_array_app, "test_bit_packed_tuples")
    assert _get_global_state(response, b"bool2") == _get_arc4_bytes(
        "(bool,bool)[]", [(i == 0, i == 1) for i in range(5)]
    )
    assert _get_global_state(response, b"bool7") == _get_arc4_bytes(
        "(uint64,bool,bool,bool,bool,bool,bool,bool,uint64)[]",
        [(i, i == 0, i == 1, i == 2, i == 3, i == 4, i == 5, i == 6, i + 1) for i in range(5)],
    )
    assert _get_global_state(response, b"bool8") == _get_arc4_bytes(
        "(uint64,bool,bool,bool,bool,bool,bool,bool,bool,uint64)[]",
        [
            (i, i == 0, i == 1, i == 2, i == 3, i == 4, i == 5, i == 6, i == 7, i + 1)
            for i in range(5)
        ],
    )
    assert _get_global_state(response, b"bool9") == _get_arc4_bytes(
        "(uint64,bool,bool,bool,bool,bool,bool,bool,bool,bool,uint64)[]",
        [
            (i, i == 0, i == 1, i == 2, i == 3, i == 4, i == 5, i == 6, i == 7, i == 8, i + 1)
            for i in range(5)
        ],
    )

    append = 5
    arr = [[i, i % 2 == 0, i % 3 == 0] for i in range(append)]
    response = simulate_call(
        immutable_array_app, "test_convert_to_array_and_back", arr=arr, append=append
    )
    assert response.abi_results[0].return_value == [*arr, *arr]

    for tuple_type in ("arc4", "native"):
        response = simulate_call(
            immutable_array_app, f"test_concat_with_{tuple_type}_tuple", arg=(3, 4)
        )
        abi_result = response.abi_results[0]
        assert not abi_result.decode_error
        assert abi_result.return_value == [1, 2, 3, 4]
    for tuple_type in ("native", "arc4"):
        response = simulate_call(
            immutable_array_app, f"test_dynamic_concat_with_{tuple_type}_tuple", arg=("c", "d")
        )
        abi_result = response.abi_results[0]
        assert (
            not abi_result.decode_error
        ), f"{abi_result.method.get_signature()}: {abi_result.decode_error}"
        assert abi_result.return_value == ["a", "b", "c", "d"]

    response = simulate_call(
        immutable_array_app,
        "test_concat_immutable_dynamic",
        imm1=[[1, "one"], [2, "foo"]],
        imm2=[[3, "tree"], [4, "floor"]],
    )
    assert response.abi_results[0].return_value == [
        [1, "one"],
        [2, "foo"],
        [3, "tree"],
        [4, "floor"],
    ]


_EXPECTED_LENGTH_20 = [False, False, True, *(False,) * 17]


@pytest.mark.parametrize("length", [0, 1, 2, 3, 4, 7, 8, 9, 15, 16, 17])
@pytest.mark.parametrize("optimization_level", [0, 1])
def test_immutable_bool_array(
    algod_client: AlgodClient, optimization_level: int, length: int, account: algokit_utils.Account
) -> None:
    immutable_array_app = _get_immutable_array_app(algod_client, optimization_level, account)

    response = simulate_call(immutable_array_app, "test_bool_array", length=length)
    expected = _EXPECTED_LENGTH_20[:length]
    assert _get_global_state(response, b"g") == _get_arc4_bytes("bool[]", expected)


@pytest.mark.parametrize("optimization_level", [0, 1])
def test_immutable_routing(
    algod_client: AlgodClient, optimization_level: int, account: algokit_utils.Account
) -> None:
    immutable_array_app = _get_immutable_array_app(algod_client, optimization_level, account)

    response = simulate_call(
        immutable_array_app,
        "sum_uints_and_lengths_and_trues",
        arr1=list(range(5)),
        arr2=[i % 2 == 0 for i in range(6)],
        arr3=[(i, i % 2 == 0, i % 3 == 0) for i in range(7)],
        arr4=[(i, " " * i) for i in range(8)],
    )
    assert response.abi_results[0].return_value == [10, 3, 21 + 4 + 3, 28 * 2]

    append = 4
    response = simulate_call(immutable_array_app, "test_uint64_return", append=append)
    assert response.abi_results[0].return_value == [1, 2, 3, *range(append)]

    append = 5
    response = simulate_call(immutable_array_app, "test_bool_return", append=append)
    assert response.abi_results[0].return_value == [
        *[True, False, True, False, True],
        *(i % 2 == 0 for i in range(append)),
    ]

    append = 6
    response = simulate_call(immutable_array_app, "test_tuple_return", append=append)
    assert response.abi_results[0].return_value == [
        [0, True, False],
        *([i, i % 2 == 0, i % 3 == 0] for i in range(append)),
    ]

    append = 3
    response = simulate_call(immutable_array_app, "test_dynamic_tuple_return", append=append)
    assert response.abi_results[0].return_value == [
        [0, "Hello"],
        *([i, " " * i] for i in range(append)),
    ]


@pytest.mark.parametrize("optimization_level", [0, 1])
def test_nested_immutable(
    algod_client: AlgodClient, optimization_level: int, account: algokit_utils.Account
) -> None:
    immutable_array_app = _get_immutable_array_app(algod_client, optimization_level, account)

    response = simulate_call(
        immutable_array_app,
        "test_nested_array",
        arr_to_add=5,
        arr=[[i * j for i in range(5)] for j in range(3)],
    )
    assert response.abi_results[0].return_value == [
        0,
        10,
        20,
        0,
        0,
        1,
        3,
        6,
    ]


def _get_immutable_array_app(
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
) -> ApplicationClient:
    example = TEST_CASES_DIR / "array" / "immutable.py"

    app_spec = _get_app_spec(example, optimization_level)
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    # ensure app meets minimum balance requirements
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=400_000,
        ),
    )

    return app_client


def _get_app_spec(
    app_spec_path: Path, optimization_level: int
) -> algokit_utils.ApplicationSpecification:
    return algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            app_spec_path,
            optimization_level=optimization_level,
            disabled_optimizations=() if optimization_level else ("remove_unused_variables",),
        )
    )


def simulate_call(
    app_client: algokit_utils.ApplicationClient,
    method: str,
    extra_budget: int = 20_000,
    txn_params: OnCompleteCallParametersDict | None = None,
    **kwargs: object,
) -> SimulateAtomicTransactionResponse:
    atc = algosdk.atomic_transaction_composer.AtomicTransactionComposer()
    app_client.compose_call(
        atc, call_abi_method=method, transaction_parameters=txn_params, **kwargs
    )
    simulate_response = atc.simulate(
        app_client.algod_client,
        SimulateRequest(
            txn_groups=[],
            extra_opcode_budget=extra_budget,
            allow_unnamed_resources=True,
            exec_trace_config=SimulateTraceConfig(
                enable=True,
                stack_change=True,
                scratch_change=True,
                state_change=True,
            ),
        ),
    )

    if simulate_response.failure_message:
        logic_error_data = algokit_utils.logic_error.parse_logic_error(
            simulate_response.failure_message
        )
        if logic_error_data is None:
            pytest.fail(f"expected LogicError, got {simulate_response.failure_message}")

        if app_client.approval is None:
            pytest.fail("expected approval program")
        raise algokit_utils.LogicError(
            logic_error_str=simulate_response.failure_message,
            program=app_client.approval.teal,
            source_map=app_client.approval.source_map,
            **logic_error_data,
        )
    return simulate_response


def _get_arc4_bytes(arc4_type: str, value: object) -> bytes:
    return algosdk.abi.ABIType.from_string(arc4_type).encode(value)


def _get_global_state(
    sim: SimulateAtomicTransactionResponse,
    key: bytes,
) -> bytes:
    group = sim.simulate_response["txn-groups"][0]
    deltas = group["txn-results"][0]["txn-result"]["global-state-delta"]
    key_b64 = base64.b64encode(key).decode("utf8")
    (match,) = (base64.b64decode(d["value"]["bytes"]) for d in deltas if d["key"] == key_b64)
    return match


def _get_box_state(
    sim: SimulateAtomicTransactionResponse,
    key: bytes,
) -> bytes:
    group = sim.simulate_response["txn-groups"][0]
    trace = group["txn-results"][0]["exec-trace"]["approval-program-trace"]
    scs = [sc for t in trace for sc in t.get("state-changes", [])]
    key_b64 = base64.b64encode(key).decode("utf8")
    *_, sc = (  # get last matching write to state-change
        sc
        for sc in scs
        if sc.get("app-state-type") == "b"  # box
        and sc.get("operation") == "w"  # write
        and sc.get("key") == key_b64  # matching key
    )
    return base64.b64decode(sc["new-value"]["bytes"])
