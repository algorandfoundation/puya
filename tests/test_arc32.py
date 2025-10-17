import base64
import contextlib
import hashlib
import math
import random
import re
from collections.abc import Sequence
from pathlib import Path

import algokit_utils
import algokit_utils.config
import algosdk
import pytest
from algokit_utils import (
    ApplicationClient,
    LogicError,
    OnCompleteCallParameters,
    OnCompleteCallParametersDict,
)
from algosdk import abi, constants, transaction
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
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
from puya.utils import sha512_256_hash
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
    contract_name: str | None = None,
    disabled_optimizations: Sequence[str] = (),
    validate_abi_values: bool = True,
) -> str:
    result = compile_src_from_options(
        PuyaPyOptions(
            paths=(src_path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
            optimizations_override={o: False for o in disabled_optimizations},
            validate_abi_values=validate_abi_values,
        )
    )
    if contract_name is None:
        (contract,) = result.teal
    else:
        (contract,) = (
            t
            for t in result.teal
            if isinstance(t, CompiledContract)
            if t.metadata.name == contract_name
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

    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=100_000,
        ),
    )
    with_box = algokit_utils.OnCompleteCallParameters(boxes=[(0, "box_mapbox")])
    app_client.call("clear", transaction_parameters=with_box)

    response = app_client.call("order_of_eval_global")
    logs = [base64.b64decode(log) for log in response.tx_info["logs"]]
    assert logs == [b"default"]

    response = app_client.call("order_of_eval_local")
    logs = [base64.b64decode(log) for log in response.tx_info["logs"]]
    assert logs == [b"account", b"default"]

    response = app_client.call("order_of_eval_box", transaction_parameters=with_box)
    logs = [base64.b64decode(log) for log in response.tx_info["logs"]]
    assert logs == [b"key", b"default"]


