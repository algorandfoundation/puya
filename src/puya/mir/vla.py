import typing
from collections.abc import Callable, Sequence, Set
from functools import cached_property

import attrs

from puya.mir import models

_StableStr = Set[str]
_empty_set = frozenset[str]()
_LiveInFactory = Callable[[dict[str, None]], _StableStr]


@attrs.define(kw_only=True)
class _OpLifetime:
    block: models.MemoryBasicBlock
    used: Sequence[str] = attrs.field(on_setattr=attrs.setters.frozen)
    defined: Sequence[str] = attrs.field(on_setattr=attrs.setters.frozen)
    live_in_factory: _LiveInFactory = attrs.field(on_setattr=attrs.setters.frozen)
    successors: Sequence[typing.Self] = attrs.field(default=())
    predecessors: Sequence[typing.Self] = attrs.field(default=())

    live_in: _StableStr = attrs.field(default=_empty_set)
    live_out: _StableStr = attrs.field(default=_empty_set)

    @classmethod
    def from_op(cls, block: models.MemoryBasicBlock, op: models.BaseOp) -> typing.Self:
        # the only nodes that change live_in are AbstractStore/Load
        # so to improve the performance of calculating live_in
        # use factories to create specific functions for transforming live_out -> Live_in
        # in[n] = use[n] U (out[n] - def [n])
        used: Sequence[str]
        defined: Sequence[str]
        live_in_factory = _live_in_identity
        used = defined = ()
        # the only nodes that change live_in are AbstractStore/Load
        # so to improve the performance of calculating live_in
        # use factories to create specific functions for transforming live_out -> Live_in
        # in[n] = use[n] U (out[n] - def [n])
        if isinstance(op, models.AbstractStore):
            defined = (op.local_id,)
            live_in_factory = _live_in_defined_factory(op.local_id)
        elif isinstance(op, models.AbstractLoad):
            used = (op.local_id,)
            live_in_factory = _live_in_used_factory(op.local_id)

        return cls(block=block, used=used, defined=defined, live_in_factory=live_in_factory)


_live_in_identity: _LiveInFactory = dict[str, None].keys


def _live_in_defined_factory(local_id: str) -> _LiveInFactory:
    def factory(live_out: dict[str, None]) -> _StableStr:
        live_in = live_out.copy()
        live_in.pop(local_id, None)
        return live_in.keys()

    return factory


def _live_in_used_factory(local_id: str) -> _LiveInFactory:
    def factory(live_out: dict[str, None]) -> _StableStr:
        live_in = live_out.copy()
        live_in[local_id] = None
        return live_in.keys()

    return factory


@attrs.frozen
class VariableLifetimeAnalysis:
    """Performs VLA analysis for a subroutine, providing a mapping of ops to sets of live local_ids
    see https://www.classes.cs.uchicago.edu/archive/2004/spring/22620-1/docs/liveness.pdf"""

    subroutine: models.MemorySubroutine

    @property
    def all_variables(self) -> Sequence[str]:
        return sorted(
            {v for live in self._op_lifetimes.values() for v in (*live.defined, *live.used)}
        )

    def is_dead_store(self, op: models.BaseOp) -> bool:
        return isinstance(op, models.AbstractStore) and (
            op.local_id not in self.get_live_out_variables(op)
        )

    def _op_lifetimes_factory(self) -> dict[models.BaseOp, _OpLifetime]:
        result = dict[models.BaseOp, _OpLifetime]()
        block_lifetimes = dict[str, list[_OpLifetime]]()
        for block in self.subroutine.body:
            block_lifetimes[block.block_name] = lifetimes = []
            for op in block.ops:
                olt = _OpLifetime.from_op(block, op)
                lifetimes.append(olt)
                result[op] = olt
        # maps the entry and terminating op for a block
        for block in self.subroutine.body:
            lifetimes = block_lifetimes[block.block_name]
            # first op in block can have multiple predecessors
            lifetimes[0].predecessors = tuple(block_lifetimes[p][-1] for p in block.predecessors)
            # ops can each only have one successor
            for op_idx in range(len(lifetimes) - 1):
                op_lifetime = lifetimes[op_idx]
                next_op_lifetime = lifetimes[op_idx + 1]
                op_lifetime.successors = (next_op_lifetime,)
                next_op_lifetime.predecessors = (op_lifetime,)
            # terminator op can have multiple successors
            lifetimes[-1].successors = tuple(block_lifetimes[s][0] for s in block.successors)
        return result

    def get_live_out_variables(self, op: models.BaseOp) -> Set[str]:
        return self._op_lifetimes[op].live_out

    def get_live_in_variables(self, op: models.BaseOp) -> Set[str]:
        return self._op_lifetimes[op].live_in

    def get_store_blocks(self, variable: str) -> set[models.MemoryBasicBlock]:
        return {op.block for op in self._op_lifetimes.values() if variable in op.defined}

    def get_load_blocks(self, variable: str) -> set[models.MemoryBasicBlock]:
        return {op.block for op in self._op_lifetimes.values() if variable in op.used}

    @cached_property
    def _op_lifetimes(self) -> dict[models.BaseOp, _OpLifetime]:
        data = self._op_lifetimes_factory()
        changed = list(reversed(data.values()))
        while changed:
            orig_changed = changed
            changed = []
            for n in orig_changed:
                # For OUT, find out the union of previous variables
                # in the IN set for each succeeding node of n.

                # out[n] = U s ∈ succ[n] in[s]
                live_out = {v: None for s in n.successors for v in s.live_in}

                # in[n] = use[n] U (out[n] - def [n])
                live_in = n.live_in_factory(live_out)

                live_out_keys = live_out.keys()
                if live_out_keys != n.live_out or live_in != n.live_in:
                    n.live_in = live_in
                    n.live_out = live_out_keys
                    changed.extend(n.predecessors)
        return data
