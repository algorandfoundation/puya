# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class PhiCongruenceContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Test contract for GVN phi handling.

        Contains patterns exercising:
        - SCC-based phi congruence (cross-assigned variables in loops)
        - Redundant phi elimination (different registers, same VN at join points)

        Each ABI method is a thin wrapper around a subroutine to make
        the intermediate IR easier to inspect.
    
    """
    @algopy.arc4.abimethod
    def test_redundant_phi(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_cross_assignment(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_triple_cycle(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_replacement_chain(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
