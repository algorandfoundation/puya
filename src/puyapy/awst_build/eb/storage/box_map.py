import abc
import typing
from collections.abc import Callable, Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoxPrefixedKeyExpression,
    BoxValueExpression,
    Expression,
    StateExists,
    StateGet,
    StateGetEx,
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
    StorageProxyConstructorArgs,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puyapy.awst_build.eb.storage import BoxProxyExpressionBuilder
from puyapy.awst_build.eb.storage._common import BoxValueExpressionBuilder
from puyapy.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    parse_storage_proxy_constructor_args,
)
from puyapy.awst_build.eb.storage._util import box_length_checked
from puyapy.awst_build.eb.tuple import TupleExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


class BoxMapTypeBuilder(TypeBuilder[pytypes.StorageMapProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericBoxMapType
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


class BoxMapGenericTypeExpressionBuilder(GenericTypeBuilder):
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
        result_type = pytypes.GenericBoxMapType.parameterise([key, content], location)
    elif not (result_type.key == key and result_type.content == content):
        logger.error(
            "explicit type annotation does not match first argument"
            " - suggest to remove the explicit type annotation, it shouldn't be required",
            location=location,
        )

    typed_args = parse_storage_proxy_constructor_args(
        arg_mapping,
        key_wtype=wtypes.box_key,
        key_arg_name=key_prefix_arg_name,
        descr_arg_name=None,
        location=location,
    )

    if typed_args.key is None:
        return StorageProxyDefinitionBuilder(typed_args, result_type, location)
    return _BoxMapProxyExpressionBuilderFromConstructor(typed_args, result_type)


class BoxMapProxyExpressionBuilder(
    BytesBackedInstanceExpressionBuilder[pytypes.StorageMapProxyType], bytes_member="key_prefix"
):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericBoxMapType
        self._member_name = member_name
        super().__init__(typ, expr)

    def _build_box_map_key(
        self, key: InstanceBuilder, location: SourceLocation
    ) -> BoxPrefixedKeyExpression:
        return BoxPrefixedKeyExpression(
            prefix=self.resolve(),
            key=key.resolve(),
            source_location=location,
        )

    def _build_box_value(
        self, key: InstanceBuilder, location: SourceLocation
    ) -> BoxValueExpression:
        if self._member_name:
            exists_assertion_message = f"check self.{self._member_name} entry exists"
        else:
            exists_assertion_message = "check BoxMap entry exists"
        return BoxValueExpression(
            key=self._build_box_map_key(key, location),
            wtype=self.pytype.content_wtype,
            exists_assertion_message=exists_assertion_message,
            source_location=location,
        )

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return BoxValueExpressionBuilder(
            self.pytype.content, self._build_box_value(index, location)
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "box":
                return _Box(location, self._build_box_map_key, self.pytype)
            case "length":
                return _Length(location, self._build_box_value, self.pytype)
            case "maybe":
                return _Maybe(location, self._build_box_value, self.pytype)
            case "get":
                return _Get(location, self._build_box_value, self.pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        box_exists = StateExists(
            field=self._build_box_value(item, location), source_location=location
        )
        return BoolExpressionBuilder(box_exists)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing of BoxMap is not supported", location)

    @typing.override
    def iterate(self) -> typing.Never:  # pragma: no cover
        raise CodeError("iteration of BoxMap is not supported", self.source_location)

    @typing.override
    def iterable_item_type(self) -> typing.Never:
        self.iterate()

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        raise CodeError("cannot determine if a BoxMap is empty or not", location)


class _BoxMapProxyExpressionBuilderFromConstructor(
    BoxMapProxyExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(self, args: StorageProxyConstructorArgs, typ: pytypes.StorageMapProxyType):
        assert args.key is not None
        super().__init__(args.key, typ, member_name=None)
        self._args = args

    @typing.override
    @property
    def args(self) -> StorageProxyConstructorArgs:
        return self._args


BoxValueBuilder = Callable[[InstanceBuilder, SourceLocation], BoxValueExpression]
BoxKeyBuilder = Callable[[InstanceBuilder, SourceLocation], BoxPrefixedKeyExpression]


class _MethodBase(FunctionBuilder, abc.ABC):
    def __init__(
        self,
        location: SourceLocation,
        box_value_builder: BoxValueBuilder,
        box_type: pytypes.StorageMapProxyType,
    ) -> None:
        super().__init__(location)
        self.build_box_value = box_value_builder
        self.box_type = box_type


class _Box(FunctionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        box_key_builder: BoxKeyBuilder,
        box_map_type: pytypes.StorageMapProxyType,
    ) -> None:
        super().__init__(location)
        self.build_box_key = box_key_builder
        self.box_map_type = box_map_type

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
        box_type = pytypes.GenericBoxType.parameterise([self.box_map_type.content], location)
        if any_missing:
            return dummy_value(box_type, location)
        key_arg = expect.argument_of_type_else_dummy(
            args_map[key_arg_name], self.box_map_type.key, resolve_literal=True
        )
        key = self.build_box_key(key_arg, location)
        return BoxProxyExpressionBuilder(key, box_type)


class _Length(_MethodBase):
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
        if any_missing:
            return dummy_value(pytypes.UInt64Type, location)

        key_arg = expect.argument_of_type_else_dummy(
            args_map[key_arg_name], self.box_type.key, resolve_literal=True
        )
        key = self.build_box_value(key_arg, location)
        return UInt64ExpressionBuilder(box_length_checked(key, location))


class _Get(_MethodBase):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        key_arg_name = "key"
        default_arg_name = "default"
        args_map, any_missing = get_arg_mapping(
            required_positional_names=[key_arg_name],
            required_kw_only=[default_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(self.box_type.content, location)
        key_arg = expect.argument_of_type_else_dummy(args_map[key_arg_name], self.box_type.key)
        default_arg = expect.argument_of_type_else_dummy(
            args_map[default_arg_name], self.box_type.content
        )
        key = self.build_box_value(key_arg, location)
        result_expr = StateGet(default=default_arg.resolve(), field=key, source_location=location)
        return builder_for_instance(self.box_type.content, result_expr)


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
            [self.box_type.content, pytypes.BoolType], location
        )
        key_arg_name = "key"
        args_map, any_missing = get_arg_mapping(
            required_positional_names=[key_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(result_typ, location)
        item_key_inst = expect.argument_of_type_else_dummy(
            args_map[key_arg_name], self.box_type.key
        )
        key = self.build_box_value(item_key_inst, location)
        return TupleExpressionBuilder(StateGetEx(field=key, source_location=location), result_typ)
