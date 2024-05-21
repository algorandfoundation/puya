import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BoxKeyExpression,
    BoxLength,
    BoxProxyExpression,
    BoxValueExpression,
    BytesRaw,
    Expression,
    Literal,
    StateExists,
    StateGet,
    StateGetEx,
)
from puya.awst_build import constants, pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.box.box import BoxValueExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import (
    expect_operand_wtype,
    get_arg_mapping,
    require_expression_builder,
    require_type_class_eb,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class BoxMapClassGenericExpressionBuilder(GenericClassExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        arg_map = get_arg_mapping(
            positional_arg_names=(
                "key_type",
                "_type",
            ),
            args=zip(arg_names, args, strict=True),
            location=location,
        )
        key_wtype = require_type_class_eb(arg_map.pop("key_type")).produces()
        content_wtype = require_type_class_eb(arg_map.pop("_type")).produces()
        wtype = wtypes.WBoxMapProxy.from_key_and_content_type(key_wtype, content_wtype)
        key_prefix = expect_operand_wtype(
            arg_map.pop("key_prefix", Literal(value=b"", source_location=location)),
            wtypes.bytes_wtype,
        )

        if arg_map:
            raise CodeError("Invalid/unhandled arguments", location)

        return BoxMapProxyExpressionBuilder(
            expr=BoxProxyExpression(key=key_prefix, wtype=wtype, source_location=location)
        )


class BoxMapClassExpressionBuilder(TypeClassExpressionBuilder[wtypes.WBoxMapProxy]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericBoxMapType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WBoxMapProxy)
        super().__init__(wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        arg_map = get_arg_mapping(
            positional_arg_names=(
                "key_type",
                "_type",
            ),
            args=zip(arg_names, args, strict=True),
            location=location,
        )
        key_wtype = require_type_class_eb(arg_map.pop("key_type")).produces()
        content_wtype = require_type_class_eb(arg_map.pop("_type")).produces()
        wtype = self.produces()
        if wtype != wtypes.WBoxMapProxy.from_key_and_content_type(key_wtype, content_wtype):
            raise CodeError(
                f"{constants.CLS_BOX_MAP_PROXY} explicit type annotation"
                f" does not match first argument - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                location,
            )

        key_prefix = expect_operand_wtype(
            arg_map.pop("key_prefix", Literal(value=b"", source_location=location)),
            wtypes.bytes_wtype,
        )

        if arg_map:
            raise CodeError("Invalid/unhandled arguments", location)

        return BoxMapProxyExpressionBuilder(
            expr=BoxProxyExpression(key=key_prefix, wtype=wtype, source_location=location)
        )


def _box_key_expr(
    box_map_proxy: Expression, key: ExpressionBuilder | Literal, location: SourceLocation
) -> BoxKeyExpression:
    if not isinstance(box_map_proxy.wtype, wtypes.WBoxMapProxy):
        raise InternalError(f"box_map_proxy must be wtype of {wtypes.WBoxMapProxy}", location)
    key_eb = require_expression_builder(key).rvalue()
    item_key = BytesRaw(expr=key_eb, source_location=location)
    return BoxKeyExpression(proxy=box_map_proxy, item_key=item_key, source_location=location)


def _box_value_expr(
    box_map_proxy: Expression, key: ExpressionBuilder | Literal, location: SourceLocation
) -> BoxValueExpression:
    if not isinstance(box_map_proxy.wtype, wtypes.WBoxMapProxy):
        raise InternalError(f"box_map_proxy must be wtype of {wtypes.WBoxMapProxy}", location)
    key_eb = require_expression_builder(key).rvalue()
    item_key = BytesRaw(expr=key_eb, source_location=location)
    return BoxValueExpression(
        proxy=box_map_proxy,
        wtype=box_map_proxy.wtype.content_wtype,
        item_key=item_key,
        source_location=location,
    )


class BoxMapProxyExpressionBuilder(ValueExpressionBuilder):
    wtype: wtypes.WBoxMapProxy

    def __init__(self, expr: Expression, typ: pytypes.PyType | None = None):  # TODO
        self.pytyp = typ
        if not isinstance(expr.wtype, wtypes.WBoxMapProxy):
            raise InternalError(
                "BoxMapProxyExpressionBuilder can only be created with expressions of "
                f"wtype {wtypes.WBoxMapProxy}",
                expr.source_location,
            )
        self.wtype = expr.wtype
        super().__init__(expr)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return BoxValueExpressionBuilder(
            box_value=_box_value_expr(self.expr, index, location),
            box_key=_box_key_expr(self.expr, index, location),
        )

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                return BoxMapLengthMethodExpressionBuilder(location, box_map_expr=self.expr)
            case "maybe":
                return BoxMapMaybeMethodExpressionBuilder(location, box_map_expr=self.expr)
            case "get":
                return BoxMapGetMethodExpressionBuilder(location, box_map_expr=self.expr)
            case _:
                return super().member_access(name, location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        box_exists = StateExists(
            field=_box_key_expr(self.expr, item, location),
            source_location=location,
        )
        return BoolExpressionBuilder(box_exists)


class BoxMapMethodExpressionBuilder(IntermediateExpressionBuilder):
    box_wtype: wtypes.WBoxMapProxy

    def __init__(self, location: SourceLocation, box_map_expr: Expression) -> None:
        super().__init__(location)
        self.box_map_expr = box_map_expr
        if not isinstance(box_map_expr.wtype, wtypes.WBoxMapProxy):
            raise InternalError(f"box_map_expr wtype must be {wtypes.WBoxMapProxy}", location)
        self.box_wtype = box_map_expr.wtype


class BoxMapLengthMethodExpressionBuilder(BoxMapMethodExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        args_map = get_arg_mapping(("key",), zip(arg_names, args, strict=True), location)
        item_key = args_map.pop("key")
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        return UInt64ExpressionBuilder(
            BoxLength(
                box_key=_box_key_expr(self.box_map_expr, item_key, location),
                source_location=location,
            )
        )


class BoxMapGetMethodExpressionBuilder(BoxMapMethodExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        args_map = get_arg_mapping(("key", "default"), zip(arg_names, args, strict=True), location)
        item_key = args_map.pop("key")
        default_value = expect_operand_wtype(args_map.pop("default"), self.box_wtype.content_wtype)
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        # TODO: use pytype
        return var_expression(
            StateGet(
                default=default_value,
                field=_box_key_expr(self.box_map_expr, item_key, location),
                source_location=location,
            )
        )


class BoxMapMaybeMethodExpressionBuilder(BoxMapMethodExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        args_map = get_arg_mapping(("key",), zip(arg_names, args, strict=True), location)
        item_key = args_map.pop("key")
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        return TupleExpressionBuilder(
            StateGetEx(
                field=_box_key_expr(self.box_map_expr, item_key, location),
                source_location=location,
            )
        )
