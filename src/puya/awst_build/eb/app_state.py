from __future__ import annotations

import typing

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
    BoolConstant,
    BytesConstant,
    BytesEncoding,
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
from puya.awst_build.eb._state import StorageProxyDefinitionBuilder
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
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

    from puya.awst_build.contract_data import AppStorageDeclaration
    from puya.parse import SourceLocation


class AppStateClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericGlobalStateType
        self._storage_pytype = typ.content
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
        return _init(
            args=args,
            arg_names=arg_names,
            location=location,
            storage_wtype=self._storage_pytype.wtype,
        )


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
        return _init(args=args, arg_names=arg_names, location=location, storage_wtype=None)


def _init(
    args: Sequence[ExpressionBuilder | Literal],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    storage_wtype: wtypes.WType | None,
) -> ExpressionBuilder:
    type_or_value_arg_name = "type_or_initial_value"
    arg_mapping = get_arg_mapping(
        positional_arg_names=[type_or_value_arg_name],
        args=zip(arg_names, args, strict=True),
        location=location,
    )
    try:
        first_arg = arg_mapping.pop(type_or_value_arg_name)
    except KeyError as ex:
        raise CodeError("Required positional argument missing", location) from ex

    key_arg = arg_mapping.pop("key", None)
    descr_arg = arg_mapping.pop("description", None)
    if arg_mapping:
        raise CodeError(f"Unrecognised keyword argument(s): {", ".join(arg_mapping)}", location)

    match first_arg:
        case TypeClassExpressionBuilder() as typ_class_eb:
            argument_wtype = typ_class_eb.produces()
            initial_value = None
        case ExpressionBuilder(value_type=wtypes.WType() as argument_wtype) as value_eb:
            initial_value = value_eb.rvalue()
        case Literal(value=bool(bool_value), source_location=source_location):
            initial_value = BoolConstant(value=bool_value, source_location=source_location)
            argument_wtype = wtypes.bool_wtype
        case _:
            raise CodeError(
                "First argument must be a type reference or an initial value", location
            )

    if storage_wtype is not None and argument_wtype != storage_wtype:
        raise CodeError(
            f"{constants.CLS_GLOBAL_STATE_ALIAS} explicit type annotation"
            f" does not match first argument - suggest to remove the explicit type annotation,"
            " it shouldn't be required",
            location,
        )

    match key_arg:
        case None:
            key_override = None
        case Literal(value=bytes(bytes_value), source_location=key_lit_loc):
            key_override = BytesConstant(
                value=bytes_value, encoding=BytesEncoding.unknown, source_location=key_lit_loc
            )
        case Literal(value=str(str_value), source_location=key_lit_loc):
            key_override = BytesConstant(
                value=str_value.encode("utf8"),
                encoding=BytesEncoding.utf8,
                source_location=key_lit_loc,
            )
        case _:
            raise CodeError("key should be a string or bytes literal", key_arg.source_location)

    match descr_arg:
        case None:
            description = None
        case Literal(value=str(str_value)):
            description = str_value
        case _:
            raise CodeError("description should be a string literal", descr_arg.source_location)

    return AppStateProxyDefinitionBuilder(
        key_override=key_override,
        description=description,
        initial_value=initial_value,
        location=location,
    )


class AppStateProxyDefinitionBuilder(StorageProxyDefinitionBuilder):
    python_name = constants.CLS_GLOBAL_STATE_ALIAS
    is_prefix = False


class AppStateExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_decl: AppStorageDeclaration, location: SourceLocation) -> None:
        self.state_decl = state_decl
        super().__init__(location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        exists_expr = StateExists(field=self._build_field(location), source_location=location)
        if negate:
            expr: Expression = Not(location, exists_expr)
        else:
            expr = exists_expr
        return BoolExpressionBuilder(expr)

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
            key=self.state_decl.key,
            field_name=self.state_decl.member_name,
            wtype=self.state_decl.definition.storage_wtype,
            source_location=location,
        )


class AppStateMaybeExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, field: AppStateExpression, location: SourceLocation) -> None:
        super().__init__(location)
        self.field = field

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

    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.expr, source_location=location)
