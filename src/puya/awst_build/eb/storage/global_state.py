import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
    BytesConstant,
    ContractReference,
    Expression,
    Not,
    StateDelete,
    StateExists,
    StateGet,
    StateGetEx,
    Statement,
)
from puya.awst_build import constants, pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    NotIterableInstanceExpressionBuilder,
)
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puya.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    extract_description,
    extract_key_override,
)
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.utils import get_arg_mapping
from puya.errors import CodeError
from puya.parse import SourceLocation


class GlobalStateTypeBuilder(TypeBuilder[pytypes.StorageProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericGlobalStateType
        self._typ = typ
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=self._typ)


class GlobalStateGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=None)


def _init(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    result_type: pytypes.StorageProxyType | None,
) -> InstanceBuilder:
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
        case NodeBuilder(pytype=pytypes.TypeType(typ=content)):
            iv_builder = None
        case InstanceBuilder(pytype=content) as iv_builder:
            pass
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

    key_override = extract_key_override(key_arg, location, typ=wtypes.state_key, is_prefix=False)
    description = extract_description(descr_arg)
    if key_override is None:
        return StorageProxyDefinitionBuilder(
            result_type, location=location, description=description, initial_value=iv_builder
        )
    return _GlobalStateExpressionBuilderFromConstructor(
        key_override=key_override,
        typ=result_type,
        description=description,
        initial_value=iv_builder,
    )


class GlobalStateExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.StorageProxyType],
    BytesBackedInstanceExpressionBuilder[pytypes.StorageProxyType],
    bytes_member="key",
):

    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericGlobalStateType
        self._member_name = member_name
        super().__init__(typ, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        exists_expr = StateExists(field=self._build_field(location), source_location=location)
        if negate:
            expr: Expression = Not(location, exists_expr)
        else:
            expr = exists_expr
        return BoolExpressionBuilder(expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        field = self._build_field(location)
        match name:
            case "value":
                return _Value(self.pytype.content, field)
            case "get":
                return _Get(field, self.pytype.content, location=self.source_location)
            case "maybe":
                return _Maybe(self.pytype.content, field, location=self.source_location)
            case _:
                return super().member_access(name, location)

    def _build_field(self, location: SourceLocation) -> AppStateExpression:
        if self._member_name:
            exists_assertion_message = f"check self.{self._member_name} exists"
        else:
            exists_assertion_message = "check GlobalState exists"
        return AppStateExpression(
            key=self.resolve(),
            wtype=self.pytype.content.wtype,
            exists_assertion_message=exists_assertion_message,
            source_location=location,
        )


class _GlobalStateExpressionBuilderFromConstructor(
    GlobalStateExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(
        self,
        key_override: Expression,
        typ: pytypes.StorageProxyType,
        description: str | None,
        initial_value: InstanceBuilder | None,
    ):
        super().__init__(key_override, typ, member_name=None)
        self.description = description
        self._initial_value = initial_value

    @typing.override
    @property
    def initial_value(self) -> InstanceBuilder | None:
        return self._initial_value

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


class _Maybe(FunctionBuilder):
    def __init__(
        self, content_type: pytypes.PyType, field: AppStateExpression, location: SourceLocation
    ) -> None:
        super().__init__(location)
        self._typ = content_type
        self.field = field

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if args:
            raise CodeError("Unexpected/unhandled arguments", location)
        expr = StateGetEx(field=self.field, source_location=location)
        result_typ = pytypes.GenericTupleType.parameterise([self._typ, pytypes.BoolType], location)
        return TupleExpressionBuilder(expr, result_typ)


class _Get(FunctionBuilder):
    def __init__(
        self, field: AppStateExpression, content_type: pytypes.PyType, location: SourceLocation
    ) -> None:
        super().__init__(location)
        self.field = field
        self.content_type = content_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [InstanceBuilder(pytype=self.content_type) as eb]:
                default_expr = eb.resolve()
            case _:
                raise CodeError("invalid/unexpected args", location)
        expr = StateGet(field=self.field, default=default_expr, source_location=location)
        return builder_for_instance(self.content_type, expr)


class _Value(ValueProxyExpressionBuilder[pytypes.PyType, AppStateExpression]):
    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.resolve(), source_location=location)