def test_template_variables(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    example = TEST_CASES_DIR / "template_variables"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    tuple_ = [1, 2]
    named_tuple = [3, 4]
    struct = [5, 6]
    tuple_bytes = _get_arc4_bytes("(uint64,uint64)", tuple_)
    named_tuple_bytes = _get_arc4_bytes("(uint64,uint64)", named_tuple)
    struct_bytes = _get_arc4_bytes("(uint64,uint64)", struct)
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        app_spec,
        signer=account,
        template_values={
            "SOME_BYTES": b"Hello I'm a variable",
            "SOME_BIG_UINT": (1337).to_bytes(length=2),
            "UPDATABLE": 1,
            "DELETABLE": 1,
            "TUPLE": tuple_bytes,
            "NAMED_TUPLE": named_tuple_bytes,
            "STRUCT": struct_bytes,
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

    get_tuple = app_client.call("get_a_tuple")
    assert get_tuple.return_value == tuple_, "expected correct tuple template var"

    get_named_tuple = app_client.call("get_a_named_tuple")
    assert get_named_tuple.return_value == named_tuple, "expected correct named tuple template var"

    get_struct = app_client.call("get_a_struct")
    assert get_struct.return_value == struct, "expected correct struct template var"

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
            "TUPLE": tuple_bytes,
            "NAMED_TUPLE": named_tuple_bytes,
            "STRUCT": struct_bytes,
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

    with pytest.raises(Exception, match="transaction rejected by ApprovalProgram"):
        app_client.update()

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
    increased_fee.fee = constants.min_txn_fee * 7
    txn_params = algokit_utils.OnCompleteCallParameters(
        suggested_params=increased_fee, foreign_apps=[logger.app_id], foreign_assets=[asset_a]
    )

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

    app_client.call(
        "test_arc4_struct",
        transaction_parameters=txn_params,
        app=logger.app_id,
    )

    app_client.call(
        "test_resource_encoding",
        transaction_parameters=txn_params,
        asset=asset_a,
        app_to_call=logger.app_id,
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


def test_avm_12(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        algokit_utils.ApplicationSpecification.from_json(
            compile_arc32(TEST_CASES_DIR / "avm_12", contract_name="Contract")
        ),
        signer=account,
    )
    app_client.create()
    increased_fee = algod_client.suggested_params()
    increased_fee.flat_fee = True
    increased_fee.fee = constants.min_txn_fee * 4

    app_client.call(
        "test_reject_version",
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            suggested_params=increased_fee
        ),
    )


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
    app_client.create(transaction_parameters={"note": random.randbytes(8)})
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
    transaction_parameters = _params_with_boxes(
        "box_a", "b", box_c, "box_d", "box_large", additional_refs=3
    )

    (a_exist, b_exist, c_exist, large_exist) = box_client.call(
        call_abi_method="boxes_exist",
        transaction_parameters=transaction_parameters,
    ).return_value
    assert not a_exist
    assert not b_exist
    assert not c_exist
    assert not large_exist

    box_client.call(
        call_abi_method="set_boxes",
        a=56,
        b=b"Hello",
        c="World",
        transaction_parameters=transaction_parameters,
    )

    (a_exist, b_exist, c_exist, large_exist) = box_client.call(
        call_abi_method="boxes_exist",
        transaction_parameters=transaction_parameters,
    ).return_value
    assert a_exist
    assert b_exist
    assert c_exist
    assert large_exist

    box_client.call("check_keys", transaction_parameters=transaction_parameters)

    (a, b, c, large) = box_client.call(
        call_abi_method="read_boxes",
        transaction_parameters=transaction_parameters,
    ).return_value

    assert (a, bytes(b), c, large) == (59, b"Hello", "World", 42)

    box_client.call(
        call_abi_method="indirect_extract_and_replace",
        transaction_parameters=_params_with_boxes("box_large", additional_refs=6),
    )

    box_client.call("delete_boxes", transaction_parameters=transaction_parameters)

    (a_exist, b_exist, c_exist, large_exist) = box_client.call(
        call_abi_method="boxes_exist",
        transaction_parameters=transaction_parameters,
    ).return_value
    assert not a_exist
    assert not b_exist
    assert not c_exist
    assert not large_exist

    box_client.call(
        call_abi_method="slice_box",
        transaction_parameters=_params_with_boxes(b"0", box_c),
    )

    box_client.call(call_abi_method="arc4_box", transaction_parameters=_params_with_boxes(b"d"))

    many_ints_txn = _params_with_boxes("many_ints", additional_refs=4)
    sp = box_client.algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 1_000 * 16
    many_ints_txn.suggested_params = sp
    box_client.call("create_many_ints", transaction_parameters=many_ints_txn)

    box_client.call("set_many_ints", index=1, value=1, transaction_parameters=many_ints_txn)
    box_client.call("set_many_ints", index=2, value=2, transaction_parameters=many_ints_txn)
    box_client.call("set_many_ints", index=256, value=256, transaction_parameters=many_ints_txn)
    box_client.call("set_many_ints", index=511, value=511, transaction_parameters=many_ints_txn)
    box_client.call("set_many_ints", index=512, value=512, transaction_parameters=many_ints_txn)

    sum_many_ints = box_client.call("sum_many_ints", transaction_parameters=many_ints_txn)
    assert sum_many_ints.return_value == (1 + 2 + 256 + 511 + 512)


def test_dynamic_box(box_client: algokit_utils.ApplicationClient) -> None:
    txn_params = _params_with_boxes("dynamic_box", additional_refs=7)

    box_client.call("create_dynamic_box", transaction_parameters=txn_params)

    length = box_client.call("append_dynamic_box", times=0, transaction_parameters=txn_params)
    assert length.return_value == 0, "expected empty array"

    total = box_client.call("sum_dynamic_box", transaction_parameters=txn_params)
    expected_sum = 0
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    length = box_client.call("append_dynamic_box", times=5, transaction_parameters=txn_params)
    assert length.return_value == 5, "expected 5 items"

    total = box_client.call("sum_dynamic_box", transaction_parameters=txn_params)
    expected_sum = 1 * sum(range(5))
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    length = box_client.call("append_dynamic_box", times=5, transaction_parameters=txn_params)
    assert length.return_value == 10, "expected 10 items"

    total = box_client.call("sum_dynamic_box", transaction_parameters=txn_params)
    expected_sum = 2 * sum(range(5))
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    length = box_client.call("pop_dynamic_box", times=5, transaction_parameters=txn_params)
    assert length.return_value == 5, "expected 5 items"

    total = box_client.call("sum_dynamic_box", transaction_parameters=txn_params)
    expected_sum = 1 * sum(range(5))
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    # append until exceeding max stack array size
    for i in range(110):
        length = box_client.call("append_dynamic_box", times=5, transaction_parameters=txn_params)
        expected_items = 5 * (i + 2)
        assert length.return_value == expected_items, f"expected {expected_items} items"

    # use simulate to ignore large op budget requirements
    total_sim = simulate_call(box_client, "sum_dynamic_box", txn_params=txn_params)
    expected_sum = 111 * sum(range(5))
    assert (
        total_sim.abi_results[0].return_value == expected_sum
    ), f"expected sum to be {expected_sum}"

    # compare actual box contents too
    expected_array = list(range(5)) * 111
    box_response = box_client.algod_client.application_box_by_name(
        box_client.app_id, b"dynamic_box"
    )
    assert isinstance(box_response, dict)
    dynamic_box_bytes = base64.b64decode(box_response["value"])
    assert len(dynamic_box_bytes) > 4096, "expected box contents to exceed max stack value size"
    dynamic_box = algosdk.abi.ABIType.from_string("uint64[]").decode(dynamic_box_bytes)
    assert dynamic_box == expected_array, "expected box contents to be correct"

    box_client.call("write_dynamic_box", index=0, value=100, transaction_parameters=txn_params)
    total_sim = simulate_call(box_client, "sum_dynamic_box", txn_params=txn_params)
    expected_sum = 111 * sum(range(5)) + 100
    assert (
        total_sim.abi_results[0].return_value == expected_sum
    ), f"expected sum to be {expected_sum}"

    box_client.call("delete_dynamic_box", transaction_parameters=txn_params)


def test_nested_struct_box(box_client: algokit_utils.ApplicationClient) -> None:
    txn_params = _params_with_boxes("box", additional_refs=7)
    sp = box_client.algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 1_000 * 2
    txn_params.suggested_params = sp
    r = iter(range(1, 256))

    def n() -> int:
        return next(r)

    def inner() -> object:
        c, arr, d = (n() for _ in range(3))
        return [c, [[arr] * 4 for _ in range(3)], d]

    struct = [n(), inner(), [inner() for _ in range(3)], n()]
    assert n() < 100, "too many ints"

    atc = AtomicTransactionComposer()
    _add_op_up(box_client, atc)
    box_client.compose_call(
        atc, "set_nested_struct", struct=struct, transaction_parameters=txn_params
    )
    box_client.execute_atc(atc)
    response = box_client.call("nested_read", i1=1, i2=2, i3=3, transaction_parameters=txn_params)
    assert response.return_value == 33, "expected sum to be correct"

    box_client.call("nested_write", index=1, value=10, transaction_parameters=txn_params)
    txn_params.note = random.randbytes(8)
    response = box_client.call("nested_read", i1=1, i2=2, i3=3, transaction_parameters=txn_params)
    assert response.return_value == 60, "expected sum to be correct"

    # modify local struct to match expected modifications performed by nested_write
    struct[0] = 10  # a
    struct[3] = 11  # b
    inner_struct = struct[1]
    assert isinstance(inner_struct, list)
    inner_struct[1][1][1] = 12  # nested.arr_arr[1][1]
    inner_struct[0] = 13  # c
    inner_struct[2] = 14  # d
    woah_1 = struct[2][1]  # type: ignore[index]
    assert isinstance(woah_1, list)
    woah_1[1][1][1] = 15  # woah[1].arr_arr[1][1]

    # verify box contents
    box_response = box_client.algod_client.application_box_by_name(box_client.app_id, b"box")
    assert isinstance(box_response, dict)
    dynamic_box_bytes = base64.b64decode(box_response["value"])
    assert len(dynamic_box_bytes) > 4096, "expected box contents to exceed max stack value size"
    dynamic_box = algosdk.abi.ABIType.from_string(
        "(byte[4096],(uint64,(uint64,uint64[][],uint64),(uint64,uint64[][],uint64)[],uint64))"
    ).decode(dynamic_box_bytes)
    assert dynamic_box == [[0] * 4096, struct], "expected box contents to be correct"


def _add_op_up(client: ApplicationClient, atc: AtomicTransactionComposer) -> None:
    signer, sender = client.get_signer_sender()
    assert signer is not None
    assert sender is not None

    atc.add_transaction(
        TransactionWithSigner(
            transaction.ApplicationCallTxn(
                approval_program=b"\x06\x81\x01",
                clear_program=b"\x06\x81\x01",
                on_complete=OnComplete.DeleteApplicationOC,
                sender=sender,
                index=0,
                sp=client.algod_client.suggested_params(),
                note=random.randbytes(8),
            ),
            signer,
        )
    )


def test_dynamic_arr_in_struct_box(box_client: algokit_utils.ApplicationClient) -> None:
    txn_params = _params_with_boxes("dynamic_arr_struct", additional_refs=7)

    box_client.call("create_dynamic_arr_struct", transaction_parameters=txn_params)

    length = box_client.call(
        "append_dynamic_arr_struct", times=0, transaction_parameters=txn_params
    )
    assert length.return_value == 0, "expected empty array"

    total = box_client.call("sum_dynamic_arr_struct", transaction_parameters=txn_params)
    expected_sum = 3
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    length = box_client.call(
        "append_dynamic_arr_struct", times=5, transaction_parameters=txn_params
    )
    assert length.return_value == 5, "expected 5 items"

    total = box_client.call("sum_dynamic_arr_struct", transaction_parameters=txn_params)
    expected_sum = 3 + 1 * sum(range(5))
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    length = box_client.call(
        "append_dynamic_arr_struct", times=5, transaction_parameters=txn_params
    )
    assert length.return_value == 10, "expected 10 items"

    total = box_client.call("sum_dynamic_arr_struct", transaction_parameters=txn_params)
    expected_sum = 3 + 2 * sum(range(5))
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    length = box_client.call("pop_dynamic_arr_struct", times=5, transaction_parameters=txn_params)
    assert length.return_value == 5, "expected 5 items"

    total = box_client.call("sum_dynamic_arr_struct", transaction_parameters=txn_params)
    expected_sum = 3 + 1 * sum(range(5))
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    length = box_client.call("pop_dynamic_arr_struct", times=5, transaction_parameters=txn_params)
    assert length.return_value == 0, "expected 0 items"

    total = box_client.call("sum_dynamic_arr_struct", transaction_parameters=txn_params)
    expected_sum = 3
    assert total.return_value == expected_sum, f"expected sum to be {expected_sum}"

    # append until exceeding max stack array size
    num_appends = 111
    for i in range(num_appends):
        length = box_client.call(
            "append_dynamic_arr_struct", times=5, transaction_parameters=txn_params
        )
        expected_items = 5 * (i + 1)
        assert length.return_value == expected_items, f"expected {expected_items} items"

    # use simulate to ignore large op budget requirements
    total_sim = simulate_call(box_client, "sum_dynamic_arr_struct", txn_params=txn_params)
    expected_sum = 3 + num_appends * sum(range(5))
    assert (
        total_sim.abi_results[0].return_value == expected_sum
    ), f"expected sum to be {expected_sum}"

    # compare actual box contents too
    expected_array = list(range(5)) * 111
    box_response = box_client.algod_client.application_box_by_name(
        box_client.app_id, b"dynamic_arr_struct"
    )
    assert isinstance(box_response, dict)
    dynamic_box_bytes = base64.b64decode(box_response["value"])
    assert len(dynamic_box_bytes) > 4096, "expected box contents to exceed max stack value size"
    dynamic_box = algosdk.abi.ABIType.from_string("(uint64,uint64[],uint64,uint64[])").decode(
        dynamic_box_bytes
    )
    assert dynamic_box == [1, expected_array, 2, []], "expected box contents to be correct"

    box_client.call(
        "write_dynamic_arr_struct", index=0, value=100, transaction_parameters=txn_params
    )
    total_sim = simulate_call(box_client, "sum_dynamic_arr_struct", txn_params=txn_params)
    expected_sum = 3 + num_appends * sum(range(5)) + 100
    assert (
        total_sim.abi_results[0].return_value == expected_sum
    ), f"expected sum to be {expected_sum}"

    box_client.call("delete_dynamic_arr_struct", transaction_parameters=txn_params)


def test_too_many_bools(box_client: algokit_utils.ApplicationClient) -> None:
    txn_params = _params_with_boxes("too_many_bools", additional_refs=7)

    box_client.call("create_bools", transaction_parameters=txn_params)

    box_client.call("set_bool", index=0, value=True, transaction_parameters=txn_params)
    box_client.call("set_bool", index=42, value=True, transaction_parameters=txn_params)
    box_client.call("set_bool", index=500, value=True, transaction_parameters=txn_params)
    box_client.call("set_bool", index=32_999, value=True, transaction_parameters=txn_params)

    total = simulate_call(box_client, "sum_bools", stop_at_total=3, txn_params=txn_params)
    expected_sum = 3
    assert total.abi_results[0].return_value == expected_sum, f"expected sum to be {expected_sum}"

    box_response = box_client.algod_client.application_box_by_name(
        box_client.app_id, b"too_many_bools"
    )
    assert isinstance(box_response, dict)
    dynamic_box_bytes = base64.b64decode(box_response["value"])
    assert len(dynamic_box_bytes) > 4096, "expected box contents to exceed max stack value size"
    too_many_bools = [False] * 33_000
    too_many_bools[0] = True
    too_many_bools[42] = True
    too_many_bools[500] = True
    too_many_bools[32_999] = True
    # encode bools into bytes (as SDK is too slow)
    expected_bytes = sum(
        val << shift for shift, val in enumerate(reversed(too_many_bools))
    ).to_bytes(length=33_000 // 8)
    assert dynamic_box_bytes == expected_bytes, "expected box contents to be correct"


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
        compile_arc32(TEST_CASES_DIR / "compile", contract_name="HelloFactory")
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
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=200_000,
        ),
    )

    app_client.call("run_tests")

    response = app_client.call("nested_tuple_params", args=("Hello", (b"World", (123,))))

    assert bytes(response.return_value[0]) == b"World"
    assert response.return_value[1][0] == "Hello"
    assert response.return_value[1][1] == 123

    response = app_client.call("named_tuple", args=(1, b"2", "3"))
    assert response.return_value == [1, [50], "3"]

    response = app_client.call("nested_named_tuple_params", args=(1, 2, (3, b"4", "5")))
    assert response.return_value == [1, 2, [3, [52], "5"]]

    parent_with_list = (
        (123, 456, (789, b"abc", "def")),
        [(234, b"bcd", "efg")],
    )
    response = app_client.call("store_tuple", pwl=parent_with_list)
    assert response.confirmed_round, "expected store tuple to succeed"

    response = app_client.call("load_tuple")
    assert response.return_value == _map_native_to_algosdk(
        parent_with_list
    ), "expected load to match stored value"

    st = (123, 456)
    box_key = b"box" + b"".join(v.to_bytes(length=8) for v in st)

    with_box: algokit_utils.OnCompleteCallParametersDict = {"boxes": [(0, box_key)]}
    response = app_client.call("store_tuple_in_box", with_box, key=st)
    assert response.confirmed_round, "expected store tuple in box to succeed"

    response = app_client.call("is_tuple_in_box", with_box, key=st)
    assert response.return_value, "expected tuple to be in box"

    response = app_client.call("load_tuple_from_box", with_box, key=st)
    assert response.return_value == [st[0], st[1] + 1], "expected tuple to load from box"


def test_tuple_storage(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    example = TEST_CASES_DIR / "tuple_support" / "tuple_storage.py"
    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    # create
    app_client.create()
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=200_000,
        ),
    )
    with_box_ref: OnCompleteCallParametersDict = {"boxes": [(0, "box")]}
    app_client.opt_in("bootstrap", transaction_parameters=with_box_ref)

    val = 123
    app_client.call("mutate_tuple", val=val)
    tup_value = app_client.get_global_state(raw=True)[b"tup"]
    assert tup_value == _get_arc4_bytes("(uint64[],uint64)", ([0, val], 0))

    val = 234
    app_client.call("mutate_box", val=val, transaction_parameters=with_box_ref)
    box_state = algod_client.application_box_by_name(app_client.app_id, b"box")
    assert isinstance(box_state, dict)
    box_value = base64.b64decode(box_state["value"])
    assert box_value == _get_arc4_bytes("(uint64[],uint64)", ([0, val], 0))

    val = 2**64 - 1
    app_client.call("mutate_global", val=val)
    glob_value = app_client.get_global_state(raw=True)[b"glob"]
    assert glob_value == _get_arc4_bytes("(uint64[],uint64)", ([0, val], 0))

    val = 345
    app_client.call("mutate_local", val=val)
    loc_value = app_client.get_local_state(account.address, raw=True)[b"loc"]
    assert loc_value == _get_arc4_bytes("(uint64[],uint64)", ([0, val], 0))


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

    # order of argument evaluation check (with side effects)
    expected_log = (
        1,
        2,
        3,
    )
    expected_return = [2, 3, 1]
    result = app_client.call(call_abi_method="build_tuple_side_effects")
    assert result.return_value == expected_return

    result_logs_raw = result.tx_info["logs"]
    l1, l2, l3, _ = decode_logs(result_logs_raw, len(result_logs_raw) * "i")
    assert (l1, l2, l3) == expected_log


