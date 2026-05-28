# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class SccVnMergedExternalsContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Smallest test exercising VN-aware SCC classification.

        Two phis form a multi-member SCC. The external init Registers come
        from commutative-equivalent expressions ``a | b`` and ``b | a``,
        which GVN canonicalises to the same VN even though they're distinct
        Registers. Under Register-identity classification this SCC was
        pessimistic; under VN-aware classification it collapses, because
        every external argument resolves to the same VN. ``x`` and ``y``
        then carry the same VN throughout the loop and the closing
        ``x + y`` becomes ``2 * (a | b)``.
    
    """
    @algopy.arc4.abimethod
    def test_commutative_externals(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
