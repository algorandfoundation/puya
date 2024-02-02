from puya.ir.avm_ops import AVMOp
from puya.ir.models import Intrinsic, Value
from puya.ir.types_ import IRType
from puya.parse import SourceLocation


def select(
    *, condition: Value, false: Value, true: Value, type_: IRType, source_location: SourceLocation
) -> Intrinsic:
    return Intrinsic(
        op=AVMOp.select,
        args=[
            false,
            true,
            condition,
        ],
        types=[type_],
        source_location=source_location,
    )