def test_uint_overflow(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        algokit_utils.ApplicationSpecification.from_json(
            compile_arc32(TEST_CASES_DIR / "arc4_types", contract_name="UIntOverflow")
        ),
        signer=account,
    )
    app_client.create()

    with pytest.raises(LogicError, match="overflow\t\t<-- Error"):
        app_client.call("test_uint8")

    with pytest.raises(LogicError, match="overflow\t\t<-- Error"):
        app_client.call("test_uint16")

    with pytest.raises(LogicError, match="overflow\t\t<-- Error"):
        app_client.call("test_uint32")

    with pytest.raises(LogicError, match="overflow\t\t<-- Error"):
        app_client.call("test_as_uint64")


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


def test_arc4_conversions(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    example = TEST_CASES_DIR / "arc4_conversions"

    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(example, contract_name="TestContract")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 10_000
    app_client.suggested_params = sp
    app_client.create()

    app_client.call("test_literal_encoding")
    app_client.call("test_native_encoding")
    app_client.call("test_arc4_encoding")
    app_client.call("test_array_uint64_encoding")
    app_client.call("test_array_static_encoding")
    app_client.call("test_array_dynamic_encoding")
    app_client.call("test_bytes_to_fixed", wrong_size=False)

    with pytest.raises(LogicError, match="invalid size\t\t<-- Error"):
        app_client.call("test_bytes_to_fixed", wrong_size=True)


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

    simulate_call(app_client, "test_array_assignment_maximum_cursage")

    simulate_call(app_client, "test_allocations", num=255)
    with pytest.raises(LogicError, match="no available slots\t\t<-- Error"):
        simulate_call(app_client, "test_allocations", num=256)

    with pytest.raises(LogicError, match="max array length exceeded\t\t<-- Error"):
        simulate_call(app_client, "test_array_too_long")

    simulate_call(app_client, "test_quicksort")
    simulate_call(app_client, "test_unobserved_write")


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
def test_immutable_array_init(
    algod_client: AlgodClient, optimization_level: int, account: algokit_utils.Account
) -> None:
    immutable_array_app = _get_immutable_array_init_app(algod_client, optimization_level, account)

    simulate_call(immutable_array_app, "test_immutable_array_init")

    simulate_call(immutable_array_app, "test_immutable_array_init_without_type_generic")

    simulate_call(immutable_array_app, "test_reference_array_init")

    simulate_call(immutable_array_app, "test_immutable_array_init_without_type_generic")


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

    response = simulate_call(
        immutable_array_app,
        "test_immutable_arc4",
        imm=[[1, 2], [3, 4], [5, 6]],
    )
    assert response.abi_results[0].return_value == [
        [1, 2],
        [3, 4],
        [1, 2],
    ]

    response = simulate_call(
        immutable_array_app,
        "test_imm_fixed_arr",
    )
    expected_imm_fixed_arr_value = [
        [2, 3],
        [2, 3],
        [2, 3],
    ]
    assert response.abi_results[0].return_value == expected_imm_fixed_arr_value
    assert _get_global_state(response, b"imm_fixed_arr") == _get_arc4_bytes(
        "(uint64,uint64)[3]",
        expected_imm_fixed_arr_value,
    )


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


@pytest.mark.parametrize(
    "value_to_hash",
    [
        b"123456",
        b"",
        b"HASHME",
        b"\x00" * 65,
    ],
)
def test_intrinsic_optimizations_implementation_correct(
    algod_client: AlgodClient, account: algokit_utils.Account, value_to_hash: bytes
) -> None:
    from Cryptodome.Hash import keccak

    example = TEST_CASES_DIR / "intrinsics" / "optimizations.py"

    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    response = app_client.call("all", value_to_hash=value_to_hash)
    sha256, sha3_256, sha512_256, keccak256 = (bytes(v) for v in response.return_value)
    assert sha256 == hashlib.sha256(value_to_hash).digest()
    assert sha3_256 == hashlib.sha3_256(value_to_hash).digest()
    assert sha512_256 == sha512_256_hash(value_to_hash)
    assert keccak256 == keccak.new(data=value_to_hash, digest_bits=256).digest()


@pytest.mark.parametrize("opt_level", [0, 1, 2])
def test_intrinsic_optimizations(
    algod_client: AlgodClient, account: algokit_utils.Account, opt_level: int
) -> None:
    from Cryptodome.Hash import keccak

    example = TEST_CASES_DIR / "intrinsics" / "optimizations.py"

    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(example, optimization_level=opt_level)
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    response = app_client.call("sha256")
    assert bytes(response.return_value) == hashlib.sha256(b"Hello World").digest()

    response = app_client.call("sha3_256")
    assert bytes(response.return_value) == hashlib.sha3_256(b"Hello World").digest()

    response = app_client.call("sha512_256")
    assert bytes(response.return_value) == sha512_256_hash(b"Hello World")

    response = app_client.call("keccak256")
    assert (
        bytes(response.return_value) == keccak.new(data=b"Hello World", digest_bits=256).digest()
    )


@pytest.fixture(scope="session")
def unauthorized(algod_client: AlgodClient) -> algokit_utils.Account:
    unauthorized = algokit_utils.Account.new_account()
    # ensure unauthorized has some funds
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=unauthorized,
            min_spending_balance_micro_algos=10_000,
        ),
    )
    return unauthorized


