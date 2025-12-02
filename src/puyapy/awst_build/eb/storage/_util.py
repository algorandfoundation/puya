from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    CheckedMaybe,
    Expression,
    IntrinsicCall,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def box_length_checked(box: BoxValueExpression, location: SourceLocation) -> Expression:
    box_len_expr = _box_len(box.key, location)
    return CheckedMaybe(box_len_expr, comment=box.exists_assertion_message or "box exists")


def _box_len(box_key: Expression, location: SourceLocation) -> IntrinsicCall:
    assert box_key.wtype == wtypes.box_key
    return IntrinsicCall(
        op_code="box_len",
        wtype=wtypes.WTuple([wtypes.uint64_wtype, wtypes.bool_wtype], source_location=location),
        stack_args=[box_key],
        source_location=location,
    )
