# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class PhiCongruenceContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    GVN phi/SCC congruence and optimistic-iteration edge cases: redundant/congruent
        phis, SCC collapse vs pessimistic classification, the moving-VN and loop-invariant
        convergence guards, the iteration cap, and commutative-equality assert elimination.
        Methods wrap subroutines so the IR is easy to inspect.
    
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

    @algopy.arc4.abimethod
    def test_alternating(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_commutative_externals(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_moving_vn(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
        y: algopy.arc4.UIntN[typing.Literal[64]],
        cond: algopy.arc4.Bool,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_loop_invariant(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
        y: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_deep_nesting(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_commutative_add_assert(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        cond: algopy.arc4.Bool,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_nested_scc_collapse(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
        p: algopy.arc4.UIntN[typing.Literal[64]],
        q: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
