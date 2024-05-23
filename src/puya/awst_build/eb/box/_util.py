from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    Expression,
    IntrinsicCall,
    Literal,
    SingleEvaluation,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build.eb.base import BuilderBinaryOp, ExpressionBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import eval_slice_component
from puya.errors import CodeError
from puya.parse import SourceLocation


def index_box_bytes(
    box: BoxValueExpression,
    index: ExpressionBuilder | Literal,
    location: SourceLocation,
) -> ExpressionBuilder:

    if isinstance(index, ExpressionBuilder):
        # no negatives
        begin_index_expr = index.rvalue()
    elif not isinstance(index.value, int):
        raise CodeError("Invalid literal index type", index.source_location)
    elif index.value >= 0:
        begin_index_expr = UInt64Constant(value=index.value, source_location=index.source_location)
    else:
        box_length = _box_len(box.key, location)
        box_length_builder = UInt64ExpressionBuilder(box_length)
        begin_index_expr = box_length_builder.binary_op(
            index, BuilderBinaryOp.sub, location, reverse=False
        ).rvalue()
    return BytesExpressionBuilder(
        IntrinsicCall(
            op_code="box_extract",
            stack_args=[
                box.key,
                begin_index_expr,
                UInt64Constant(value=1, source_location=location),
            ],
            source_location=location,
            wtype=wtypes.bytes_wtype,
        )
    )


def slice_box_bytes(
    box: BoxValueExpression,
    begin_index: ExpressionBuilder | Literal | None,
    end_index: ExpressionBuilder | Literal | None,
    stride: ExpressionBuilder | Literal | None,
    location: SourceLocation,
) -> ExpressionBuilder:
    if stride:
        raise CodeError("Stride is not supported when slicing boxes", location)
    len_expr = SingleEvaluation(_box_len(box.key, location))

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
            stack_args=[box.key, begin_index_expr, length_expr],
            source_location=location,
            wtype=wtypes.bytes_wtype,
        )
    )


def _box_len(box_key: Expression, location: SourceLocation) -> Expression:
    assert box_key.wtype == wtypes.bytes_wtype
    box_len_expr = IntrinsicCall(
        op_code="box_len",
        wtype=wtypes.WTuple([wtypes.uint64_wtype, wtypes.bool_wtype], source_location=location),
        stack_args=[box_key],
        source_location=location,
    )
    box_length = TupleItemExpression(
        base=box_len_expr,
        index=0,
        source_location=location,
    )
    return box_length
