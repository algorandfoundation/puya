import itertools
import typing
import typing as t
from collections.abc import Iterable

import attrs

from puya import log
from puya.avm import AVMType
from puya.ir import models
from puya.ir.types_ import PrimitiveIRType, SlotType
from puya.ir.visitor_mem_replacer import MemoryReplacer
from puya.ir.vla import VariableLifetimeAnalysis
from puya.options import LocalsCoalescingStrategy
from puya.utils import StableSet

logger = log.get_logger(__name__)


@attrs.define
class MemoryReplacerWithRedundantAssignmentRemoval(MemoryReplacer):
    def visit_assignment(self, op: models.Assignment) -> models.Assignment | None:
        ass = super().visit_assignment(op)
        if ass is None or ass.targets == (ass.source,):
            return None
        return ass


class CoalesceGroupStrategy(t.Protocol):
    def get_group_key(self, reg: models.Register) -> object: ...

    def determine_group_replacement(self, regs: Iterable[models.Register]) -> models.Register: ...


def coalesce_registers(group_strategy: CoalesceGroupStrategy, sub: models.Subroutine) -> int:
    """
    A local can be merged with another local if they are never live at the same time.

    For each local that is being defined, check to see what the live-out locals are.

    It can be merged with another local set if:
     - This local is not in the "live-out" of any local in set
     - The "live-out" of this local does not intersect the local set
    """
    vla = VariableLifetimeAnalysis.analyze(sub)

    # TODO: this uses a basic definition of interference by looking at live-ranges,
    #       a better option is to continue with https://inria.hal.science/inria-00349925v1/document
    #       which has already been partially implemented (phase 1 + 4 have been, anyway)

    variables_live_at_definition = dict[models.Register, StableSet[models.Register]]()
    for param in sub.parameters:
        variables_live_at_definition[param] = StableSet.from_iter(sub.parameters)
    for block in sub.body:
        for op in block.ops:
            match op:
                case models.Assignment(targets=targets):
                    op_live_out = vla.get_live_out_variables(op)
                    for defined_reg in targets:
                        live_set = variables_live_at_definition.setdefault(
                            defined_reg, StableSet()
                        )
                        live_set |= op_live_out

    coalescable_groups_by_key = dict[
        object, list[tuple[StableSet[models.Register], StableSet[models.Register]]]
    ]()
    for defined_reg, live_set in variables_live_at_definition.items():
        coalescable_groups = coalescable_groups_by_key.setdefault(
            group_strategy.get_group_key(defined_reg), []
        )
        for coalescable_register_set, combined_live_out in coalescable_groups:
            # conditions:
            # 1) this register/variable must not be "alive" _after_ the
            #    definition of any other variable in this set
            # 2) no register already in the set should be live out at the
            #    definition of this register
            # regardless of the order the definitions are processed in, this guarantees that:
            # for all A and B in coalescable_register_set such that A != B:
            #       A is not live-out whenever B is assigned
            #   AND B is not live-out whenever A is assigned
            if defined_reg not in combined_live_out and live_set.isdisjoint(
                coalescable_register_set
            ):
                coalescable_register_set.add(defined_reg)
                combined_live_out |= live_set
                break
        else:
            coalescable_groups.append((StableSet(defined_reg), StableSet.from_iter(live_set)))

    replacements = dict[models.Register, models.Register]()
    for group in coalescable_groups_by_key.values():
        for coalescable_register_set, _ in group:
            if len(coalescable_register_set) < 2:
                continue
            replacement = group_strategy.determine_group_replacement(coalescable_register_set)
            find = coalescable_register_set - {replacement}

            logger.debug(f"Coalescing {replacement} with [{', '.join(map(str, find))}]")
            replacements.update({to_find: replacement for to_find in find})
    total_replacements = MemoryReplacerWithRedundantAssignmentRemoval.apply(
        sub.body, replacements=replacements
    )
    return total_replacements


class RootOperandGrouping(CoalesceGroupStrategy):
    def __init__(self, isolate: frozenset[models.Register] | None = None) -> None:
        self._isolate = isolate or frozenset()

    def get_group_key(self, reg: models.Register) -> object:
        if reg in self._isolate:
            return reg
        ir_type = reg.ir_type
        # preserve PrimitiveIRType, because this seems to provide a decent balance
        # preserve SlotType because otherwise MIR will error
        if not isinstance(ir_type, PrimitiveIRType | SlotType):
            match ir_type.maybe_avm_type:
                case AVMType.uint64:
                    ir_type = PrimitiveIRType.uint64
                case AVMType.bytes:
                    ir_type = PrimitiveIRType.bytes
        return reg.name, ir_type

    def determine_group_replacement(self, regs: Iterable[models.Register]) -> models.Register:
        return min(regs, key=lambda r: r.version)


class AggressiveGrouping(CoalesceGroupStrategy):
    def __init__(self, sub: models.Subroutine) -> None:
        self._params = frozenset(sub.parameters)
        self._counter = itertools.count()

    def get_group_key(self, reg: models.Register) -> object:
        if reg in self._params:
            return reg
        else:
            return reg.atype

    def determine_group_replacement(self, regs: Iterable[models.Register]) -> models.Register:
        next_id = next(self._counter)
        (atype,) = {r.atype for r in regs}
        match atype:
            case AVMType.uint64:
                ir_type = PrimitiveIRType.uint64
            case AVMType.bytes:
                ir_type = PrimitiveIRType.bytes
            case _:
                typing.assert_never(atype)
        return models.Register(
            name="",
            version=next_id,
            ir_type=ir_type,
            source_location=None,
        )


def coalesce_locals(subroutine: models.Subroutine, strategy: LocalsCoalescingStrategy) -> None:
    match strategy:
        case LocalsCoalescingStrategy.root_operand:
            group_strategy: CoalesceGroupStrategy = RootOperandGrouping()
        case LocalsCoalescingStrategy.root_operand_excluding_args:
            group_strategy = RootOperandGrouping(isolate=frozenset(subroutine.parameters))
        case LocalsCoalescingStrategy.aggressive:
            group_strategy = AggressiveGrouping(subroutine)
    logger.debug(
        f"Coalescing local variables in {subroutine.id}"
        f" using strategy {type(group_strategy).__name__}"
    )
    replacements = coalesce_registers(group_strategy, subroutine)
    logger.debug(f"Coalescing resulted in {replacements} replacement/s")
