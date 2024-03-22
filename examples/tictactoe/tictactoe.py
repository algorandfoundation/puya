# ruff: noqa: PT018
import typing

from puyapy import Account, GlobalState, Txn, UInt64, arc4, op, subroutine

Row: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[3]]
Game: typing.TypeAlias = arc4.StaticArray[Row, typing.Literal[3]]
Move: typing.TypeAlias = tuple[UInt64, UInt64]
EMPTY = 0
HOST = 1
CHALLENGER = 2
DRAW = 3


class TicTacToeContract(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.challenger = GlobalState(Account)
        self.winner = GlobalState(arc4.UInt8)

    @arc4.abimethod(create="allow")
    def new_game(self, move: Move) -> None:
        if Txn.application_id:
            # if a challenger has joined, don't allow starting a new game
            # until this one is complete
            if self.challenger:
                assert self.winner, "Game isn't over"
            # reset challenger and winner
            del self.challenger.value
            del self.winner.value
        self.host = Txn.sender
        self.game = Game.from_bytes(op.bzero(9))
        column, row = move
        assert column < 3 and row < 3, "Move must be in range"
        self.game[row][column] = arc4.UInt8(HOST)
        self.turns = UInt64(0)

    @arc4.abimethod
    def join_game(self, move: Move) -> None:
        assert not self.challenger, "Host already has a challenger"
        self.challenger.value = Txn.sender
        self.make_move(arc4.UInt8(CHALLENGER), move)

    @arc4.abimethod
    def whose_turn(self) -> arc4.UInt8:
        return arc4.UInt8(HOST) if self.turns % 2 else arc4.UInt8(CHALLENGER)

    @arc4.abimethod
    def play(self, move: Move) -> None:
        assert not self.winner, "Game is already finished"
        if self.turns % 2:
            assert Txn.sender == self.host, "It is the host's turn"
            player = arc4.UInt8(HOST)
        else:
            assert Txn.sender == self.challenger.get(
                default=Account()
            ), "It is the challenger's turn"
            player = arc4.UInt8(CHALLENGER)
        self.make_move(player, move)

    @subroutine
    def make_move(self, player: arc4.UInt8, move: Move) -> None:
        column, row = move
        assert column < 3 and row < 3, "Move must be in range"
        assert self.game[row][column] == EMPTY, "Square is already taken"
        self.game[row][column] = player
        self.turns += 1
        if self.did_win(player, column=column, row=row):
            self.winner.value = player
        elif self.turns == 9:
            self.winner.value = arc4.UInt8(DRAW)

    @subroutine
    def did_win(self, player: arc4.UInt8, column: UInt64, row: UInt64) -> bool:
        g = self.game.copy()

        if g[row][0] == g[row][1] == g[row][2]:
            return True

        if g[0][column] == g[1][column] == g[2][column]:
            return True

        # if player owns center, check diagonals
        if player == g[1][1]:
            if g[0][0] == player == g[2][2]:
                return True
            if g[0][2] == player == g[2][0]:
                return True
        return False
