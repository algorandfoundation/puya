"""
The compiled reference replacement is part of the optimizer pipeline for two reasons:

1.) It relies on any template variables provided being optimized into constant values
2.) Once compiled references are replaced there are additional optimizations that can occur
"""

import typing
from collections.abc import Mapping

import attrs
from immutabledict import immutabledict

from puya import log
from puya.algo_constants import HASH_PREFIX_PROGRAM, MAX_BYTES_LENGTH
from puya.awst.txn_fields import TxnField
from puya.compilation_artifacts import TemplateValue
from puya.context import ArtifactCompileContext
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.visitor_mutator import IRMutator
from puya.program_refs import ProgramKind
from puya.utils import (
    Address,
    biguint_bytes_eval,
    calculate_extra_program_pages,
    method_selector_hash,
    sha512_256_hash,
)

logger = log.get_logger(__name__)


def replace_compiled_references(
    context: ArtifactCompileContext, subroutine: ir.Subroutine
) -> bool:
    replacer = CompiledReferenceReplacer(context)
    for block in subroutine.body:
        replacer.visit_block(block)
    return replacer.modified


@attrs.define
class CompiledReferenceReplacer(IRMutator):
    context: ArtifactCompileContext
    modified: bool = False

    def visit_compiled_logicsig_reference(  # type: ignore[override]
        self,
        const: ir.CompiledLogicSigReference,
    ) -> ir.CompiledLogicSigReference | ir.Constant:
        if not _is_constant(const.template_variables):
            return const
        template_constants = _get_template_constants(const.template_variables)
        program_bytecode = self.context.build_program_bytecode(
            const.artifact, ProgramKind.logic_signature, template_constants=template_constants
        )
        address_public_key = sha512_256_hash(HASH_PREFIX_PROGRAM + program_bytecode)
        return ir.AddressConstant(
            value=Address.from_public_key(address_public_key).address,
            source_location=const.source_location,
        )

    def visit_compiled_contract_reference(  # type: ignore[override]
        self,
        const: ir.CompiledContractReference,
    ) -> ir.CompiledContractReference | ir.Constant:
        field = const.field
        if field in (
            TxnField.GlobalNumUint,
            TxnField.GlobalNumByteSlice,
            TxnField.LocalNumUint,
            TxnField.LocalNumByteSlice,
        ):
            state_total = self.context.get_state_totals(const.artifact)
            match field:
                case TxnField.GlobalNumUint:
                    total = state_total.global_uints
                case TxnField.GlobalNumByteSlice:
                    total = state_total.global_bytes
                case TxnField.LocalNumUint:
                    total = state_total.local_uints
                case TxnField.LocalNumByteSlice:
                    total = state_total.local_bytes
                case _:
                    raise InternalError(
                        f"Invalid state total field: {field.name}", const.source_location
                    )
            return ir.UInt64Constant(
                value=total,
                source_location=const.source_location,
            )

        if not _is_constant(const.template_variables):
            return const
        template_constants = _get_template_constants(const.template_variables)
        match field:
            case TxnField.ApprovalProgramPages | TxnField.ClearStateProgramPages:
                page = const.program_page
                if page is None:
                    raise InternalError("expected non-none value for page", const.source_location)
                program_bytecode = self.context.build_program_bytecode(
                    const.artifact,
                    (
                        ProgramKind.approval
                        if field == TxnField.ApprovalProgramPages
                        else ProgramKind.clear_state
                    ),
                    template_constants=template_constants,
                )
                program_page = program_bytecode[
                    page * MAX_BYTES_LENGTH : (page + 1) * MAX_BYTES_LENGTH
                ]
                return ir.BytesConstant(
                    value=program_page,
                    encoding=AVMBytesEncoding.base64,
                    source_location=const.source_location,
                )
            case TxnField.ExtraProgramPages:
                approval_bytecode = self.context.build_program_bytecode(
                    const.artifact, ProgramKind.approval, template_constants=template_constants
                )
                clear_bytecode = self.context.build_program_bytecode(
                    const.artifact, ProgramKind.clear_state, template_constants=template_constants
                )
                return ir.UInt64Constant(
                    value=calculate_extra_program_pages(
                        len(approval_bytecode), len(clear_bytecode)
                    ),
                    source_location=const.source_location,
                )
        raise InternalError(
            f"Unhandled compiled reference field: {field.name}", const.source_location
        )


def _is_constant(
    template_variables: Mapping[str, ir.Value],
) -> typing.TypeGuard[Mapping[str, ir.Constant]]:
    return all(isinstance(var, ir.Constant) for var in template_variables.values())


def _get_template_constants(
    template_variables: Mapping[str, ir.Constant],
) -> immutabledict[str, TemplateValue]:
    result = {
        var: (_extract_constant_value(value), value.source_location)
        for var, value in template_variables.items()
    }
    return immutabledict(result)


def _extract_constant_value(value: ir.Constant) -> int | bytes:
    match value:
        case ir.UInt64Constant(value=int_value):
            return int_value
        case ir.BytesConstant(value=bytes_value):
            return bytes_value
        case ir.BigUIntConstant(value=biguint):
            return biguint_bytes_eval(biguint)
        case ir.AddressConstant(value=addr):
            address = Address.parse(addr)
            return address.public_key
        case ir.MethodConstant(value=method):
            return method_selector_hash(method)
        case ir.ITxnConstant():
            raise CodeError(
                "inner transactions cannot be used as a template variable",
                value.source_location,
            )
        case _:
            raise InternalError(
                f"unhandled constant type: {type(value).__name__}",
                location=value.source_location,
            )
