from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    Literal,
    SingleEvaluation,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build.eb.base import BuilderBinaryOp, NodeBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import eval_slice_component
from puya.errors import CodeError
from puya.parse import SourceLocation


def index_box_bytes(
    box: BoxValueExpression,
    index: NodeBuilder | Literal,
    location: SourceLocation,
) -> NodeBuilder:

    if isinstance(index, NodeBuilder):
        # no negatives
        begin_index_expr = index.rvalue()
    elif not isinstance(index.value, int):
        raise CodeError("Invalid literal index type", index.source_location)
    elif index.value >= 0:
        begin_index_expr = UInt64Constant(value=index.value, source_location=index.source_location)
    else:
        box_length = box_length_unchecked(box, location)
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
    begin_index: NodeBuilder | Literal | None,
    end_index: NodeBuilder | Literal | None,
    stride: NodeBuilder | Literal | None,
    location: SourceLocation,
) -> NodeBuilder:
    if stride:
        raise CodeError("Stride is not supported when slicing boxes", location)
    len_expr = SingleEvaluation(box_length_unchecked(box, location))

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


def box_length_unchecked(box: BoxValueExpression, location: SourceLocation) -> Expression:
    box_len_expr = _box_len(box.key, location)
    box_length = TupleItemExpression(
        base=box_len_expr,
        index=0,
        source_location=location,
    )
    return box_length


def box_length_checked(box: BoxValueExpression, location: SourceLocation) -> Expression:
    box_len_expr = _box_len(box.key, location)
    if box.member_name:
        comment = f"box {box.member_name} exists"
    else:
        comment = "box exists"
    return CheckedMaybe(box_len_expr, comment=comment)


def _box_len(box_key: Expression, location: SourceLocation) -> IntrinsicCall:
    assert box_key.wtype == wtypes.bytes_wtype
    return IntrinsicCall(
        op_code="box_len",
        wtype=wtypes.WTuple([wtypes.uint64_wtype, wtypes.bool_wtype], source_location=location),
        stack_args=[box_key],
        source_location=location,
    )
