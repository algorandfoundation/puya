import typing

from puya import log
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class SlotReservationValidator(DestructuredIRValidator):
    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        super().visit_intrinsic_op(intrinsic)
        reserved = self.active_program.slot_allocation.reserved
        if intrinsic.op in (AVMOp.load, AVMOp.store):
            slot = intrinsic.immediates[0]
            # this should be done automatically, so emit a critical error if it isn't
            if slot not in reserved:
                logger.critical("unreserved constant slot", location=intrinsic.source_location)
        elif intrinsic.op in (AVMOp.loads, AVMOp.stores):
            if not reserved:
                logger.error(
                    "dynamic slot usage detected, but no slots reserved on class, "
                    "please reserve slots or use constant values for slots",
                    location=intrinsic.source_location,
                )