@pytest.mark.parametrize(
    "contract_name",
    [
        "Case1WithTups",
        "Case2WithImmStruct",
        "Case3WithStruct",
    ],
)
def test_mutable_native_types(
    algod_client: AlgodClient,
    contract_name: str,
    account: algokit_utils.Account,
    unauthorized: algokit_utils.Account,
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            TEST_CASES_DIR / "mutable_native_types",
            contract_name=contract_name,
        )
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    # ensure app meets minimum balance requirements
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=2_000_000,
        ),
    )

    boxes = [(0, "tup_bag")] * 5
    txn_params = algokit_utils.OnCompleteCallParameters(boxes=boxes)

    app_client.call("create_box", transaction_parameters=txn_params)

    response = app_client.call("num_tups", transaction_parameters=txn_params)
    assert response.return_value == 0

    fixed_array_size = 8
    tups = [[i + 1, i + 2] for i in range(fixed_array_size)]
    app_client.call("add_tup", tup=tups[0], transaction_parameters=txn_params)
    response = app_client.call("num_tups", transaction_parameters=txn_params)
    assert response.return_value == 1

    with pytest.raises(LogicError, match="sender not authorized"):
        app_client.call(
            "add_tup",
            tup=tups[0],
            transaction_parameters=algokit_utils.OnCompleteCallParameters(
                boxes=boxes,
                sender=unauthorized.address,
                signer=AccountTransactionSigner(unauthorized.private_key),
            ),
        )

    with pytest.raises(LogicError, match="not enough items"):
        app_client.call("get_3_tups", start=0, transaction_parameters=txn_params)

    app_client.call("add_fixed_tups", tups=tups[1:4], transaction_parameters=txn_params)
    response = app_client.call("num_tups", transaction_parameters=txn_params)
    assert response.return_value == 4

    response = app_client.call("get_3_tups", start=0, transaction_parameters=txn_params)
    assert response.return_value == [[i + 1, i + 2] for i in range(3)]

    app_client.call("add_many_tups", tups=tups[4:], transaction_parameters=txn_params)
    response = app_client.call("num_tups", transaction_parameters=txn_params)
    assert response.return_value == fixed_array_size

    response = app_client.call("get_all_tups", transaction_parameters=txn_params)
    assert response.return_value == [[i + 1, i + 2] for i in range(fixed_array_size)]

    with pytest.raises(LogicError, match="not enough items"):
        app_client.call("get_3_tups", start=6, transaction_parameters=txn_params)

    with pytest.raises(algokit_utils.LogicError, match="too many tups"):
        app_client.call("add_tup", tup=(1, 2), transaction_parameters=txn_params)

    for i in range(8):
        response = app_client.call("get_tup", index=i, transaction_parameters=txn_params)
        assert response.return_value == tups[i]

    with pytest.raises(algokit_utils.LogicError, match="index out of bounds"):
        app_client.call("get_tup", index=8, transaction_parameters=txn_params)

    response = app_client.call("sum", transaction_parameters=txn_params)
    assert response.return_value == sum(i + 1 + i + 2 for i in range(fixed_array_size))

    app_client.call("set_a", a=1, transaction_parameters=txn_params)

    response = app_client.call("sum", transaction_parameters=txn_params)
    assert response.return_value == sum(1 + i + 2 for i in range(fixed_array_size))

    app_client.call("set_b", b=1, transaction_parameters=txn_params)

    response = app_client.call("sum", transaction_parameters=txn_params)
    assert response.return_value == sum(1 + 1 for _ in range(fixed_array_size))

    response = app_client.call("get_3_tups", start=5, transaction_parameters=txn_params)
    assert response.return_value == [[1, 1] for _ in range(3)]


