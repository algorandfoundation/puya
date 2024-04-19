import typing

from puya import log
from puya.ir.models import Intrinsic
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class MinAvmVersionValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> None:
        target_avm_version = self.context.options.target_avm_version
        if intrinsic.op.min_avm_version > target_avm_version:
            logger.warning(
                f"Opcode {intrinsic.op} requires a min AVM version of "
                f"{intrinsic.op.min_avm_version} but the target AVM version is"
                f" {target_avm_version}",
                intrinsic.source_location,
            )
