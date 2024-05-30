import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst.nodes import (
    BoxValueExpression,
    BytesConstant,
    BytesRaw,
    ContractReference,
    Expression,
    Literal,
    Not,
    StateDelete,
    StateExists,
    Statement,
)
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._storage import StorageProxyDefinitionBuilder, extract_key_override
from puya.awst_build.eb.base import (
    GenericClassExpressionBuilder,
    InstanceExpressionBuilder,
    NodeBuilder,
    StorageProxyConstructorResult,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.box._common import BoxGetExpressionBuilder, BoxMaybeExpressionBuilder
from puya.awst_build.eb.box._util import box_length_checked, index_box_bytes, slice_box_bytes
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.utils import get_arg_mapping
from puya.errors import CodeError
from puya.parse import SourceLocation


class BoxClassExpressionBuilder(TypeClassExpressionBuilder[pytypes.StorageProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericBoxType
        self._typ = typ
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        return _init(args, arg_typs, arg_names, location, result_type=self._typ)


class BoxClassGenericExpressionBuilder(GenericClassExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        return _init(args, arg_typs, arg_names, location, result_type=None)


def _init(
    args: Sequence[NodeBuilder | Literal],
    arg_typs: Sequence[pytypes.PyType],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    result_type: pytypes.StorageProxyType | None,
) -> NodeBuilder:
    type_arg_name = "type_"
    arg_mapping = get_arg_mapping(
        positional_arg_names=[type_arg_name],
        args=zip(arg_names, zip(args, arg_typs, strict=True), strict=True),
        location=location,
    )
    try:
        _, type_arg_typ = arg_mapping.pop(type_arg_name)
    except KeyError as ex:
        raise CodeError("Required positional argument missing", location) from ex

    key_arg, _ = arg_mapping.pop("key", (None, None))
    descr_arg, _ = arg_mapping.pop("description", (None, None))
    if arg_mapping:
        raise CodeError(f"Unrecognised keyword argument(s): {", ".join(arg_mapping)}", location)

    match type_arg_typ:
        case pytypes.TypeType(typ=content):
            pass
        case _:
            raise CodeError("First argument must be a type reference", location)
    if result_type is None:
        result_type = pytypes.GenericBoxType.parameterise([content], location)
    elif result_type.content != content:
        raise CodeError(
            f"{result_type.generic} explicit type annotation"
            f" does not match first argument - suggest to remove the explicit type annotation,"
            " it shouldn't be required",
            location,
        )

    key_override = extract_key_override(key_arg, location, is_prefix=False)
    if key_override is None:
        return StorageProxyDefinitionBuilder(result_type, location=location, description=None)
    return _BoxProxyExpressionBuilderFromConstructor(key_override=key_override, typ=result_type)


class BoxProxyExpressionBuilder(InstanceExpressionBuilder[pytypes.StorageProxyType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericBoxType
        self._typ = typ
        self._member_name = member_name
        super().__init__(typ, expr)

    def _box_key_expr(self, location: SourceLocation) -> BoxValueExpression:
        return BoxValueExpression(
            key=self.expr,
            wtype=self._typ.content.wtype,
            member_name=self._member_name,
            source_location=location,
        )

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "value":
                return BoxValueExpressionBuilder(self._typ.content, self._box_key_expr(location))
            case "get":
                return BoxGetExpressionBuilder(
                    self._box_key_expr(location), content_type=self._typ.content
                )
            case "maybe":
                return BoxMaybeExpressionBuilder(
                    self._box_key_expr(location), content_type=self._typ.content
                )

        return super().member_access(name, location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> NodeBuilder:
        box_exists = StateExists(
            field=self._box_key_expr(location),
            source_location=location,
        )
        return BoolExpressionBuilder(
            Not(expr=box_exists, source_location=location) if negate else box_exists
        )


class _BoxProxyExpressionBuilderFromConstructor(
    BoxProxyExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(self, key_override: Expression, typ: pytypes.StorageProxyType):
        super().__init__(key_override, typ, member_name=None)

    @typing.override
    @property
    def initial_value(self) -> Expression | None:
        return None

    @typing.override
    def build_definition(
        self,
        member_name: str,
        defined_in: ContractReference,
        typ: pytypes.PyType,
        location: SourceLocation,
    ) -> AppStorageDeclaration:
        key_override = self.expr
        if not isinstance(key_override, BytesConstant):
            raise CodeError(
                f"assigning {typ} to a member variable requires a constant value for key",
                location,
            )
        return AppStorageDeclaration(
            description=None,
            member_name=member_name,
            key_override=key_override,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )


class BoxValueExpressionBuilder(ValueProxyExpressionBuilder):
    expr: BoxValueExpression  # TODO: remove "lies"

    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.expr, source_location=location)

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "length":
                return UInt64ExpressionBuilder(box_length_checked(self.expr, location))
            case "bytes":
                return BoxValueBytesExpressionBuilder(self.expr, location)
            case _:
                return super().member_access(name, location)

    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        if self.pytype != pytypes.BytesType:
            return super().index(index, location)
        return index_box_bytes(self.expr, index, location)

    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        if self.pytype != pytypes.BytesType:
            return super().slice_index(begin_index, end_index, stride, location)

        return slice_box_bytes(self.expr, begin_index, end_index, stride, location)


class BoxValueBytesExpressionBuilder(ValueProxyExpressionBuilder):
    def __init__(self, expr: BoxValueExpression, location: SourceLocation) -> None:
        self._typed = expr
        super().__init__(pytypes.BytesType, BytesRaw(expr=expr, source_location=location))

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "length":
                return UInt64ExpressionBuilder(box_length_checked(self._typed, location))
            case _:
                return super().member_access(name, location)

    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        return index_box_bytes(self._typed, index, location)

    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        return slice_box_bytes(self._typed, begin_index, end_index, stride, location)
