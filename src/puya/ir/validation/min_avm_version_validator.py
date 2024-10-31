import typing

from puya import log
from puya.ir.models import Intrinsic
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class MinAvmVersionValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> None:
        program_avm_version = self.active_program.avm_version
        op_avm_version = intrinsic.op_variant.min_avm_version
        if op_avm_version > program_avm_version:
            op_desc = intrinsic.op.value
            # if variant min version differs from op min version, then include variant enum
            if op_avm_version != intrinsic.op.min_avm_version:
                op_desc += f" {intrinsic.op_variant.enum}"
            logger.error(
                f"Opcode {op_desc!r} requires a min AVM version of "
                f"{op_avm_version} but the target AVM version is"
                f" {program_avm_version}",
                location=intrinsic.source_location,
            )
