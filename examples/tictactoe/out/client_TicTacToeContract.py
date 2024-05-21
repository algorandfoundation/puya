# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TicTacToeContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create='allow')
    def new_game(
        self,
        move: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def join_game(
        self,
        move: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def whose_turn(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[8]]: ...

    @algopy.arc4.abimethod
    def play(
        self,
        move: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...
