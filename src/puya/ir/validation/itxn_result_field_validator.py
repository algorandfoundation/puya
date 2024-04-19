import typing

from puya import log
from puya.ir.models import InnerTransactionField, ITxnConstant
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class ITxnResultFieldValidator(DestructuredIRValidator):
    @typing.override
    def visit_itxn_constant(self, const: ITxnConstant) -> None:
        logger.info(
            "Potential cause of field access with non-constant group index",
            location=const.source_location,
        )

    @typing.override
    def visit_inner_transaction_field(self, field: InnerTransactionField) -> None:
        logger.error(
            "Inner transaction field access with non constant group index,"
            " to resolve move field access to same code path where the inner transaction is"
            " submitted",
            location=field.source_location,
        )
