import typing
from collections.abc import Sequence, Set

import attrs

from puya.errors import InternalError
from puya.ir import models as ops
from puya.ir.visitor import IRTraverser

IrOp: typing.TypeAlias = ops.Op | ops.ControlOp | ops.Phi

_empty_set = frozenset[ops.Register]()


@attrs.define(kw_only=True)
class _OpLifetime:
    block: ops.BasicBlock
    used: Sequence[ops.Register] = attrs.field(on_setattr=attrs.setters.frozen)
    defined: Sequence[ops.Register] = attrs.field(on_setattr=attrs.setters.frozen)
    successors: Sequence[typing.Self] = attrs.field(default=())
    predecessors: Sequence[typing.Self] = attrs.field(default=())

    live_in: Set[ops.Register] = attrs.field(default=_empty_set)
    live_out: Set[ops.Register] = attrs.field(default=_empty_set)


@attrs.define
class _VlaTraverser(IRTraverser):
    used: Sequence[ops.Register] = attrs.field(default=())
    defined: Sequence[ops.Register] = attrs.field(default=())

    @classmethod
    def apply(cls, op: IrOp) -> tuple[Sequence[ops.Register], Sequence[ops.Register]]:
        traverser = cls()
        op.accept(traverser)
        return traverser.used, traverser.defined

    def visit_register(self, reg: ops.Register) -> None:
        self.used = (*self.used, reg)

    def visit_assignment(self, ass: ops.Assignment) -> None:
        ass.source.accept(self)
        self.defined = ass.targets

    def visit_phi(self, _phi: ops.Phi) -> None:
        # WARNING: this is slightly trickier than it might seem for SSA,
        #          consider how this translates when coming out of SSA -
        #          the target register isn't defined here, but defined at
        #          the end of each predecessor block.
        #          Similarly, the arguments aren't live-in at this location necessarily.
        raise InternalError("IR VLA not capable of handling SSA yet")


@attrs.define
class VariableLifetimeAnalysis:
    """Performs VLA analysis for a subroutine, providing a mapping of ops to sets of live local_ids
    see https://www.classes.cs.uchicago.edu/archive/2004/spring/22620-1/docs/liveness.pdf"""

    subroutine: ops.Subroutine
    _op_lifetimes: dict[IrOp, _OpLifetime] = attrs.field(init=False)

    @_op_lifetimes.default
    def _op_lifetimes_factory(self) -> dict[IrOp, _OpLifetime]:
        result = dict[IrOp, _OpLifetime]()
        block_lifetimes = dict[ops.BasicBlock, list[_OpLifetime]]()
        for block in self.subroutine.body:
            assert not block.phis, "IR VLA cannot operate on SSA IR"
            block_lifetimes[block] = lifetimes = []
            for op in block.all_ops:
                used, defined = _VlaTraverser.apply(op)
                olt = _OpLifetime(block=block, used=used, defined=defined)
                lifetimes.append(olt)
                result[op] = olt
        for block, lifetimes in block_lifetimes.items():
            # for the first op add control op of each predecessor block
            lifetimes[0].predecessors = tuple(block_lifetimes[p][-1] for p in block.predecessors)
            # iterate all ops until the last
            for op_idx in range(len(lifetimes) - 1):
                op_lifetime = lifetimes[op_idx]
                next_op_lifetime = lifetimes[op_idx + 1]
                op_lifetime.successors = (next_op_lifetime,)
                next_op_lifetime.predecessors = (op_lifetime,)
            # for the last op set successors to the first op of each successor block
            lifetimes[-1].successors = tuple(block_lifetimes[s][0] for s in block.successors)
        return result

    def get_live_out_variables(self, op: IrOp) -> Set[ops.Register]:
        return self._op_lifetimes[op].live_out

    @classmethod
    def analyze(cls, subroutine: ops.Subroutine) -> typing.Self:
        analysis = cls(subroutine)
        analysis._analyze()  # noqa: SLF001
        return analysis

    def _analyze(self) -> None:
        op_lifetimes = self._op_lifetimes
        changed = list(reversed(op_lifetimes.values()))
        while changed:
            orig_changed = changed
            changed = []
            for n in orig_changed:
                # For OUT, find out the union of previous variables
                # in the IN set for each succeeding node of n.

                # out[n] = U s ∈ succ[n] in[s]
                live_out = {r: None for s in n.successors for r in s.live_in}

                # in[n] = use[n] U (out[n] - def [n])
                live_in = live_out.copy()
                for r in n.defined:
                    live_in.pop(r, None)
                for r in n.used:
                    live_in[r] = None

                if not (live_in.keys() == n.live_in and live_out.keys() == n.live_out):
                    n.live_in = live_in.keys()
                    n.live_out = live_out.keys()
                    changed.extend(n.predecessors)