def test_mutable_native_types_abi_call(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            TEST_CASES_DIR / "mutable_native_types",
            contract_name="TestAbiCall",
        )
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 1_000 * 7
    large_fee_txn_params = algokit_utils.OnCompleteCallParameters(
        suggested_params=sp,
    )

    app_client.call("test_fixed_struct", transaction_parameters=large_fee_txn_params)
    app_client.call("test_nested_struct", transaction_parameters=large_fee_txn_params)
    app_client.call("test_dynamic_struct", transaction_parameters=large_fee_txn_params)
    app_client.call("test_fixed_array", transaction_parameters=large_fee_txn_params)
    app_client.call("test_native_array", transaction_parameters=large_fee_txn_params)

    sp.fee = 1_000 * 9
    app_client.call("test_log", transaction_parameters=large_fee_txn_params)


def test_mutable_native_types_contract(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            TEST_CASES_DIR / "mutable_native_types",
            contract_name="Contract",
        )
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    app_client.call("test_arr", arr=[])
    app_client.call("test_imm_fixed_array")

    response = app_client.call("test_match_struct", arg=[1, 2])
    assert response.return_value is True

    response = app_client.call("test_match_struct", arg=[2, 1])
    assert response.return_value is False


# see https://github.com/algorandfoundation/puya-ts-demo/blob/main/contracts/marketplace/marketplace.test.ts
def test_marketplace_with_tups(
    algod_client: AlgodClient, account: algokit_utils.Account, asset_a: int
) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            TEST_CASES_DIR / "marketplace_demo", contract_name="DigitalMarketplaceWithTups"
        )
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    create_response = app_client.create()
    assert create_response.confirmed_round

    sp = algod_client.suggested_params()

    # ensure app meets minimum balance requirements
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=100_000,
        ),
    )

    # optin to receive asset.
    optin_txn = TransactionWithSigner(
        txn=algosdk.transaction.PaymentTxn(
            sender=account.address,
            receiver=app_client.app_address,
            amt=100_000,
            note=b"minimum balance to optin to an asset",
            sp=sp,
        ),
        signer=account.signer,
    )
    app_client.call(
        "allowAsset",
        mbr_pay=optin_txn,
        asset=asset_a,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            suggested_params=suggested_params(algod_client=algod_client, fee=1_000),
            # TODO: use populate resources feature after upgrading algokit_utils
            foreign_assets=[asset_a],
        ),
    )

    # test parameters for the application call.
    nonce = 1
    unitary_price = 1
    deposited = 10

    # create the payment and asset transfer transactions which will be run as part of the
    # same transaction group as the application call.
    mbr_pay = TransactionWithSigner(
        txn=algosdk.transaction.PaymentTxn(
            sender=account.address,
            receiver=app_client.app_address,
            amt=50500,
            note=b"firstDeposit payment",
            sp=sp,
        ),
        signer=account.signer,
    )
    xfer = TransactionWithSigner(
        txn=algosdk.transaction.AssetTransferTxn(
            account.address, sp, app_client.app_address, deposited, asset_a
        ),
        signer=account.signer,
    )

    # The application call needs to know which boxes will be used.
    box_key = b"listings" + _get_arc4_bytes(
        "(address,uint64,uint64)", (account.address, asset_a, nonce)
    )
    transaction_parameters = _params_with_boxes(1, box_key)

    # make the app call
    app_client.call(
        "firstDeposit",
        mbr_pay=mbr_pay,
        xfer=xfer,
        unitary_price=unitary_price,
        nonce=nonce,
        transaction_parameters=transaction_parameters,
    )

    # Assert (original test only checks the deposited value is as expected, it should check more)
    box_state = algod_client.application_box_by_name(app_client.app_id, box_key)
    assert isinstance(box_state, dict)
    box_value = base64.b64decode(box_state["value"])
    assert int.from_bytes(box_value[:8]) == deposited


