import itertools
import typing
from collections.abc import Iterable, Mapping, Sequence

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir import (
    models,
    types_ as types,
)
from puya.ir.visitor_mem_replacer import MemoryReplacer
from puya.ir.vla import VariableLifetimeAnalysis
from puya.options import LocalsCoalescingStrategy
from puya.utils import StableSet

logger = log.get_logger(__name__)


def _replace_registers_and_remove_redundant_assignments(
    blocks: Iterable[models.BasicBlock],
    *,
    replacements: Mapping[models.Register, models.Register],
) -> int:
    if not replacements:
        return 0
    replacer = MemoryReplacer(replacements=replacements)
    for block in blocks:
        assert not block.phis, "coalescing runs after phi-node removal"
        ops = list[models.Op]()
        for op in block.ops:
            replacement = op.accept(replacer)
            assert replacement is None, "MemoryReplacer should modify in-place"
            if not _assignment_eliminated(op):
                ops.append(op)
        block.ops[:] = ops
        assert block.terminator is not None
        replacement = block.terminator.accept(replacer)
        assert replacement is None, "MemoryReplacer should modify in-place"
    return replacer.replaced


def _assignment_eliminated(op: models.Op) -> bool:
    """
    Removes redundant copy(s) if op is an Assignment.
    If an assignment becomes a no-op, returns True.
    """
    if type(op) is not models.Assignment:
        return False
    ass: models.Assignment = op
    source = ass.source
    if isinstance(source, models.Register):
        (target,) = ass.targets
        if source == target:
            return True
    elif type(source) is models.ValueTuple:
        redundant_indexes = [
            idx
            for idx, (dst, src) in enumerate(zip(ass.targets, source.values, strict=True))
            if dst == src
        ]
        if len(redundant_indexes) == len(ass.targets):
            return True
        for idx in reversed(redundant_indexes):
            ass.targets.pop(idx)
            source.values.pop(idx)
    return False


class CoalesceGroupStrategy[TKey](typing.Protocol):
    def get_group_key(self, reg: models.Register) -> TKey: ...

    def determine_group_replacement(
        self, group_key: TKey, regs: Iterable[models.Register]
    ) -> models.Register: ...


def coalesce_registers(
    group_strategy: CoalesceGroupStrategy[typing.Any],
    sub: models.Subroutine,
    *,
    allow_params: bool,
) -> int:
    """
    A local can be merged with another local if they are never live at the same time.

    For each local that is being defined, check to see what the live-out locals are.

    It can be merged with another local set if:
     - This local is not in the "live-out" of any local in set
     - The "live-out" of this local does not intersect the local set
    """
    vla = VariableLifetimeAnalysis.analyze(sub)

    variables_live_at_definition = dict[models.Register, StableSet[models.Register]]()
    if allow_params:
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
    for group_key, group in coalescable_groups_by_key.items():
        for coalescable_register_set, _ in group:
            if len(coalescable_register_set) < 2:
                continue
            replacement = group_strategy.determine_group_replacement(
                group_key, coalescable_register_set
            )
            find = coalescable_register_set - {replacement}

            logger.debug(f"Coalescing {replacement} with [{', '.join(map(str, find))}]")
            replacements.update({to_find: replacement for to_find in find})
    total_replacements = _replace_registers_and_remove_redundant_assignments(
        sub.body, replacements=replacements
    )
    return total_replacements


_RootOperandKey = tuple[str, types.IRType]


class RootOperandGrouping(CoalesceGroupStrategy[_RootOperandKey]):
    def __init__(self, params: Sequence[models.Parameter]) -> None:
        self._params = params

    @typing.override
    def get_group_key(self, reg: models.Register) -> _RootOperandKey:
        ir_type = reg.ir_type
        # preserve PrimitiveIRType, because this seems to provide a decent balance
        # preserve SlotType because otherwise MIR will error
        if not isinstance(ir_type, types.PrimitiveIRType | types.SlotType):
            match ir_type.maybe_avm_type:
                case AVMType.uint64:
                    ir_type = types.uint64
                case AVMType.bytes:
                    ir_type = types.bytes_
        return reg.name, ir_type

    @typing.override
    def determine_group_replacement(
        self, group_key: _RootOperandKey, regs: Iterable[models.Register]
    ) -> models.Register:
        params = [r for r in regs if r in self._params]
        match params:
            case [param]:
                # if there is a parameter in the group, we must use that, it wouldn't be updated
                return param
            case []:
                # otherwise use the smallest version number, and if they're all the same type use
                # that, otherwise use the type they were grouped by
                version = min(r.version for r in regs)
                name, ir_type_key = group_key
                try:
                    (ir_type,) = {r.ir_type for r in regs}
                except ValueError:
                    ir_type = ir_type_key
                return models.Register(
                    name=name,
                    ir_type=ir_type,
                    version=version,
                    source_location=None,
                )
            case _:
                # this shouldn't happen, if params are being considered for coalescing, they
                # should all be alive at their definition point and thus not grouped together
                raise InternalError(
                    f"coalesced register set ({[r.local_id for r in regs]})"
                    f" contained multiple parameters: {[p.local_id for p in params]}"
                )


class AggressiveGrouping(CoalesceGroupStrategy[types.IRType]):
    def __init__(self) -> None:
        self._counter = itertools.count()

    @typing.override
    def get_group_key(self, reg: models.Register) -> types.IRType:
        if isinstance(reg.ir_type, types.SlotType):
            match reg.ir_type.contents.avm_type:
                case AVMType.uint64:
                    return types.SlotType(types.uint64)
                case _:
                    return types.SlotType(types.bytes_)
        else:
            match reg.atype:
                case AVMType.uint64:
                    return types.uint64
                case AVMType.bytes:
                    return types.bytes_

    @typing.override
    def determine_group_replacement(
        self, group_key: types.IRType, regs: Iterable[models.Register]
    ) -> models.Register:
        next_id = next(self._counter)
        return models.Register(
            name=f"%{next_id}",
            version=0,
            ir_type=group_key,
            source_location=None,
        )


def coalesce_locals(subroutine: models.Subroutine, strategy: LocalsCoalescingStrategy) -> None:
    logger.debug(f"Coalescing local variables in {subroutine.id} using strategy {strategy.name!r}")
    group_strategy: RootOperandGrouping | AggressiveGrouping
    match strategy:
        case LocalsCoalescingStrategy.root_operand:
            group_strategy = RootOperandGrouping(params=subroutine.parameters)
            allow_params = True
        case LocalsCoalescingStrategy.root_operand_excluding_args:
            group_strategy = RootOperandGrouping(params=subroutine.parameters)
            allow_params = False
        case LocalsCoalescingStrategy.aggressive:
            group_strategy = AggressiveGrouping()
            allow_params = False
    replacements = coalesce_registers(group_strategy, subroutine, allow_params=allow_params)
    logger.debug(f"Coalescing resulted in {replacements} replacement/s")
