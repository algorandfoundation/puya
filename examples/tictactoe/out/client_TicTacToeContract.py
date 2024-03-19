# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class TicTacToeContract(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod(create='allow')
    def new_game(
        self,
        move: puyapy.arc4.Tuple[puyapy.arc4.UInt64, puyapy.arc4.UInt64],
    ) -> None: ...

    @puyapy.arc4.abimethod
    def join_game(
        self,
        move: puyapy.arc4.Tuple[puyapy.arc4.UInt64, puyapy.arc4.UInt64],
    ) -> None: ...

    @puyapy.arc4.abimethod
    def whose_turn(
        self,
    ) -> puyapy.arc4.UInt8: ...

    @puyapy.arc4.abimethod
    def play(
        self,
        move: puyapy.arc4.Tuple[puyapy.arc4.UInt64, puyapy.arc4.UInt64],
    ) -> None: ...
