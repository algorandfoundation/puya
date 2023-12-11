import itertools
import typing
from collections.abc import Sequence, Set
from functools import cached_property

import attrs

from puya.codegen import ops
from puya.utils import StableSet


@attrs.define(kw_only=True)
class _OpLifetime:
    block: ops.MemoryBasicBlock
    used: StableSet[str] = attrs.field(on_setattr=attrs.setters.frozen)
    defined: StableSet[str] = attrs.field(on_setattr=attrs.setters.frozen)
    successors: Sequence[ops.BaseOp] = attrs.field(on_setattr=attrs.setters.frozen)

    live_in: StableSet[str] = attrs.field(factory=StableSet)
    live_out: StableSet[str] = attrs.field(factory=StableSet)


@attrs.define(slots=False)
class VariableLifetimeAnalysis:
    """Performs VLA analysis for a subroutine, providing a mapping of ops to sets of live local_ids
    see https://www.classes.cs.uchicago.edu/archive/2004/spring/22620-1/docs/liveness.pdf"""

    subroutine: ops.MemorySubroutine
    _op_lifetimes: dict[ops.BaseOp, _OpLifetime] = attrs.field(init=False)

    @cached_property
    def all_variables(self) -> Sequence[str]:
        return sorted(
            {v for live in self._op_lifetimes.values() for v in (*live.defined, *live.used)}
        )

    @_op_lifetimes.default
    def _op_lifetimes_factory(self) -> dict[ops.BaseOp, _OpLifetime]:
        result = dict[ops.BaseOp, _OpLifetime]()
        block_map = {b.block_name: b.ops[0] for b in self.subroutine.body}
        for block in self.subroutine.all_blocks:
            for op, next_op in itertools.zip_longest(block.ops, block.ops[1:]):
                used = StableSet[str]()
                defined = StableSet[str]()
                if isinstance(op, ops.StoreVirtual):
                    defined.add(op.local_id)
                elif isinstance(op, ops.LoadVirtual):
                    used.add(op.local_id)
                if next_op is None:
                    # for last op, add first op of each successor block
                    successors = [block_map[s] for s in block.successors]
                else:
                    successors = [next_op]
                result[op] = _OpLifetime(
                    block=block,
                    used=used,
                    defined=defined,
                    successors=successors,
                )
        return result

    def get_live_out_variables(self, op: ops.BaseOp) -> Set[str]:
        return self._op_lifetimes[op].live_out

    def get_live_in_variables(self, op: ops.BaseOp) -> Set[str]:
        return self._op_lifetimes[op].live_in

    def get_store_blocks(self, variable: str) -> set[ops.MemoryBasicBlock]:
        return {op.block for op in self._op_lifetimes.values() if variable in op.defined}

    def get_load_blocks(self, variable: str) -> set[ops.MemoryBasicBlock]:
        return {op.block for op in self._op_lifetimes.values() if variable in op.used}

    @classmethod
    def analyze(cls, subroutine: ops.MemorySubroutine) -> typing.Self:
        analysis = cls(subroutine)
        analysis._analyze()  # noqa: SLF001
        return analysis

    def _analyze(self) -> None:
        changes = True
        while changes:
            changes = False
            for n in self._op_lifetimes.values():
                # For OUT, find out the union of previous variables
                # in the IN set for each succeeding node of n.

                # out[n] = U s ∈ succ[n] in[s]
                live_out = StableSet[str]()
                for s in n.successors:
                    live_out |= self._op_lifetimes[s].live_in

                # in[n] = use[n] U (out[n] - def [n])
                live_in = n.used | (live_out - n.defined)

                if not (live_in == n.live_in and live_out == n.live_out):
                    n.live_in = live_in
                    n.live_out = live_out
                    changes = True
