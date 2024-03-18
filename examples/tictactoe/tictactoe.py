import typing

from puyapy import Global, Txn, UInt64, arc4, op, subroutine, urange

Row: typing.TypeAlias = arc4.StaticArray[arc4.UInt8, typing.Literal[3]]
Game: typing.TypeAlias = arc4.StaticArray[Row, typing.Literal[3]]
Move: typing.TypeAlias = tuple[UInt64, UInt64]
HOST = 1
CHALLENGER = 2
DRAW = 3


class TicTacToeContract(arc4.ARC4Contract):
    @arc4.abimethod(create="allow")
    def new_game(self, move: Move) -> tuple[Game, arc4.UInt8]:
        self.game = Game.from_bytes(op.bzero(9))
        self.host = Txn.sender
        self.challenger = Global.zero_address
        self.winner = arc4.UInt8(0)
        assert move[0] < 3 and move[1] < 3, "Move must be in range"
        self.game[move[1]][move[0]] = arc4.UInt8(HOST)
        self.turns = UInt64(0)
        return self.game, self.winner

    @arc4.abimethod
    def join_game(self, move: Move) -> tuple[Game, arc4.UInt8]:
        assert self.challenger == Global.zero_address, "Host already has a challenger"
        self.challenger = Txn.sender
        self.make_move(arc4.UInt8(CHALLENGER), move)
        return self.game, self.winner

    @arc4.abimethod
    def whose_turn(self) -> arc4.UInt8:
        return arc4.UInt8(HOST) if self.turns % 2 else arc4.UInt8(CHALLENGER)

    @arc4.abimethod
    def play(self, move: Move) -> tuple[Game, arc4.UInt8]:
        assert not self.winner, "Game is already finished"
        if self.turns % 2 == 1:
            assert self.host == Txn.sender, "It is the host's turn"
            self.make_move(arc4.UInt8(HOST), move)
        else:
            assert self.challenger == Txn.sender, "It is the challenger's turn"
            self.make_move(arc4.UInt8(CHALLENGER), move)
        return self.game, self.winner

    @subroutine
    def make_move(self, piece: arc4.UInt8, move: Move) -> None:
        assert move[0] < 3 and move[1] < 3, "Move must be in range"
        assert self.game[move[1]][move[0]] == arc4.UInt8(0), "Square is already taken"
        self.game[move[1]][move[0]] = piece
        self.turns += 1
        self.check_winner()
        if self.turns == 9 and not self.winner:
            self.winner = arc4.UInt8(DRAW)

    @subroutine
    def check_winner(self) -> None:
        g = self.game.copy()
        for row in g:
            if row[0] and row[0] == row[1] == row[2]:
                self.winner = row[0]
                return
        for col in urange(3):
            if g[0][col] and g[0][col] == g[1][col] == g[2][col]:
                self.winner = g[0][col]
                return
        # if center has been played
        if g[1][1]:
            if g[0][0] == g[1][1] == g[2][2]:
                self.winner = g[0][0]
            elif g[0][2] == g[1][1] == g[2][0]:
                self.winner = g[0][2]
