import abc
import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
    Expression,
    ExpressionStatement,
    Not,
    StateDelete,
    StateExists,
    StateGet,
    StateGetEx,
    Statement,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    NotIterableInstanceExpressionBuilder,
)
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StorageProxyConstructorArgs,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puyapy.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    parse_storage_proxy_constructor_args,
)
from puyapy.awst_build.eb.storage._value_proxy import ValueProxyExpressionBuilder
from puyapy.awst_build.eb.tuple import TupleExpressionBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


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
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=self._typ)


class GlobalStateGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
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
    key_arg_name = "key"
    descr_arg_name = "description"
    arg_mapping, _ = get_arg_mapping(
        required_positional_names=[type_or_value_arg_name],
        optional_kw_only=[key_arg_name, descr_arg_name],
        args=args,
        arg_names=arg_names,
        call_location=location,
        raise_on_missing=True,
    )

    match arg_mapping[type_or_value_arg_name]:
        case NodeBuilder(pytype=pytypes.TypeType(typ=content)):
            iv_builder = None
            if result_type is None:
                result_type = pytypes.GenericGlobalStateType.parameterise([content], location)
            elif result_type.content != content:
                logger.error(
                    "explicit type annotation does not match first argument"
                    " - suggest to remove the explicit type annotation, it shouldn't be required",
                    location=location,
                )
        case value_arg if result_type is not None:
            iv_builder = expect.argument_of_type_else_dummy(value_arg, result_type.content)
        case InstanceBuilder(pytype=content) as iv_builder:
            result_type = pytypes.GenericGlobalStateType.parameterise([content], location)
        case _:
            raise CodeError(
                "first argument must be a type reference or an initial value", location
            )

    typed_args = parse_storage_proxy_constructor_args(
        arg_mapping,
        key_wtype=wtypes.state_key,
        key_arg_name=key_arg_name,
        descr_arg_name=descr_arg_name,
        initial_value=iv_builder,
        location=location,
    )

    if typed_args.key is None:
        return StorageProxyDefinitionBuilder(typed_args, result_type, location)
    return _GlobalStateExpressionBuilderFromConstructor(typed_args, result_type)


class GlobalStateExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.StorageProxyType],
    BytesBackedInstanceExpressionBuilder[pytypes.StorageProxyType],
    bytes_member="key",
):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericGlobalStateType
        self.member_name: typing.Final = member_name
        super().__init__(typ, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        field = _build_field(self, location)
        exists_expr = StateExists(field=field, source_location=location)
        if negate:
            expr: Expression = Not(location, exists_expr)
        else:
            expr = exists_expr
        return BoolExpressionBuilder(expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "value":
                field = _build_field(self, location)
                return _Value(self.pytype.content, field)
            case "get":
                return _Get(self, location)
            case "maybe":
                return _Maybe(self, location)
            case _:
                return super().member_access(name, location)


def _build_field(
    self: GlobalStateExpressionBuilder, location: SourceLocation
) -> AppStateExpression:
    if self.member_name:
        exists_assertion_message = f"check self.{self.member_name} exists"
    else:
        exists_assertion_message = "check GlobalState exists"
    return AppStateExpression(
        key=self.resolve(),
        wtype=self.pytype.content_wtype,
        exists_assertion_message=exists_assertion_message,
        source_location=location,
    )


class _GlobalStateExpressionBuilderFromConstructor(
    GlobalStateExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(self, args: StorageProxyConstructorArgs, typ: pytypes.StorageProxyType):
        assert args.key is not None
        super().__init__(args.key, typ, member_name=None)
        self._args = args

    @typing.override
    @property
    def args(self) -> StorageProxyConstructorArgs:
        return self._args

    @typing.override
    def resolve(self) -> Expression:
        if self._args.initial_value is not None:
            logger.error(
                "providing an initial value is only allowed when assigning to a member variable",
                location=self.source_location,
            )
        return super().resolve()


class _MemberFunction(FunctionBuilder, abc.ABC):
    def __init__(self, base: GlobalStateExpressionBuilder, location: SourceLocation):
        super().__init__(location)
        self._base = base


class _Maybe(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        content_typ = self._base.pytype.content
        expect.no_args(args, location)
        field = _build_field(self._base, self.source_location)
        expr = StateGetEx(field=field, source_location=location)
        result_typ = pytypes.GenericTupleType.parameterise(
            [content_typ, pytypes.BoolType], location
        )
        return TupleExpressionBuilder(expr, result_typ)


class _Get(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        content_typ = self._base.pytype.content
        default_arg = expect.exactly_one_arg_of_type_else_dummy(args, content_typ, location)
        default_expr = default_arg.resolve()
        field = _build_field(self._base, self.source_location)
        expr = StateGet(field=field, default=default_expr, source_location=location)
        return builder_for_instance(content_typ, expr)


class _Value(ValueProxyExpressionBuilder[pytypes.PyType, AppStateExpression]):
    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return ExpressionStatement(StateDelete(field=self.resolve(), source_location=location))
