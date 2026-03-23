import abc
import typing
from collections.abc import Callable, Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppAccountStateExpression,
    Expression,
    ExpressionStatement,
    MapPrefixedKeyExpression,
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
from puyapy.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
    StorageProxyConstructorArgs,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puyapy.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    parse_storage_proxy_constructor_args,
)
from puyapy.awst_build.eb.storage._util import resolve_account
from puyapy.awst_build.eb.storage._value_proxy import ValueProxyExpressionBuilder
from puyapy.awst_build.eb.storage.local_state import (
    LocalStateExpressionBuilder,
)
from puyapy.awst_build.eb.tuple import TupleExpressionBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


class LocalMapTypeBuilder(TypeBuilder[pytypes.StorageMapProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericLocalMapType
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=self.produces())


class LocalMapGenericTypeExpressionBuilder(GenericTypeBuilder):
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
    result_type: pytypes.StorageMapProxyType | None,
) -> InstanceBuilder:
    key_type_arg_name = "key_type"
    value_type_arg_name = "value_type"
    key_prefix_arg_name = "key_prefix"

    arg_mapping, _ = get_arg_mapping(
        required_positional_names=[key_type_arg_name, value_type_arg_name],
        optional_kw_only=[key_prefix_arg_name],
        args=args,
        arg_names=arg_names,
        call_location=location,
        raise_on_missing=True,
    )
    key_type_arg = arg_mapping[key_type_arg_name]
    value_type_arg = arg_mapping[value_type_arg_name]
    match key_type_arg.pytype, value_type_arg.pytype:
        case pytypes.TypeType(typ=key), pytypes.TypeType(typ=content):
            pass
        case _:
            raise CodeError("first and second arguments must be type references", location)

    if result_type is None:
        result_type = pytypes.GenericLocalMapType.parameterise([key, content], location)
    elif not (result_type.key == key and result_type.content == content):
        logger.error(
            "explicit type annotation does not match arguments"
            " - suggest to remove the explicit type annotation, it shouldn't be required",
            location=location,
        )

    typed_args = parse_storage_proxy_constructor_args(
        arg_mapping,
        key_wtype=wtypes.state_key,
        key_arg_name=key_prefix_arg_name,
        descr_arg_name=None,
        location=location,
    )

    if typed_args.key is None:
        return StorageProxyDefinitionBuilder(typed_args, result_type, location)
    return _LocalMapProxyExpressionBuilderFromConstructor(typed_args, result_type)


