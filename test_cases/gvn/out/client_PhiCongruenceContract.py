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

        Each ABI method is a thin wrapper around the matching module-level
        @subroutine(inline=False), so the GVN-relevant IR shape is preserved
        (algopy.public doesn't support inline= specification).
    
    """
    @algopy.arc4.abimethod
    def call_test_redundant_phi(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def call_test_cross_assignment(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def call_test_triple_cycle(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def call_test_replacement_chain(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
