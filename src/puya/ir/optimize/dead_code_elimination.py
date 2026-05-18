import typing
from collections.abc import Iterable

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models, visitor
from puya.ir._puya_lib import PuyaLibIR
from puya.ir._utils import bfs_block_order
from puya.ir.optimize._intrinsics import SIDE_EFFECT_FREE_AVM_OPS
from puya.utils import StableSet

logger = log.get_logger(__name__)


@attrs.define
class SubroutineCollector(visitor.IRTraverser):
    subroutines: StableSet[models.Subroutine] = attrs.field(factory=StableSet)
    referenced_libs: StableSet[PuyaLibIR] = attrs.field(factory=StableSet)

    @classmethod
    def collect(cls, program: models.Program) -> StableSet[models.Subroutine]:
        collector = cls()
        collector.visit_subroutine(program.main)
        # also include any referenced library functions
        referenced_subs = [s for s in program.subroutines if s.id in collector.referenced_libs]
        for referenced_sub in referenced_subs:
            collector.visit_subroutine(referenced_sub)
        return collector.subroutines

    def visit_subroutine(self, subroutine: models.Subroutine) -> None:
        if subroutine not in self.subroutines:
            self.subroutines.add(subroutine)
            self.visit_all_blocks(subroutine.body)

    def visit_extract_value(self, _: models.ExtractValue) -> None:
        self.referenced_libs |= (
            PuyaLibIR.static_array_read_dynamic_element,
            PuyaLibIR.static_array_read_byte_length_element,
            PuyaLibIR.dynamic_array_read_dynamic_element,
            PuyaLibIR.dynamic_array_read_byte_length_element,
            PuyaLibIR.dynamic_assert_index,
        )

    def visit_replace_value(self, _: models.ReplaceValue) -> None:
        self.referenced_libs |= (
            PuyaLibIR.dynamic_array_replace_byte_length_head,
            PuyaLibIR.dynamic_array_replace_dynamic_element,
            PuyaLibIR.static_array_replace_byte_length_head,
            PuyaLibIR.static_array_replace_dynamic_element,
            PuyaLibIR.static_array_read_dynamic_element,
            PuyaLibIR.static_array_read_byte_length_element,
            PuyaLibIR.dynamic_array_read_dynamic_element,
            PuyaLibIR.dynamic_array_read_byte_length_element,
            PuyaLibIR.dynamic_assert_index,
        )

    def visit_array_pop(self, _: models.ArrayPop) -> None:
        self.referenced_libs |= (
            PuyaLibIR.dynamic_array_pop_bit,
            PuyaLibIR.r_trim,
            PuyaLibIR.dynamic_array_pop_fixed_size,
            PuyaLibIR.dynamic_array_pop_byte_length_head,
            PuyaLibIR.dynamic_array_pop_dynamic_element,
            PuyaLibIR.box_dynamic_array_pop_fixed_size,
            PuyaLibIR.box_update_offset_dec,
        )

    def visit_array_concat(self, _: models.ArrayConcat) -> None:
        self.referenced_libs |= (
            PuyaLibIR.dynamic_array_concat_fixed,
            PuyaLibIR.dynamic_array_concat_dynamic_element,
            PuyaLibIR.dynamic_array_concat_bits,
            PuyaLibIR.dynamic_array_concat_byte_length_head,
            PuyaLibIR.box_dynamic_array_concat_fixed,
            PuyaLibIR.box_update_offset_inc,
        )

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        self.visit_subroutine(callsub.target)


def remove_unused_subroutines(program: models.Program) -> bool:
    subroutines = SubroutineCollector.collect(program)
    if modified := (len(subroutines) != (1 + len(program.subroutines))):
        to_keep = [p for p in program.subroutines if p in subroutines]
        for p in program.subroutines:
            if p not in subroutines:
                logger.debug(f"removing unused subroutine {p.id}")
        program.subroutines = to_keep
    return modified


_PureValueProviders = (
    models.Value
    | models.InnerTransactionField
    | models.BoxRead
    | models.ExtractValue
    | models.ReplaceValue
    | models.DecodeBytes
    | models.BytesEncode
    | models.ArrayLength
    | models.ArrayPop
    | models.ArrayConcat
)


def remove_unused_variables(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = 0
    assignments = dict[tuple[models.BasicBlock, models.Assignment], set[models.Register]]()
    for block, op, register in UnusedRegisterCollector.collect(subroutine):
        if isinstance(op, models.Assignment):
            assignments.setdefault((block, op), set()).add(register)
        else:
            assert register == op.register
            block.phis.remove(op)
            logger.debug(f"Removing unused variable {register.local_id}")
            modified += 1

    for (block, ass), registers in assignments.items():
        if registers.symmetric_difference(ass.targets):
            pass  # some registers still used
        elif (
            isinstance(ass.source, _PureValueProviders)
            or (isinstance(ass.source, models.InvokeSubroutine) and ass.source.target.pure)
            or (
                isinstance(ass.source, models.Intrinsic)
                and ass.source.op.code in SIDE_EFFECT_FREE_AVM_OPS
            )
        ):
            for reg in sorted(registers, key=lambda r: r.local_id):
                logger.debug(f"Removing unused variable {reg.local_id}")
            block.ops.remove(ass)
            modified += 1
        else:
            logger.debug(
                f"Not removing unused assignment since source is not marked as pure: {ass}"
            )
    return modified > 0


@attrs.define(kw_only=True)
class UnusedRegisterCollector(visitor.IRTraverser):
    used: set[models.Register] = attrs.field(factory=set)
    assigned: dict[models.Register, tuple[models.BasicBlock, models.Assignment | models.Phi]] = (
        attrs.field(factory=dict)
    )
    active_block: models.BasicBlock

    @classmethod
    def collect(
        cls, sub: models.Subroutine
    ) -> Iterable[tuple[models.BasicBlock, models.Assignment | models.Phi, models.Register]]:
        collector = cls(active_block=sub.entry)
        collector.visit_all_blocks(sub.body)
        for reg, (block, ass) in collector.assigned.items():
            if reg not in collector.used:
                yield block, ass, reg

    @typing.override
    def visit_block(self, block: models.BasicBlock) -> None:
        self.active_block = block
        super().visit_block(block)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        for target in ass.targets:
            self.assigned[target] = (self.active_block, ass)
        ass.source.accept(self)

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        # don't visit phi.register, as this would mean the phi can never be considered unused
        for arg in phi.args:
            arg.accept(self)
        self.assigned[phi.register] = (self.active_block, phi)

    @typing.override
    def visit_register(self, reg: models.Register) -> None:
        self.used.add(reg)


def remove_unreachable_blocks(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    reachable_set = frozenset(bfs_block_order(subroutine.entry))
    if len(reachable_set) == len(subroutine.body):
        return False

    reachable_blocks = [subroutine.body[0]]
    for block in subroutine.body[1:]:
        if block in reachable_set:
            reachable_blocks.append(block)
        else:
            logger.debug(f"Removing unreachable block: {block}")
            for succ in block.successors:
                if succ in reachable_set:
                    did_remove = succ.remove_predecessor(block)
                    assert did_remove

    subroutine.body[:] = reachable_blocks
    return True