class LocalMapProxyExpressionBuilder(
    BytesBackedInstanceExpressionBuilder[pytypes.StorageMapProxyType], bytes_member="key_prefix"
):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericLocalMapType
        self._member_name = member_name
        super().__init__(typ, expr)

    def _build_local_map_key(
        self, key: InstanceBuilder, location: SourceLocation
    ) -> MapPrefixedKeyExpression:
        return MapPrefixedKeyExpression(
            prefix=self.resolve(),
            key=key.resolve(),
            wtype=wtypes.state_key,
            source_location=location,
        )

    def _build_local_value(
        self,
        account: InstanceBuilder,
        key: InstanceBuilder,
        location: SourceLocation,
    ) -> AppAccountStateExpression:
        account_expr = resolve_account(account)
        if self._member_name:
            exists_assertion_message = f"check self.{self._member_name} entry exists for account"
        else:
            exists_assertion_message = "check LocalMap entry exists for account"
        return AppAccountStateExpression(
            key=self._build_local_map_key(key, location),
            account=account_expr,
            wtype=self.pytype.content_wtype,
            exists_assertion_message=exists_assertion_message,
            source_location=location,
        )

    def _unpack_account_and_key(
        self, index: InstanceBuilder, location: SourceLocation
    ) -> tuple[InstanceBuilder, InstanceBuilder]:
        if not isinstance(index, StaticSizedCollectionBuilder):
            raise CodeError("LocalMap requires a tuple of (account, key) for indexing", location)
        items = index.iterate_static()
        if len(items) != 2:
            raise CodeError("LocalMap requires a tuple of (account, key) for indexing", location)
        account, key = items
        key = expect.argument_of_type_else_dummy(key, self.pytype.key, resolve_literal=True)
        return account, key

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        account, key = self._unpack_account_and_key(index, location)
        return _Value(self.pytype.content, self._build_local_value(account, key, location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "state":
                return _State(location, self._build_local_map_key, self.pytype)
            case "maybe":
                return _Maybe(location, self._build_local_value, self.pytype)
            case "get":
                return _Get(location, self._build_local_value, self.pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        account, key = self._unpack_account_and_key(item, location)
        local_exists = StateExists(
            field=self._build_local_value(account, key, location), source_location=location
        )
        return BoolExpressionBuilder(local_exists)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing of LocalMap is not supported", location)

    @typing.override
    def iterate(self) -> typing.Never:
        raise CodeError("iteration of LocalMap is not supported", self.source_location)

    @typing.override
    def iterable_item_type(self) -> typing.Never:
        self.iterate()

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        raise CodeError("cannot determine if a LocalMap is empty or not", location)


class _LocalMapProxyExpressionBuilderFromConstructor(
    LocalMapProxyExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(self, args: StorageProxyConstructorArgs, typ: pytypes.StorageMapProxyType):
        assert args.key is not None
        super().__init__(args.key, typ, member_name=None)
        self._args = args

    @typing.override
    @property
    def args(self) -> StorageProxyConstructorArgs:
        return self._args


LocalValueBuilder = Callable[
    [InstanceBuilder, InstanceBuilder, SourceLocation], AppAccountStateExpression
]
LocalKeyBuilder = Callable[[InstanceBuilder, SourceLocation], MapPrefixedKeyExpression]


class _MethodBase(FunctionBuilder, abc.ABC):
    def __init__(
        self,
        location: SourceLocation,
        local_value_builder: LocalValueBuilder,
        local_type: pytypes.StorageMapProxyType,
    ) -> None:
        super().__init__(location)
        self.build_local_value = local_value_builder
        self.local_type = local_type


class _State(FunctionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        local_key_builder: LocalKeyBuilder,
        local_map_type: pytypes.StorageMapProxyType,
    ) -> None:
        super().__init__(location)
        self.build_local_key = local_key_builder
        self.local_map_type = local_map_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        key_arg_name = "key"
        args_map, any_missing = get_arg_mapping(
            required_positional_names=[key_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        local_state_type = pytypes.GenericLocalStateType.parameterise(
            [self.local_map_type.content], location
        )
        if any_missing:
            return dummy_value(local_state_type, location)
        key_arg = expect.argument_of_type_else_dummy(
            args_map[key_arg_name], self.local_map_type.key, resolve_literal=True
        )
        key = self.build_local_key(key_arg, location)
        return LocalStateExpressionBuilder(key, local_state_type)


class _Get(_MethodBase):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        account_arg_name = "account"
        key_arg_name = "key"
        default_arg_name = "default"
        args_map, any_missing = get_arg_mapping(
            required_positional_names=[account_arg_name, key_arg_name],
            required_kw_only=[default_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(self.local_type.content, location)
        account_arg = expect.instance_builder(
            args_map[account_arg_name], default=expect.default_dummy_value(pytypes.AccountType)
        )
        key_arg = expect.argument_of_type_else_dummy(args_map[key_arg_name], self.local_type.key)
        default_arg = expect.argument_of_type_else_dummy(
            args_map[default_arg_name], self.local_type.content
        )
        field = self.build_local_value(account_arg, key_arg, location)
        result_expr = StateGet(
            default=default_arg.resolve(), field=field, source_location=location
        )
        return builder_for_instance(self.local_type.content, result_expr)


class _Maybe(_MethodBase):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        result_typ = pytypes.GenericTupleType.parameterise(
            [self.local_type.content, pytypes.BoolType], location
        )
        account_arg_name = "account"
        key_arg_name = "key"
        args_map, any_missing = get_arg_mapping(
            required_positional_names=[account_arg_name, key_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(result_typ, location)
        account_arg = expect.instance_builder(
            args_map[account_arg_name], default=expect.default_dummy_value(pytypes.AccountType)
        )
        key_arg = expect.argument_of_type_else_dummy(args_map[key_arg_name], self.local_type.key)
        field = self.build_local_value(account_arg, key_arg, location)
        return TupleExpressionBuilder(
            StateGetEx(field=field, source_location=location), result_typ
        )


class _Value(ValueProxyExpressionBuilder[pytypes.PyType, AppAccountStateExpression]):
    def delete(self, location: SourceLocation) -> Statement:
        return ExpressionStatement(StateDelete(field=self.resolve(), source_location=location))