def test_bool_only(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            TEST_CASES_DIR / "regression_tests",
            contract_name="BoolOnly",
        )
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    resposne = app_client.call("set_0_convert", inp=b"\x00")
    assert resposne.return_value == [2**7]
    resposne = app_client.call("set_0_compare", inp=b"\x00")
    assert resposne.return_value == [2**7]

    sp = algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 1_000 * 4
    fees = algokit_utils.OnCompleteCallParameters(
        suggested_params=sp,
    )

    # ensure app meets minimum balance requirements
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=100_000,
        ),
    )
    app_client.call("bool_only_properties", transaction_parameters=fees)


@pytest.fixture(scope="session")
def arc4_validation_client(
    algod_client: AlgodClient, account: algokit_utils.Account
) -> ApplicationClient:
    app_spec = algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(TEST_CASES_DIR / "arc4_validation")
    )
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()
    return app_client


def _invalid_size(type_name: str) -> str:
    return f"invalid number of bytes for {type_name}"


def _invalid_arr_size(element_type_name: str, size: int | None = None) -> str:
    if size is None:
        return _invalid_size(f"arc4.dynamic_array<{element_type_name}>")
    else:
        return _invalid_size(f"arc4.static_array<{element_type_name}, {size}>")


_VALID_DYNAMIC_STRUCT_BYTES = b"\x00" * 9 + b"\x00\x0b\x00\x00"
_INVALID_DYNAMIC_STRUCT_BYTES = b"\x00" * 9 + b"\x00\x0b\x00\x01"
_STATIC_STRUCT = "test_cases.arc4_validation.contract.ARC4StaticStruct"
_DYNAMIC_STRUCT = "test_cases.arc4_validation.contract.ARC4DynamicStruct"


