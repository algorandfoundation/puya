from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BoxKeyExpression,
    BoxLength,
    BoxProxyExpression,
    BoxValueExpression,
    Expression,
    Literal,
    Not,
    StateDelete,
    StateExists,
    Statement,
)
from puya.awst_build import constants
from puya.awst_build.eb._utils import get_bytes_expr
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.box._common import BoxGetExpressionBuilder, BoxMaybeExpressionBuilder
from puya.awst_build.eb.box._util import index_box_bytes, slice_box_bytes
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.utils import (
    expect_operand_wtype,
    get_arg_mapping,
    require_type_class_eb,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class BoxClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        if self.wtype:
            return self.wtype
        raise InternalError(
            "Cannot resolve wtype of generic EB until the index method is called with the "
            "generic type parameter."
        )

    def __init__(self, location: SourceLocation) -> None:
        super().__init__(location)
        self.wtype: wtypes.WBoxProxy | None = None

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        match index:
            case TypeClassExpressionBuilder() as eb:
                content_wtype = eb.produces()
                self.wtype = wtypes.WBoxProxy.from_content_type(content_wtype)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        return self

    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        match indexes:
            case [TypeClassExpressionBuilder() as eb]:
                content_wtype = eb.produces()
                self.wtype = wtypes.WBoxProxy.from_content_type(content_wtype)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        return self

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        arg_map = get_arg_mapping(
            positional_arg_names=("_type",),
            args=zip(arg_names, args, strict=True),
            location=location,
        )
        type_arg_wtype = require_type_class_eb(arg_map.pop("_type")).produces()
        if not self.wtype:
            self.wtype = wtypes.WBoxProxy.from_content_type(type_arg_wtype)
        elif self.wtype.content_wtype != type_arg_wtype:
            raise CodeError(
                f"{constants.CLS_BOX_PROXY} explicit type annotation"
                f" does not match first argument - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                location,
            )

        key = expect_operand_wtype(arg_map.pop("key"), wtypes.bytes_wtype)

        if arg_map:
            raise CodeError("Invalid/unhandled arguments", location)

        return BoxProxyExpressionBuilder(
            expr=BoxProxyExpression(key=key, wtype=self.wtype, source_location=location)
        )


class BoxProxyExpressionBuilder(ValueExpressionBuilder):
    wtype: wtypes.WBoxProxy
    python_name = constants.CLS_BOX_PROXY

    def __init__(self, expr: Expression) -> None:
        if not isinstance(expr.wtype, wtypes.WBoxProxy):
            raise InternalError(
                "BoxProxyExpressionBuilder can only be created with expressions of "
                f"wtype {wtypes.WBoxProxy}",
                expr.source_location,
            )
        self.wtype = expr.wtype
        super().__init__(expr)

    def _box_key_expr(self, location: SourceLocation) -> BoxKeyExpression:
        return BoxKeyExpression(
            proxy=self.expr,
            source_location=location,
        )

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "value":
                return BoxValueExpressionBuilder(
                    box_key=self._box_key_expr(location),
                    box_value=BoxValueExpression(
                        wtype=self.wtype.content_wtype,
                        proxy=self.expr,
                        source_location=location,
                    ),
                )
            case "get":
                return BoxGetExpressionBuilder(self._box_key_expr(location))
            case "maybe":
                return BoxMaybeExpressionBuilder(self._box_key_expr(location))

        return super().member_access(name, location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        box_exists = StateExists(
            field=self._box_key_expr(location),
            source_location=location,
        )
        return BoolExpressionBuilder(
            Not(expr=box_exists, source_location=location) if negate else box_exists
        )


class BoxValueExpressionBuilder(ValueProxyExpressionBuilder):
    def __init__(self, *, box_key: BoxKeyExpression, box_value: BoxValueExpression) -> None:
        self.wtype = box_value.wtype
        super().__init__(box_value)
        self.box_key = box_key
        self.box_value = box_value

    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.box_key, source_location=location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                return UInt64ExpressionBuilder(
                    BoxLength(box_key=self.box_key, source_location=location)
                )
            case "bytes":
                return BoxValueBytesExpressionBuilder(
                    box_key=self.box_key, box_value=self.box_value
                )
            case _:
                return super().member_access(name, location)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if self.wtype != wtypes.bytes_wtype:
            return super().index(index, location)
        return index_box_bytes(self.box_key, index, location)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if self.wtype != wtypes.bytes_wtype:
            return super().slice_index(begin_index, end_index, stride, location)

        return slice_box_bytes(self.box_key, begin_index, end_index, stride, location)


class BoxValueBytesExpressionBuilder(ValueProxyExpressionBuilder):
    def __init__(self, *, box_key: BoxKeyExpression, box_value: BoxValueExpression) -> None:
        self.wtype = wtypes.bytes_wtype
        super().__init__(get_bytes_expr(box_value))
        self.box_key = box_key
        self.box_value = box_value

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                return UInt64ExpressionBuilder(
                    BoxLength(box_key=self.box_key, source_location=location)
                )
            case _:
                return super().member_access(name, location)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return index_box_bytes(self.box_key, index, location)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        return slice_box_bytes(self.box_key, begin_index, end_index, stride, location)
