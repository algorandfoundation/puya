import itertools
import typing
from collections.abc import Sequence, Set

import attrs

from puya.errors import InternalError
from puya.ir import models as ops
from puya.ir.visitor import IRTraverser
from puya.utils import StableSet

IrOp: typing.TypeAlias = ops.Op | ops.ControlOp | ops.Phi


@attrs.define(kw_only=True)
class _OpLifetime:
    block: ops.BasicBlock
    used: StableSet[ops.Register] = attrs.field(on_setattr=attrs.setters.frozen)
    defined: StableSet[ops.Register] = attrs.field(on_setattr=attrs.setters.frozen)
    successors: Sequence[IrOp] = attrs.field(on_setattr=attrs.setters.frozen)

    live_in: StableSet[ops.Register] = attrs.field(factory=StableSet)
    live_out: StableSet[ops.Register] = attrs.field(factory=StableSet)


@attrs.define
class _VlaTraverser(IRTraverser):
    used: StableSet[ops.Register] = attrs.field(factory=StableSet)
    defined: StableSet[ops.Register] = attrs.field(factory=StableSet)

    @classmethod
    def apply(cls, op: IrOp) -> tuple[StableSet[ops.Register], StableSet[ops.Register]]:
        traverser = cls()
        op.accept(traverser)
        return traverser.used, traverser.defined

    def visit_register(self, reg: ops.Register) -> None:
        self.used.add(reg)

    def visit_assignment(self, ass: ops.Assignment) -> None:
        ass.source.accept(self)
        self.defined = StableSet.from_iter(ass.targets)

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
        block_map = {b.id: next(b.all_ops) for b in self.subroutine.body}
        for block in self.subroutine.body:
            assert not block.phis
            all_ops = list(block.all_ops)
            for op, next_op in itertools.zip_longest(all_ops, all_ops[1:]):
                used, defined = _VlaTraverser.apply(op)
                if next_op is None:
                    # for last op, add first op of each successor block
                    successors = [block_map[s.id] for s in block.successors]
                else:
                    successors = [next_op]
                result[op] = _OpLifetime(
                    block=block,
                    used=used,
                    defined=defined,
                    successors=successors,
                )
        return result

    def get_live_out_variables(self, op: IrOp) -> Set[ops.Register]:
        return self._op_lifetimes[op].live_out

    def get_live_in_variables(self, op: IrOp) -> Set[ops.Register]:
        return self._op_lifetimes[op].live_in

    @classmethod
    def analyze(cls, subroutine: ops.Subroutine) -> typing.Self:
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
                live_out = StableSet[ops.Register]()
                for s in n.successors:
                    live_out |= self._op_lifetimes[s].live_in

                # in[n] = use[n] U (out[n] - def [n])
                live_in = n.used | (live_out - n.defined)

                if not (live_in == n.live_in and live_out == n.live_out):
                    n.live_in = live_in
                    n.live_out = live_out
                    changes = True
