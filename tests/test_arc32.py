import math
import random
from pathlib import Path

import algokit_utils
import algokit_utils.config
import algosdk
import pytest
from algokit_utils import LogicError
from algosdk import abi, constants, transaction
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk.transaction import OnComplete
from algosdk.v2client.algod import AlgodClient
from nacl.signing import SigningKey
from puya.arc32 import create_arc32_json
from puya.models import CompiledContract

from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.test_execution import decode_logs
from tests.utils import compile_src
from tests.utils.merkle_tree import MerkleTree, sha_256_raw

pytestmark = pytest.mark.localnet


def compile_arc32(src_path: Path, *, optimization_level: int = 1, debug_level: int = 2) -> str:
    result = compile_src(src_path, optimization_level=optimization_level, debug_level=debug_level)
    ((contract,),) = result.teal.values()
    assert isinstance(contract, CompiledContract), "Compilation artifact must be a contract"
    return create_arc32_json(contract)


@pytest.fixture()
def user_account() -> algokit_utils.Account:
    private_key, address = algosdk.account.generate_account()
    return algokit_utils.Account(private_key=private_key, address=address)


@pytest.fixture()
def funded_user_account(algod_client: AlgodClient) -> algokit_utils.Account:
    private_key, address = algosdk.account.generate_account()
    user = algokit_utils.Account(private_key=private_key, address=address)
    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=user,
            min_spending_balance_micro_algos=1_000_000,
        ),
    )
    return user


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


@pytest.fixture()
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

    quorum = math.ceil(random.randint(1, 9) * 1000)  # noqa: S311
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


def test_state_proxies(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    example = TEST_CASES_DIR / "state_proxies" / "contract.py"

    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)

    app_client.create(transaction_parameters={"on_complete": OnComplete.OptInOC})
    assert app_client.get_global_state() == {"g1": 1, "g2": 0}
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
        call_abi_method="verify", leaf=sha_256_raw(b"a"), proof=test_tree.get_proof(b"a")
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
        "test_native_tuple",
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


def test_arc28(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        algokit_utils.ApplicationSpecification.from_json(compile_arc32(EXAMPLES_DIR / "arc-28")),
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


@pytest.fixture()
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
    algod_client: AlgodClient, account: algokit_utils.Account, other_account: algokit_utils.Account
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
    }[
        winner_index  # type: ignore[index]
    ]
    return board, winner


def test_dynamic_arrays(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    app_client = algokit_utils.ApplicationClient(
        algod_client,
        algokit_utils.ApplicationSpecification.from_json(
            compile_arc32(TEST_CASES_DIR / "arc4_dynamic_arrays")
        ),
        signer=account,
    )
    app_client.create()

    string1 = "a"
    string2 = "bee"
    string3 = "Hello World"
    uint1 = 3
    uint2 = 2**42

    # static
    static_struct_t = abi.ABIType.from_string("(uint64,byte[2])")
    static_arr_t = abi.ArrayDynamicType(static_struct_t)
    static_struct0 = (uint1, bytes((4, 5)))
    static_struct1 = (uint2, bytes((42, 255)))

    static_result = app_client.call("test_static_elements")
    (static_arr_bytes, static_0_bytes, static_1_bytes) = decode_logs(
        static_result.tx_info["logs"], "bbb"
    )

    assert static_arr_bytes == static_arr_t.encode([static_struct0, static_struct1])
    assert static_0_bytes == static_struct_t.encode(static_struct0)
    assert static_1_bytes == static_struct_t.encode(static_struct1)

    # dynamic
    dynamic_struct_t = abi.ABIType.from_string("(string,string)")
    dynamic_arr_t = abi.ABIType.from_string("(string,string)[]")
    dynamic_struct0 = (string1, string2)
    dynamic_struct1 = (string3, string1)

    dynamic_result = app_client.call("test_dynamic_elements")
    (dynamic_arr_bytes, dynamic_0_bytes, dynamic_1_bytes) = decode_logs(
        dynamic_result.tx_info["logs"], "bbb"
    )

    assert dynamic_arr_bytes == dynamic_arr_t.encode([dynamic_struct0, dynamic_struct1])
    assert dynamic_0_bytes == dynamic_struct_t.encode(dynamic_struct0)
    assert dynamic_1_bytes == dynamic_struct_t.encode(dynamic_struct1)

    # mixed single dynamic
    mixed1_struct_t = abi.ABIType.from_string("(uint64,string,uint64)")
    mixed1_arr_t = abi.ArrayDynamicType(mixed1_struct_t)
    mixed1_struct0 = (uint1, string1, uint2)
    mixed1_struct1 = (uint2, string2, uint1)

    mixed_single_result = app_client.call("test_mixed_single_dynamic_elements")
    (mixed1_arr_bytes, mixed1_0_bytes, mixed1_1_bytes) = decode_logs(
        mixed_single_result.tx_info["logs"], "bbb"
    )

    assert mixed1_arr_bytes == mixed1_arr_t.encode([mixed1_struct0, mixed1_struct1])
    assert mixed1_0_bytes == mixed1_struct_t.encode(mixed1_struct0)
    assert mixed1_1_bytes == mixed1_struct_t.encode(mixed1_struct1)

    # mixed multiple dynamic
    mixed2_struct_t = abi.ABIType.from_string("(uint64,string,uint64,string,uint64)")
    mixed2_arr_t = abi.ArrayDynamicType(mixed2_struct_t)
    mixed2_struct0 = (uint1, string1, uint2, string2, uint1)
    mixed2_struct1 = (uint2, string3, uint1, string1, uint2)

    mixed_multiple_result = app_client.call("test_mixed_multiple_dynamic_elements")
    (mixed2_arr_bytes, mixed2_0_bytes, mixed2_1_bytes) = decode_logs(
        mixed_multiple_result.tx_info["logs"], "bbb"
    )

    assert mixed2_arr_bytes == mixed2_arr_t.encode([mixed2_struct0, mixed2_struct1])
    assert mixed2_0_bytes == mixed2_struct_t.encode(mixed2_struct0)
    assert mixed2_1_bytes == mixed2_struct_t.encode(mixed2_struct1)
