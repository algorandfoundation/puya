import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BoxLength,
    BoxValueExpression,
    BytesConstant,
    BytesRaw,
    ContractReference,
    Expression,
    Literal,
    StateExists,
    StateGet,
    StateGetEx,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._storage import StorageProxyDefinitionBuilder, extract_key_override
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
    StorageProxyConstructorResult,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.box.box import BoxValueExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype, get_arg_mapping, require_expression_builder
from puya.errors import CodeError
from puya.parse import SourceLocation


class BoxMapClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericBoxMapType
        self._typ = typ
        super().__init__(typ.wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        return _init(args, arg_typs, arg_names, location, result_type=self._typ)


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
        return _init(args, arg_typs, arg_names, location, result_type=None)


def _init(
    args: Sequence[ExpressionBuilder | Literal],
    arg_typs: Sequence[pytypes.PyType],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    result_type: pytypes.StorageMapProxyType | None,
) -> ExpressionBuilder:
    key_type_arg_name = "key_type"
    value_type_arg_name = "value_type"
    arg_mapping = get_arg_mapping(
        positional_arg_names=[key_type_arg_name, value_type_arg_name],
        args=zip(arg_names, zip(args, arg_typs, strict=True), strict=True),
        location=location,
    )
    try:
        _, key_type_arg_typ = arg_mapping.pop(key_type_arg_name)
        _, value_type_arg_typ = arg_mapping.pop(value_type_arg_name)
    except KeyError as ex:
        raise CodeError("Required positional argument missing", location) from ex

    key_prefix_arg, _ = arg_mapping.pop("key_prefix", (None, None))
    if arg_mapping:
        raise CodeError(f"Unrecognised keyword argument(s): {", ".join(arg_mapping)}", location)

    match key_type_arg_typ, value_type_arg_typ:
        case pytypes.TypeType(typ=key), pytypes.TypeType(typ=content):
            pass
        case _:
            raise CodeError("First and second arguments must be type references", location)
    if result_type is None:
        result_type = pytypes.GenericBoxMapType.parameterise([key, content], location)
    elif not (result_type.key == key and result_type.content == content):
        raise CodeError(
            f"{result_type.generic} explicit type annotation"
            f" does not match type arguments - suggest to remove the explicit type annotation,"
            " it shouldn't be required",
            location,
        )

    key_prefix_override = extract_key_override(key_prefix_arg, location, is_prefix=True)
    if key_prefix_override is None:
        return BoxMapProxyDefinitionBuilder(location=location, description=None)
    return _BoxMapProxyExpressionBuilderFromConstructor(
        key_prefix_override=key_prefix_override, typ=result_type
    )


class BoxMapProxyDefinitionBuilder(StorageProxyDefinitionBuilder):
    python_name = str(pytypes.GenericBoxMapType)
    is_prefix = False


class BoxMapProxyExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.bytes_wtype

    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericBoxMapType
        self._typ = typ
        self._member_name = member_name
        super().__init__(expr)

    @typing.override
    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return BoxValueExpressionBuilder(
            _box_value_expr(self.expr, index, location, self._typ.content.wtype)
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                return BoxMapLengthMethodExpressionBuilder(location, self.expr, self._typ)
            case "maybe":
                return BoxMapMaybeMethodExpressionBuilder(location, self.expr, self._typ)
            case "get":
                return BoxMapGetMethodExpressionBuilder(location, self.expr, self._typ)
            case _:
                return super().member_access(name, location)

    @typing.override
    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        box_exists = StateExists(
            field=_box_value_expr(self.expr, item, location, self._typ.content.wtype),
            source_location=location,
        )
        return BoolExpressionBuilder(box_exists)


class _BoxMapProxyExpressionBuilderFromConstructor(
    BoxMapProxyExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(self, key_prefix_override: Expression, typ: pytypes.StorageMapProxyType):
        super().__init__(key_prefix_override, typ, member_name=None)

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
                f"assigning {typ} to a member variable requires a constant value for key_prefix",
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


class BoxMapMethodExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        box_map_expr: Expression,
        box_type: pytypes.StorageMapProxyType,
    ) -> None:
        super().__init__(location)
        self.box_map_expr = box_map_expr
        self.box_type = box_type


class BoxMapLengthMethodExpressionBuilder(BoxMapMethodExpressionBuilder):
    @typing.override
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
                box_key=_box_value_expr(
                    self.box_map_expr, item_key, location, self.box_type.content.wtype
                ),
                source_location=location,
            )
        )


class BoxMapGetMethodExpressionBuilder(BoxMapMethodExpressionBuilder):
    @typing.override
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
        default_value = expect_operand_wtype(args_map.pop("default"), self.box_type.content.wtype)
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        # TODO: use pytype
        return var_expression(
            StateGet(
                default=default_value,
                field=_box_value_expr(
                    self.box_map_expr, item_key, location, self.box_type.content.wtype
                ),
                source_location=location,
            )
        )


class BoxMapMaybeMethodExpressionBuilder(BoxMapMethodExpressionBuilder):
    @typing.override
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
                field=_box_value_expr(
                    self.box_map_expr, item_key, location, self.box_type.content.wtype
                ),
                source_location=location,
            )
        )


def _box_value_expr(
    key_prefix: Expression,
    key: ExpressionBuilder | Literal,
    location: SourceLocation,
    content_type: wtypes.WType,
) -> BoxValueExpression:
    prefix = expect_operand_wtype(key_prefix, wtypes.bytes_wtype)
    key_data = require_expression_builder(key).rvalue()
    if key_data.wtype != wtypes.bytes_wtype:
        key_data = BytesRaw(expr=key_data, source_location=location)
    full_key = intrinsic_factory.concat(prefix, key_data, location)
    return BoxValueExpression(
        key=full_key,
        wtype=content_type,
        member_name=None,  # TODO: can/should we set this??
        source_location=location,
    )