@pytest.mark.parametrize(
    ("type_name", "size_or_bytes_value", "expected_error"),
    [
        ("uint64", 8, None),
        ("uint64", 7, _invalid_size("arc4.uint64")),
        ("ufixed64", 8, None),
        ("ufixed64", 7, _invalid_size("arc4.ufixed64x2")),
        ("uint8", 1, None),
        ("uint8", 2, _invalid_size("arc4.uint8")),
        ("bool", 1, None),
        ("bool", 2, _invalid_size("arc4.bool")),
        ("byte", 1, None),
        ("byte", 2, _invalid_size("arc4.uint8")),
        ("string", 2, None),
        ("string", (4, b"\x00" * 4), None),
        ("string", 5, _invalid_arr_size("arc4.uint8")),
        ("bytes", 2, None),
        ("bytes", (4, b"\x00" * 4), None),
        ("bytes", 5, _invalid_arr_size("arc4.uint8")),
        ("address", 32, None),
        ("address", 0, _invalid_arr_size("arc4.uint8", 32)),
        ("address", 33, _invalid_arr_size("arc4.uint8", 32)),
        ("account", 32, None),
        ("account", 0, _invalid_arr_size("arc4.uint8", 32)),
        ("account", 33, _invalid_arr_size("arc4.uint8", 32)),
        ("uint512", 64, None),
        ("uint512", 63, _invalid_size("arc4.uint512")),
        ("uint8_arr", 2, None),
        ("uint8_arr", b"\x00\x01\x00", None),
        ("uint8_arr", 1, "invalid array length header"),
        ("uint8_arr", 3, _invalid_arr_size("arc4.uint8")),
        ("uint8_arr3", 3, None),
        ("uint8_arr3", 1, _invalid_arr_size("arc4.uint8", 3)),
        ("uint8_arr3", 4, _invalid_arr_size("arc4.uint8", 3)),
        ("bool_arr", b"\x00\x00", None),
        ("bool_arr", b"\x00\x01\x00", None),
        ("bool_arr", b"\x00\x08\x00", None),
        ("bool_arr", b"\x00\x0a\x00\x00", None),
        ("bool_arr", b"\x00\x01", _invalid_arr_size("arc4.bool")),
        ("bool_arr", b"\x00\x09\x00", _invalid_arr_size("arc4.bool")),
        ("static_struct", 9, None),
        ("static_struct", 8, _invalid_size(_STATIC_STRUCT)),
        ("dynamic_struct", 0, "invalid tuple encoding"),
        ("dynamic_struct", _VALID_DYNAMIC_STRUCT_BYTES, None),
        ("dynamic_struct", 11, "invalid tail pointer"),
        ("dynamic_struct", _INVALID_DYNAMIC_STRUCT_BYTES, _invalid_size(_DYNAMIC_STRUCT)),
        ("static_tuple", 9, None),
        ("static_tuple", 8, _invalid_size("arc4.tuple<arc4.uint64,arc4.uint8>")),
        ("dynamic_tuple", 0, "invalid tuple encoding"),
        ("dynamic_tuple", _VALID_DYNAMIC_STRUCT_BYTES, None),
        ("dynamic_tuple", 11, "invalid tail pointer"),
        (
            "dynamic_tuple",
            _INVALID_DYNAMIC_STRUCT_BYTES,
            _invalid_size("arc4.tuple<arc4.uint64,arc4.uint8,arc4.dynamic_array<arc4.uint8>>"),
        ),
        ("static_struct_arr", b"\x00\x03" + b"\x00" * 27, None),
        ("static_struct_arr", 0, "invalid array length header"),
        ("static_struct_arr", 1, "invalid array length header"),
        ("static_struct_arr", 29, _invalid_arr_size(_STATIC_STRUCT)),
        ("static_struct_arr3", 27, None),
        ("static_struct_arr3", 26, _invalid_arr_size(_STATIC_STRUCT, 3)),
        ("dynamic_struct_arr", 2, None),
        (
            "dynamic_struct_arr",
            (
                2,  # len
                4,  # ptr 1
                4 + len(_VALID_DYNAMIC_STRUCT_BYTES),  # ptr 2
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            None,
        ),
        ("dynamic_struct_arr", 0, "invalid array length header"),
        ("dynamic_struct_arr", 1, "invalid array length header"),
        ("dynamic_struct_arr", 29, _invalid_arr_size(_DYNAMIC_STRUCT)),
        ("dynamic_struct_imm_arr", 0, "invalid array length header"),
        ("dynamic_struct_imm_arr", 1, "invalid array length header"),
        (
            "dynamic_struct_imm_arr",
            29,
            _invalid_arr_size("test_cases.arc4_validation.contract.ARC4FrozenDynamicStruct"),
        ),
        ("dynamic_struct_arr3", 27, "invalid tail pointer"),
        (
            "dynamic_struct_arr3",
            (
                6,
                6,
                6,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            # invalid tuple encoding because the offsets result in a 0-length read of the 1st tuple
            "invalid tuple encoding",
        ),
        (
            "dynamic_struct_arr3",
            0,
            "invalid array encoding",
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            None,
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _INVALID_DYNAMIC_STRUCT_BYTES,
            ),
            _invalid_arr_size(_DYNAMIC_STRUCT, 3),
        ),
    ],
)
def test_arc4_validation(
    arc4_validation_client: ApplicationClient,
    type_name: str,
    size_or_bytes_value: bytes | int | list[bytes | int],
    expected_error: str | None,
) -> None:
    if isinstance(size_or_bytes_value, bytes):
        bytes_value = size_or_bytes_value
    elif isinstance(size_or_bytes_value, int):
        bytes_value = b"\x00" * size_or_bytes_value
    else:
        bytes_value = b"".join(
            b if isinstance(b, bytes) else b.to_bytes(length=2) for b in size_or_bytes_value
        )
    ctx = (
        pytest.raises(LogicError, match=re.escape(expected_error) + r"[^\n]*<-- Error")
        if expected_error is not None
        else contextlib.nullcontext()
    )
    with ctx:
        arc4_validation_client.call(f"validate_{type_name}", value=bytes_value)


_NATIVE_STATIC_STRUCT = "test_cases.arc4_validation.contract.NativeStaticStruct"
_NATIVE_DYNAMIC_STRUCT = "test_cases.arc4_validation.contract.NativeDynamicStruct"


@pytest.mark.parametrize(
    ("type_name", "size_or_bytes_value", "expected_error"),
    [
        ("static_struct", 9, None),
        ("static_struct", 8, _invalid_size(_NATIVE_STATIC_STRUCT)),
        ("dynamic_struct", 0, "invalid tuple encoding"),
        ("dynamic_struct", _VALID_DYNAMIC_STRUCT_BYTES, None),
        ("dynamic_struct", 11, "invalid tail pointer"),
        ("dynamic_struct", _INVALID_DYNAMIC_STRUCT_BYTES, _invalid_size(_NATIVE_DYNAMIC_STRUCT)),
        ("static_struct_arr", b"\x00\x03" + b"\x00" * 27, None),
        ("static_struct_arr", 0, "invalid array length header"),
        ("static_struct_arr", 1, "invalid array length header"),
        ("static_struct_arr", 29, _invalid_arr_size(_NATIVE_STATIC_STRUCT)),
        ("static_struct_arr3", 27, None),
        ("static_struct_arr3", 26, _invalid_arr_size(_NATIVE_STATIC_STRUCT, 3)),
        ("dynamic_struct_arr", 2, None),
        (
            "dynamic_struct_arr",
            (
                2,  # len
                4,  # ptr 1
                4 + len(_VALID_DYNAMIC_STRUCT_BYTES),  # ptr 2
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            None,
        ),
        ("dynamic_struct_arr", 0, "invalid array length header"),
        ("dynamic_struct_arr", 1, "invalid array length header"),
        ("dynamic_struct_arr", 29, _invalid_arr_size(_NATIVE_DYNAMIC_STRUCT)),
        ("dynamic_struct_arr3", 27, "invalid tail pointer"),
        (
            "dynamic_struct_arr3",
            (
                6,
                6,
                6,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            "invalid tuple encoding",
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            None,
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _INVALID_DYNAMIC_STRUCT_BYTES,
            ),
            _invalid_arr_size(_NATIVE_DYNAMIC_STRUCT, 3),
        ),
    ],
)
def test_native_validation(
    arc4_validation_client: ApplicationClient,
    type_name: str,
    size_or_bytes_value: bytes | int | list[bytes | int],
    expected_error: str | None,
) -> None:
    if isinstance(size_or_bytes_value, bytes):
        bytes_value = size_or_bytes_value
    elif isinstance(size_or_bytes_value, int):
        bytes_value = b"\x00" * size_or_bytes_value
    else:
        bytes_value = b"".join(
            b if isinstance(b, bytes) else b.to_bytes(length=2) for b in size_or_bytes_value
        )
    ctx = (
        pytest.raises(LogicError, match=re.escape(expected_error) + r"[^\n]*<-- Error")
        if expected_error is not None
        else contextlib.nullcontext()
    )
    with ctx:
        arc4_validation_client.call(f"validate_native_{type_name}", value=bytes_value)


def _get_immutable_array_app(
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
) -> ApplicationClient:
    example = TEST_CASES_DIR / "array" / "immutable.py"
    return _get_app_client(
        example,
        algod_client,
        optimization_level,
        account,
        # disable validation at O0 as it is too expensive
        validate_abi_values=optimization_level != 0,
    )


def _get_immutable_array_init_app(
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
) -> ApplicationClient:
    example = TEST_CASES_DIR / "array" / "immutable-init.py"
    return _get_app_client(example, algod_client, optimization_level, account)


def _get_app_client(
    example: Path,
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
    *,
    validate_abi_values: bool = True,
) -> ApplicationClient:
    app_spec = _get_app_spec(example, optimization_level, validate_abi_values=validate_abi_values)
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create(transaction_parameters={"note": random.randbytes(8)})

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
    app_spec_path: Path, optimization_level: int, *, validate_abi_values: bool = True
) -> algokit_utils.ApplicationSpecification:
    return algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            app_spec_path,
            optimization_level=optimization_level,
            disabled_optimizations=() if optimization_level else ("remove_unused_variables",),
            validate_abi_values=validate_abi_values,
        )
    )


def simulate_call(
    app_client: algokit_utils.ApplicationClient,
    method: str,
    extra_budget: int = 20_000,
    txn_params: OnCompleteCallParametersDict | OnCompleteCallParameters | None = None,
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


def _map_native_to_algosdk(value: object) -> object:
    # algosdk decoding represents some types differently than their equivalent unencoded types
    # handle those conversions here
    if isinstance(value, str):
        # explicitly return strings unmodified before doing sequence conversions
        return value
    if isinstance(value, bytes):
        # bytes are a sequence of ints
        return list(value)
    if isinstance(value, Sequence):
        # convert tuples to list, as well as recursing into any sequence elements
        return [_map_native_to_algosdk(v) for v in value]
    return value
