from __future__ import annotations

import typing

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
    BytesConstant,
    ContractReference,
    Expression,
    Literal,
    Not,
    StateDelete,
    StateExists,
    StateGet,
    StateGetEx,
    Statement,
)
from puya.awst_build import constants, pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._storage import (
    StorageProxyDefinitionBuilder,
    extract_description,
    extract_key_override,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
    StorageProxyConstructorResult,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype, get_arg_mapping
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation


class AppStateClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericGlobalStateType
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


class AppStateGenericClassExpressionBuilder(GenericClassExpressionBuilder):
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
    result_type: pytypes.StorageProxyType | None,
) -> ExpressionBuilder:
    type_or_value_arg_name = "type_or_initial_value"
    arg_mapping = get_arg_mapping(
        positional_arg_names=[type_or_value_arg_name],
        args=zip(arg_names, zip(args, arg_typs, strict=True), strict=True),
        location=location,
    )
    try:
        first_arg, first_arg_typ = arg_mapping.pop(type_or_value_arg_name)
    except KeyError as ex:
        raise CodeError("Required positional argument missing", location) from ex

    key_arg, _ = arg_mapping.pop("key", (None, None))
    descr_arg, _ = arg_mapping.pop("description", (None, None))
    if arg_mapping:
        raise CodeError(f"Unrecognised keyword argument(s): {", ".join(arg_mapping)}", location)

    match first_arg_typ:
        case pytypes.TypeType(typ=content):
            initial_value = None
        case pytypes.PyType() as content:
            initial_value = expect_operand_wtype(first_arg, content.wtype)
        case _:
            raise CodeError(
                "First argument must be a type reference or an initial value", location
            )

    if result_type is None:
        result_type = pytypes.GenericGlobalStateType.parameterise([content], location)
    elif result_type.content != content:
        raise CodeError(
            f"{constants.CLS_GLOBAL_STATE_ALIAS} explicit type annotation"
            f" does not match first argument - suggest to remove the explicit type annotation,"
            " it shouldn't be required",
            location,
        )

    key_override = extract_key_override(key_arg, location, is_prefix=False)
    description = extract_description(descr_arg)
    if key_override is None:
        return AppStateProxyDefinitionBuilder(
            location=location, description=description, initial_value=initial_value
        )
    return _AppStateExpressionBuilderFromConstructor(
        key_override=key_override,
        typ=result_type,
        description=description,
        initial_value=initial_value,
    )


class AppStateProxyDefinitionBuilder(StorageProxyDefinitionBuilder):
    python_name = constants.CLS_GLOBAL_STATE_ALIAS
    is_prefix = False


class AppStateExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.bytes_wtype

    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericGlobalStateType
        self._typ = typ
        self._member_name = member_name
        super().__init__(expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        exists_expr = StateExists(field=self._build_field(location), source_location=location)
        if negate:
            expr: Expression = Not(location, exists_expr)
        else:
            expr = exists_expr
        return BoolExpressionBuilder(expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        field = self._build_field(self.source_location)
        match name:
            case "value":
                return AppStateValueExpressionBuilder(field)
            case "get":
                return AppStateGetExpressionBuilder(field, location=self.source_location)
            case "maybe":
                return AppStateMaybeExpressionBuilder(field, location=self.source_location)
            case _:
                return super().member_access(name, location)

    def _build_field(self, location: SourceLocation) -> AppStateExpression:
        return AppStateExpression(
            key=self.expr,
            field_name=self._member_name,
            wtype=self._typ.content.wtype,
            source_location=location,
        )


class _AppStateExpressionBuilderFromConstructor(
    AppStateExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(
        self,
        key_override: Expression,
        typ: pytypes.StorageProxyType,
        description: str | None,
        initial_value: Expression | None,
    ):
        super().__init__(key_override, typ, member_name=None)
        self.description = description
        self._initial_value = initial_value

    @typing.override
    @property
    def initial_value(self) -> Expression | None:
        return self._initial_value

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
            description=self.description,
            member_name=member_name,
            key_override=key_override,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )


class AppStateMaybeExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, field: AppStateExpression, location: SourceLocation) -> None:
        super().__init__(location)
        self.field = field

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if args:
            raise CodeError("Unexpected/unhandled arguments", location)
        expr = StateGetEx(field=self.field, source_location=location)
        return TupleExpressionBuilder(expr)


class AppStateGetExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, field: AppStateExpression, location: SourceLocation) -> None:
        super().__init__(location)
        self.field = field

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        (default_arg,) = args
        default_expr = expect_operand_wtype(default_arg, target_wtype=self.field.wtype)
        expr = StateGet(field=self.field, default=default_expr, source_location=location)
        return var_expression(expr)


class AppStateValueExpressionBuilder(ValueProxyExpressionBuilder):
    expr: AppStateExpression

    def __init__(self, expr: AppStateExpression):
        self.wtype = expr.wtype
        super().__init__(expr)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.expr, source_location=location)
