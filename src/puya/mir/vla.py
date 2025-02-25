import itertools
import typing
from collections.abc import Sequence, Set
from functools import cached_property

import attrs

from puya.mir import models
from puya.utils import StableSet


@attrs.define(kw_only=True)
class _OpLifetime:
    block: models.MemoryBasicBlock
    used: StableSet[str] = attrs.field(on_setattr=attrs.setters.frozen)
    defined: StableSet[str] = attrs.field(on_setattr=attrs.setters.frozen)
    successors: list[typing.Self] = attrs.field(factory=list)
    predecessors: list[typing.Self] = attrs.field(factory=list)

    live_in: StableSet[str] = attrs.field(factory=StableSet)
    live_out: StableSet[str] = attrs.field(factory=StableSet)


@attrs.define
class VariableLifetimeAnalysis:
    """Performs VLA analysis for a subroutine, providing a mapping of ops to sets of live local_ids
    see https://www.classes.cs.uchicago.edu/archive/2004/spring/22620-1/docs/liveness.pdf"""

    subroutine: models.MemorySubroutine
    _op_lifetimes: dict[models.BaseOp, _OpLifetime] = attrs.field(init=False)

    @cached_property
    def all_variables(self) -> Sequence[str]:
        return sorted(
            {v for live in self._op_lifetimes.values() for v in (*live.defined, *live.used)}
        )

    @_op_lifetimes.default
    def _op_lifetimes_factory(self) -> dict[models.BaseOp, _OpLifetime]:
        result = dict[models.BaseOp, _OpLifetime]()
        block_map = {b.block_name: b.ops[0] for b in self.subroutine.body}
        for block in self.subroutine.body:
            for op in block.ops:
                used = StableSet[str]()
                defined = StableSet[str]()
                if isinstance(op, models.AbstractStore):
                    defined.add(op.local_id)
                elif isinstance(op, models.AbstractLoad):
                    used.add(op.local_id)
                result[op] = _OpLifetime(
                    block=block,
                    used=used,
                    defined=defined,
                )
        for block in self.subroutine.body:
            for op, next_op in itertools.zip_longest(block.ops, block.ops[1:]):
                if isinstance(op, models.ControlOp):
                    assert next_op is None
                    # note: control ops that end the current subroutine don't have any logical
                    # successors
                    successors = [result[block_map[s]] for s in op.targets()]
                else:
                    assert next_op is not None
                    successors = [result[next_op]]
                op_lifetime = result[op]
                op_lifetime.successors = successors
                for s in successors:
                    s.predecessors.append(op_lifetime)
        return result

    def get_live_out_variables(self, op: models.BaseOp) -> Set[str]:
        return self._op_lifetimes[op].live_out

    def get_live_in_variables(self, op: models.BaseOp) -> Set[str]:
        return self._op_lifetimes[op].live_in

    def get_store_blocks(self, variable: str) -> set[models.MemoryBasicBlock]:
        return {op.block for op in self._op_lifetimes.values() if variable in op.defined}

    def get_load_blocks(self, variable: str) -> set[models.MemoryBasicBlock]:
        return {op.block for op in self._op_lifetimes.values() if variable in op.used}

    @classmethod
    def analyze(cls, subroutine: models.MemorySubroutine) -> typing.Self:
        analysis = cls(subroutine)
        analysis._analyze()  # noqa: SLF001
        return analysis

    def _analyze(self) -> None:
        changed = list(self._op_lifetimes.values())
        while changed:
            orig_changed = changed
            changed = []
            for n in orig_changed:
                # For OUT, find out the union of previous variables
                # in the IN set for each succeeding node of n.

                # out[n] = U s ∈ succ[n] in[s]
                live_out = StableSet[str]()
                for s in n.successors:
                    live_out |= s.live_in

                # in[n] = use[n] U (out[n] - def [n])
                live_in = n.used | (live_out - n.defined)

                if live_out != n.live_out or live_in != n.live_in:
                    n.live_in = live_in
                    n.live_out = live_out
                    changed.extend(n.predecessors)
