import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    BytesConstant,
    BytesEncoding,
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    NumericComparison,
    NumericComparisonExpression,
    TupleItemExpression,
    UInt64BinaryOperation,
    UInt64BinaryOperator,
    UInt64Constant,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._utils import resolve_negative_literal_index
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    StorageProxyConstructorResult,
)
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.models import ContractReference
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def index_box_bytes(
    box: BoxValueExpression,
    index: InstanceBuilder,
    location: SourceLocation,
) -> InstanceBuilder:
    box_length = box_length_unchecked(box, location)
    begin_index = resolve_negative_literal_index(index, box_length, location)
    return BytesExpressionBuilder(
        IntrinsicCall(
            op_code="box_extract",
            stack_args=[
                box.key,
                begin_index.resolve(),
                UInt64Constant(value=1, source_location=location),
            ],
            source_location=location,
            wtype=wtypes.bytes_wtype,
        )
    )


def slice_box_bytes(
    box: BoxValueExpression,
    begin_index: InstanceBuilder | None,
    end_index: InstanceBuilder | None,
    stride: InstanceBuilder | None,
    location: SourceLocation,
) -> InstanceBuilder:
    if stride:
        logger.error("stride is not supported when slicing boxes", location=location)
    len_expr = box_length_unchecked(box, location).single_eval().resolve()

    begin_index_expr = _eval_slice_component(len_expr, begin_index, location) or UInt64Constant(
        value=0, source_location=location
    )
    end_index_expr = _eval_slice_component(len_expr, end_index, location) or len_expr
    length_expr = (
        UInt64ExpressionBuilder(end_index_expr)
        .binary_op(
            UInt64ExpressionBuilder(begin_index_expr), BuilderBinaryOp.sub, location, reverse=False
        )
        .resolve()
    )

    return BytesExpressionBuilder(
        IntrinsicCall(
            op_code="box_extract",
            stack_args=[box.key, begin_index_expr, length_expr],
            source_location=location,
            wtype=wtypes.bytes_wtype,
        )
    )


def box_length_unchecked(box: BoxValueExpression, location: SourceLocation) -> InstanceBuilder:
    box_len_expr = _box_len(box.key, location)
    box_length = TupleItemExpression(
        base=box_len_expr,
        index=0,
        source_location=location,
    )
    return UInt64ExpressionBuilder(box_length)


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


def _eval_slice_component(
    len_expr: Expression, val: NodeBuilder | None, location: SourceLocation
) -> Expression | None:
    if val is None:
        return None

    if not isinstance(val, LiteralBuilder):
        # no negatives to deal with here, easy
        temp_index = (
            expect.argument_of_type_else_dummy(val, pytypes.UInt64Type).single_eval().resolve()
        )
        return intrinsic_factory.select(
            false=len_expr,
            true=temp_index,
            condition=NumericComparisonExpression(
                lhs=temp_index,
                operator=NumericComparison.lt,
                rhs=len_expr,
                source_location=location,
            ),
            loc=location,
        )

    int_lit = val.value
    if not isinstance(int_lit, int):
        logger.error(f"Invalid literal for slicing: {int_lit!r}", location=val.source_location)
        int_lit = 0

    # take the min of abs(int_lit) and len(self.expr)
    abs_lit_expr = UInt64Constant(value=abs(int_lit), source_location=val.source_location)
    trunc_value_expr = intrinsic_factory.select(
        false=len_expr,
        true=abs_lit_expr,
        condition=NumericComparisonExpression(
            lhs=abs_lit_expr,
            operator=NumericComparison.lt,
            rhs=len_expr,
            source_location=location,
        ),
        loc=location,
    )
    return (
        trunc_value_expr
        if int_lit >= 0
        else UInt64BinaryOperation(
            left=len_expr,
            op=UInt64BinaryOperator.sub,
            right=trunc_value_expr,
            source_location=location,
        )
    )


class BoxProxyConstructorResult(StorageProxyConstructorResult, abc.ABC):
    @typing.override
    @property
    def initial_value(self) -> None:
        return None

    @typing.override
    def build_definition(
        self,
        member_name: str,
        defined_in: ContractReference,
        typ: pytypes.PyType,
        location: SourceLocation,
    ) -> AppStorageDeclaration:
        key_override = self.resolve()
        if not isinstance(key_override, BytesConstant):
            logger.error(
                f"assigning {typ} to a member variable requires a constant value for"
                f" key{'_prefix' if isinstance(typ, pytypes.StorageMapProxyType) else ''}",
                location=location,
            )
            key_override = BytesConstant(
                value=b"0",
                wtype=wtypes.box_key,
                encoding=BytesEncoding.unknown,
                source_location=key_override.source_location,
            )
        return AppStorageDeclaration(
            description=None,
            member_name=member_name,
            key_override=key_override,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )
