"""
The compiled reference replacement is part of the optimizer pipeline for two reasons:

1.) It relies on any template variables provided being optimized into constant values
2.) Once compiled references are replaced there are additional optimizations that can occur
"""

from collections.abc import Mapping

import attrs
from immutabledict import immutabledict

from puya import algo_constants, log
from puya.algo_constants import HASH_PREFIX_PROGRAM, MAX_APP_PAGE_SIZE, MAX_BYTES_LENGTH
from puya.awst.txn_fields import TxnField
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.optimize.context import IROptimizeContext
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.visitor_mutator import IRMutator
from puya.models import (
    TemplateValue,
)
from puya.utils import Address, sha512_256_hash

logger = log.get_logger(__name__)


def replace_compiled_references(context: IROptimizeContext, subroutine: ir.Subroutine) -> bool:
    replacer = CompiledReferenceReplacer(context)
    for block in subroutine.body:
        replacer.visit_block(block)
    return replacer.modified


@attrs.define
class CompiledReferenceReplacer(IRMutator):
    context: IROptimizeContext
    modified: bool = False

    def visit_compiled_logicsig_reference(  # type: ignore[override]
        self,
        const: ir.CompiledLogicSigReference,
    ) -> ir.CompiledLogicSigReference | ir.Constant:
        if not _is_constant(const.template_variables):
            return const
        template_constants = _get_template_constants(
            self.context.options.template_variables, const.template_variables
        )
        program_bytecode = self.context.get_program_bytecode(
            const.artifact, "logic_sig", template_constants
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
            try:
                state_total = self.context.state_totals[const.artifact]
            except KeyError:
                raise InternalError(
                    f"Invalid contract reference: {const.artifact}", const.source_location
                ) from None
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
        template_constants = _get_template_constants(
            self.context.options.template_variables, const.template_variables
        )
        match field:
            case TxnField.ApprovalProgramPages | TxnField.ClearStateProgramPages:
                page = const.program_page
                if page is None:
                    raise InternalError("expected non-none value for page", const.source_location)
                program_bytecode = self.context.get_program_bytecode(
                    const.artifact,
                    ("approval" if field == TxnField.ApprovalProgramPages else "clear_state"),
                    template_constants,
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
                approval_bytecode = self.context.get_program_bytecode(
                    const.artifact, "approval", template_constants
                )
                clear_bytecode = self.context.get_program_bytecode(
                    const.artifact, "clear_state", template_constants
                )
                total_bytes = len(approval_bytecode) + len(clear_bytecode)
                extra_pages = (total_bytes - 1) // MAX_APP_PAGE_SIZE
                return ir.UInt64Constant(
                    value=extra_pages,
                    source_location=const.source_location,
                )
        raise InternalError(
            f"Unhandled compiled reference field: {field.name}", const.source_location
        )


def _is_constant(template_variables: Mapping[str, ir.Value]) -> bool:
    return all(isinstance(var, ir.Constant) for var in template_variables.values())


def _get_template_constants(
    global_consts: Mapping[str, int | bytes], template_variables: Mapping[str, ir.Value]
) -> immutabledict[str, TemplateValue]:
    template_consts: dict[str, TemplateValue] = {k: (v, None) for k, v in global_consts.items()}
    for var, value in template_variables.items():
        match value:
            case ir.UInt64Constant() | ir.BytesConstant() as const:
                template_consts[var] = const.value, const.source_location
            case ir.BigUIntConstant(value=biguint, source_location=loc):
                template_consts[var] = biguint.to_bytes(algo_constants.MAX_BIGUINT_BYTES), loc
            case ir.AddressConstant(value=addr, source_location=loc):
                address = Address.parse(addr)
                template_consts[var] = address.public_key, loc
            case ir.MethodConstant(value=method, source_location=loc):
                template_consts[var] = sha512_256_hash(method.encode("utf8"))[:4], loc
            case ir.ITxnConstant():
                logger.error(
                    "inner transactions cannot be used as a template variable",
                    location=value.source_location,
                )
            case _:
                raise InternalError(
                    "expected compile time constant", location=value.source_location
                )
    return immutabledict(template_consts)
