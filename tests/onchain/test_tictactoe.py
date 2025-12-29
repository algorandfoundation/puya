import random

import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer


def test_tictactoe(deployer: Deployer) -> None:
    algorand = deployer.localnet
    host_account = deployer.account

    # Create challenger account
    challenger_account = algorand.account.random()
    algorand.account.ensure_funded(
        account_to_fund=challenger_account.addr,
        dispenser_account=host_account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(10_000_000),
    )

    # Create host client
    client_host = deployer.create(
        EXAMPLES_DIR / "tictactoe" / "tictactoe.py",
        method="new_game",
        args={"move": (0, 0)},
    ).client

    turn_result = client_host.send.call(
        au.AppClientMethodCallParams(method="whose_turn", note=random.randbytes(8))
    )
    assert turn_result.abi_return == 2

    # No one has joined, can start a new game
    client_host.send.call(
        au.AppClientMethodCallParams(method="new_game", args=[(1, 1)], note=random.randbytes(8))
    )

    # Host tries to play, but it's challenger's turn
    with pytest.raises(au.LogicError, match="It is the challenger's turn"):
        client_host.send.call(
            au.AppClientMethodCallParams(method="play", args=[(0, 0)], note=random.randbytes(8))
        )

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "- - -",
        "- X -",
        "- - -",
    ]
    assert winner is None

    # Get challenger client using factory
    challenger_client = au.AppClient(
        au.AppClientParams(
            algorand=algorand,
            app_spec=client_host.app_spec,
            app_id=client_host.app_id,
            default_sender=challenger_account.addr,
            default_signer=challenger_account.signer,
        )
    )

    challenger_client.send.call(
        au.AppClientMethodCallParams(method="join_game", args=[(0, 0)], note=random.randbytes(8))
    )

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O - -",
        "- X -",
        "- - -",
    ]
    assert winner is None

    turn_result = challenger_client.send.call(
        au.AppClientMethodCallParams(method="whose_turn", note=random.randbytes(8))
    )
    assert turn_result.abi_return == 1

    # Can't start new game while game in progress
    with pytest.raises(au.LogicError, match="Game isn't over"):
        client_host.send.call(
            au.AppClientMethodCallParams(
                method="new_game", args=[(2, 2)], note=random.randbytes(8)
            )
        )

    client_host.send.call(
        au.AppClientMethodCallParams(method="play", args=[(0, 1)], note=random.randbytes(8))
    )

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O - -",
        "X X -",
        "- - -",
    ]
    assert winner is None

    challenger_client.send.call(
        au.AppClientMethodCallParams(method="play", args=[(1, 0)], note=random.randbytes(8))
    )

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O O -",
        "X X -",
        "- - -",
    ]
    assert winner is None

    client_host.send.call(
        au.AppClientMethodCallParams(method="play", args=[(2, 1)], note=random.randbytes(8))
    )

    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "O O -",
        "X X X",
        "- - -",
    ]
    assert winner == "Host"

    client_host.send.call(
        au.AppClientMethodCallParams(method="new_game", args=[(1, 1)], note=random.randbytes(8))
    )
    game, winner = _get_tic_tac_toe_game_status(client_host)
    assert game == [
        "- - -",
        "- X -",
        "- - -",
    ]
    assert winner is None


def _get_tic_tac_toe_game_status(client: au.AppClient) -> tuple[list[str], str | None]:
    state = client.get_global_state()
    game_value = state.get("game")
    assert game_value is not None
    game_bytes = game_value.value_raw
    assert isinstance(game_bytes, bytes)
    chars = ["X" if b == 1 else "O" if b == 2 else "-" for b in game_bytes]
    board = [" ".join(chars[:3]), " ".join(chars[3:6]), " ".join(chars[6:])]

    winner_value = state.get("winner")
    if winner_value is None:
        winner = None
    else:
        winner_bytes = winner_value.value_raw
        assert isinstance(winner_bytes, bytes)
        winner = {
            b"\01": "Host",
            b"\02": "Challenger",
            b"\03": "Draw",
        }.get(winner_bytes)
    return board, winner
