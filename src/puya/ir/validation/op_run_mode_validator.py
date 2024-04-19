import typing

from puya import log
from puya.ir.avm_ops_models import RunMode
from puya.ir.models import Intrinsic
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class OpRunModeValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> None:
        match intrinsic.op_variant.supported_modes:
            case RunMode.any:
                pass
            case RunMode.app:
                if self.current_run_mode != RunMode.app:
                    logger.warning(
                        f"The operation {intrinsic} is only allowed in smart contracts",
                        location=intrinsic.source_location,
                    )
            case RunMode.lsig:
                if self.current_run_mode != RunMode.lsig:
                    logger.warning(
                        f"The operation {intrinsic} is only allowed in logic signatures",
                        location=intrinsic.source_location,
                    )
            case _:
                typing.assert_never(intrinsic.op_variant.supported_modes)
