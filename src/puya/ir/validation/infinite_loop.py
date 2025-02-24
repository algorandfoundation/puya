import typing

from puya import log
from puya.ir import models
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class NoInfiniteLoopsValidator(DestructuredIRValidator):
    @typing.override
    def visit_block(self, block: models.BasicBlock) -> None:
        assert block.terminator is not None, "unterminated block found during IR validation"
        if block.terminator.unique_targets == [block]:
            logger.error(
                "infinite loop detected",
                location=block.terminator.source_location or block.source_location,
            )
