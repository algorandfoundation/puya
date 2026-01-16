import base64
import math
import random
from collections.abc import Callable, Sequence
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

from puya.arc56 import create_arc56_json
from puya.compilation_artifacts import CompiledContract
from puyapy.options import PuyaPyOptions
from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.test_execution import decode_logs
from tests.utils import compile_src_from_options

pytestmark = pytest.mark.localnet


def compile_arc32(
    src_path: Path,
    *,
    optimization_level: int = 1,
    debug_level: int = 2,
    contract_name: str | None = None,
    disabled_optimizations: Sequence[str] = (),
    validate_abi_args: bool = True,
) -> str:
    result = compile_src_from_options(
        PuyaPyOptions(
            paths=(src_path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
            optimizations_override={o: False for o in disabled_optimizations},
            validate_abi_args=validate_abi_args,
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


def test_dynamic_itxn_group(algod_client: AlgodClient, account: algokit_utils.Account) -> None:
    example = TEST_CASES_DIR / "dynamic_itxn_group" / "contract.py"
    verifier = TEST_CASES_DIR / "dynamic_itxn_group" / "verifier.py"

    app_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(example))
    app_client = algokit_utils.ApplicationClient(algod_client, app_spec, signer=account)
    app_client.create()

    verifier_spec = algokit_utils.ApplicationSpecification.from_json(compile_arc32(verifier))
    verifier_client = algokit_utils.ApplicationClient(algod_client, verifier_spec, signer=account)
    verifier_client.create()

    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client.app_address,
            min_spending_balance_micro_algos=400_000,
        ),
    )

    def create_funded_account() -> algokit_utils.Account:
        a_key_address = algosdk.account.generate_account()
        acc = algokit_utils.Account(private_key=a_key_address[0], address=a_key_address[1])
        algokit_utils.ensure_funded(
            algod_client,
            parameters=algokit_utils.EnsureBalanceParameters(
                account_to_fund=acc, min_spending_balance_micro_algos=400_000
            ),
        )
        return acc

    test_accounts = [create_funded_account() for _ in range(4)]
    pay_fields = {
        "sender": account.address,
        "amt": 900_000,
        "receiver": app_client.app_address,
        "note": b"minimum balance to optin to an asset",
        "sp": algod_client.suggested_params(),
    }

    def args() -> dict[str, object]:
        return {
            "addresses": [a.public_key for a in test_accounts],
            "funds": TransactionWithSigner(
                algosdk.transaction.PaymentTxn(**pay_fields),
                signer=account.signer,
            ),
            "verifier": verifier_client.app_id,
            "transaction_parameters": algokit_utils.OnCompleteCallParameters(
                suggested_params=suggested_params(
                    algod_client=algod_client, fee=100_000, flat_fee=True
                ),
                accounts=[a.address for a in test_accounts],
                foreign_apps=[verifier_client.app_id],
            ),
        }

    app_client.call("test_firstly", **args())  # type: ignore[call-overload]
    app_client.call("test_looply", **args())  # type: ignore[call-overload]
    app_client.call("test_firstly_abi_call", **args())  # type: ignore[call-overload]
    app_client.call("test_looply_abi_call", **args())  # type: ignore[call-overload]


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

    with pytest.raises(algokit_utils.logic_error.LogicError, match="assert failed"):
        app_client.update()

    app_client.delete()


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
    transaction_parameters = algokit_utils.OnCompleteCallParameters(
        boxes=[(0, (1).to_bytes(8)), (0, box_key)]
    )

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


def _get_app_client(
    example: Path,
    algod_client: AlgodClient,
    optimization_level: int,
    account: algokit_utils.Account,
    *,
    validate_abi_args: bool = True,
) -> ApplicationClient:
    app_spec = _get_app_spec(example, optimization_level, validate_abi_args=validate_abi_args)
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
    app_spec_path: Path, optimization_level: int, *, validate_abi_args: bool = True
) -> algokit_utils.ApplicationSpecification:
    return algokit_utils.ApplicationSpecification.from_json(
        compile_arc32(
            app_spec_path,
            optimization_level=optimization_level,
            disabled_optimizations=() if optimization_level else ("remove_unused_variables",),
            validate_abi_args=validate_abi_args,
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
