# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class IterationCapContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Test contract whose subroutine forces GVN's optimistic iteration to cap out.

        Deeply nested loops with a shared accumulator produce a phi chain
        whose corrections propagate at roughly one level per optimistic
        iteration. 14 levels exceeds _MAX_OPTIMISTIC_ITERATIONS = 16,
        triggering the pessimistic single-pass fallback.
    
    """
    @algopy.arc4.abimethod
    def test_deep_nesting(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
