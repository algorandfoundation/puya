from puya.awst import wtypes
from puya.awst.nodes import (
    BoxLength,
    BoxValueExpression,
    IntrinsicCall,
    Literal,
    SingleEvaluation,
    UInt64Constant,
)
from puya.awst_build.eb.base import BuilderBinaryOp, ExpressionBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import eval_slice_component
from puya.errors import CodeError
from puya.parse import SourceLocation


def index_box_bytes(
    box_key: BoxValueExpression,
    index: ExpressionBuilder | Literal,
    location: SourceLocation,
) -> ExpressionBuilder:
    len_expr = BoxLength(box_key=box_key, source_location=location)

    begin_index_expr = eval_slice_component(len_expr, index, location)
    assert begin_index_expr, "Index expression cannot evaluate to None"
    return BytesExpressionBuilder(
        IntrinsicCall(
            op_code="box_extract",
            stack_args=[
                box_key,
                begin_index_expr,
                UInt64Constant(value=1, source_location=location),
            ],
            source_location=location,
            wtype=wtypes.bytes_wtype,
        )
    )


def slice_box_bytes(
    box_key: BoxValueExpression,
    begin_index: ExpressionBuilder | Literal | None,
    end_index: ExpressionBuilder | Literal | None,
    stride: ExpressionBuilder | Literal | None,
    location: SourceLocation,
) -> ExpressionBuilder:
    if stride:
        raise CodeError("Stride is not supported when slicing boxes", location)
    len_expr = SingleEvaluation(BoxLength(box_key=box_key, source_location=location))

    begin_index_expr = eval_slice_component(len_expr, begin_index, location) or UInt64Constant(
        value=0, source_location=location
    )
    end_index_expr = eval_slice_component(len_expr, end_index, location) or len_expr
    length_expr = (
        UInt64ExpressionBuilder(end_index_expr)
        .binary_op(
            UInt64ExpressionBuilder(begin_index_expr), BuilderBinaryOp.sub, location, reverse=False
        )
        .rvalue()
    )

    return BytesExpressionBuilder(
        IntrinsicCall(
            op_code="box_extract",
            stack_args=[
                box_key.key,
                begin_index_expr,
                length_expr,
            ],
            source_location=location,
            wtype=wtypes.bytes_wtype,
        )
    )
