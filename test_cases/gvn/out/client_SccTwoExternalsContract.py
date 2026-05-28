# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class SccTwoExternalsContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Smallest test exercising the SCC pre-pass's pessimistic classification.

        Two phis form a multi-member SCC with two distinct external init
        Registers (the parameters ``a`` and ``b``). The SCC cannot collapse to
        a single VN — odd iterations swap ``x`` and ``y`` — so the pre-pass
        marks both phis pessimistic and ``visit_phi`` short-circuits the
        redundancy claim. Without the pre-pass, optimistic iteration would
        converge to the same partition in 2-3 walks (small SCC).
    
    """
    @algopy.arc4.abimethod
    def test_alternating(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
