import typing
from collections.abc import Mapping

from puya.avm import AVMType
from puya.compilation_artifacts import TemplateValue
from puya.context import CompileContext
from puya.program_refs import ContractReference, LogicSigReference
from puya.teal import models as teal
from puya.ussemble import models
from puya.ussemble.assemble import assemble_bytecode_and_debug_info
from puya.ussemble.context import AssembleContext
from puya.utils import attrs_extend


def assemble_program(
    ctx: CompileContext,
    ref: ContractReference | LogicSigReference,
    program: teal.TealProgram,
    *,
    template_constants: Mapping[str, TemplateValue] | None = None,
    is_reference: bool = False,
) -> models.AssembledProgram:
    referenced_template_vars = _gather_template_variables(program)
    assemble_ctx = attrs_extend(
        AssembleContext,
        ctx,
        artifact_ref=ref,
        is_reference=is_reference,
        template_variable_types=referenced_template_vars,
        template_constants=template_constants,
    )
    return assemble_bytecode_and_debug_info(assemble_ctx, program)


def _gather_template_variables(
    program: teal.TealProgram,
) -> Mapping[str, typing.Literal[AVMType.uint64, AVMType.bytes]]:
    return {
        t: AVMType.uint64 if isinstance(op, teal.IntBlock) else AVMType.bytes
        for sub in program.all_subroutines
        for block in sub.blocks
        for op in block.ops
        if isinstance(op, teal.IntBlock | teal.BytesBlock)
        for t in op.constants
        if isinstance(t, str)
    }
