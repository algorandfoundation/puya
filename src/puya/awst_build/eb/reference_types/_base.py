from __future__ import annotations

import abc
import typing

from immutabledict import immutabledict

from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    Not,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import (
    NotIterableInstanceExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder, NodeBuilder
from puya.awst_build.utils import convert_literal_to_builder

if typing.TYPE_CHECKING:

    from collections.abc import Mapping

    from puya.parse import SourceLocation


class ReferenceValueExpressionBuilder(NotIterableInstanceExpressionBuilder, abc.ABC):
    def __init__(
        self,
        expr: Expression,
        *,
        typ: pytypes.PyType,
        native_type: pytypes.PyType,
        native_access_member: str,
        field_mapping: Mapping[str, tuple[str, pytypes.PyType]],
        field_op_code: str,
        field_bool_comment: str,
    ):
        super().__init__(typ, expr)
        self.native_type = native_type
        self.native_access_member = native_access_member
        self.field_mapping = immutabledict[str, tuple[str, pytypes.PyType]](field_mapping)
        self.field_op_code = field_op_code
        self.field_bool_comment = field_bool_comment

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == self.native_access_member:
            native_cast = ReinterpretCast(
                expr=self.resolve(), wtype=self.native_type.wtype, source_location=location
            )
            return builder_for_instance(self.native_type, native_cast)
        if name in self.field_mapping:
            immediate, typ = self.field_mapping[name]
            acct_params_get = IntrinsicCall(
                source_location=location,
                wtype=wtypes.WTuple((typ.wtype, wtypes.bool_wtype), location),
                op_code=self.field_op_code,
                immediates=[immediate],
                stack_args=[self.resolve()],
            )
            checked_maybe = CheckedMaybe(acct_params_get, comment=self.field_bool_comment)
            return builder_for_instance(typ, checked_maybe)
        return super().member_access(name, location)


class UInt64BackedReferenceValueExpressionBuilder(ReferenceValueExpressionBuilder):
    def __init__(
        self,
        expr: Expression,
        *,
        typ: pytypes.PyType,
        native_access_member: str,
        field_mapping: Mapping[str, tuple[str, pytypes.PyType]],
        field_op_code: str,
        field_bool_comment: str,
    ):
        super().__init__(
            expr,
            typ=typ,
            native_type=pytypes.UInt64Type,
            native_access_member=native_access_member,
            field_mapping=field_mapping,
            field_op_code=field_op_code,
            field_bool_comment=field_bool_comment,
        )

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return intrinsic_factory.itob(self.resolve(), location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        as_bool = ReinterpretCast(
            expr=self.resolve(),
            wtype=wtypes.bool_wtype,
            source_location=self.resolve().source_location,
        )
        if negate:
            expr: Expression = Not(location, as_bool)
        else:
            expr = as_bool
        return BoolExpressionBuilder(expr)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        if not (
            other.pytype == self.pytype  # can only compare with other of same type?
            and op in (BuilderComparisonOp.eq, BuilderComparisonOp.ne)
        ):
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.resolve(),
            operator=NumericComparison(op.value),
            rhs=other.resolve(),
        )
        return BoolExpressionBuilder(cmp_expr)