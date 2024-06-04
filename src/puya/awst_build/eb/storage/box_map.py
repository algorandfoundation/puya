import abc
import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    BytesConstant,
    ContractReference,
    Expression,
    StateExists,
    StateGet,
    StateGetEx,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    TypeBuilder,
)
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    InstanceBuilder,
    Iteration,
    NodeBuilder,
    StorageProxyConstructorResult,
)
from puya.awst_build.eb.storage._common import BoxValueExpressionBuilder
from puya.awst_build.eb.storage._storage import StorageProxyDefinitionBuilder, extract_key_override
from puya.awst_build.eb.storage._util import box_length_checked
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import (
    expect_operand_type,
    get_arg_mapping,
    require_instance_builder,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class BoxMapTypeBuilder(TypeBuilder[pytypes.StorageMapProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericBoxMapType
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_typs, arg_names, location, result_type=self.produces())


class BoxMapClassGenericExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_typs, arg_names, location, result_type=None)


def _init(
    args: Sequence[NodeBuilder],
    arg_typs: Sequence[pytypes.PyType],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    result_type: pytypes.StorageMapProxyType | None,
) -> InstanceBuilder:
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
        return StorageProxyDefinitionBuilder(result_type, location=location, description=None)
    return _BoxMapProxyExpressionBuilderFromConstructor(
        key_prefix_override=key_prefix_override, typ=result_type
    )


class BoxMapProxyExpressionBuilder(
    BytesBackedInstanceExpressionBuilder[pytypes.StorageMapProxyType], bytes_member="key_prefix"
):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageMapProxyType)
        assert typ.generic == pytypes.GenericBoxMapType
        self._member_name = member_name
        super().__init__(typ, expr)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return BoxValueExpressionBuilder(
            self.pytype.content,
            _box_value_expr(self.resolve(), index, location, self.pytype.content.wtype),
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return _Length(location, self.resolve(), self.pytype)
            case "maybe":
                return _Maybe(location, self.resolve(), self.pytype)
            case "get":
                return _Get(location, self.resolve(), self.pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        box_exists = StateExists(
            field=_box_value_expr(self.resolve(), item, location, self.pytype.content.wtype),
            source_location=location,
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
    def iterate(self) -> Iteration:
        raise CodeError("iteration of BoxMap is not supported", self.source_location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)


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
        key_override = self.resolve()
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


class _MethodBase(FunctionBuilder, abc.ABC):
    def __init__(
        self,
        location: SourceLocation,
        box_map_expr: Expression,
        box_type: pytypes.StorageMapProxyType,
    ) -> None:
        super().__init__(location)
        self.box_map_expr = box_map_expr
        self.box_type = box_type


class _Length(_MethodBase):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        args_map = get_arg_mapping(("key",), zip(arg_names, args, strict=True), location)
        item_key = args_map.pop("key")
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        return UInt64ExpressionBuilder(
            box_length_checked(
                _box_value_expr(
                    self.box_map_expr, item_key, location, self.box_type.content.wtype
                ),
                location,
            )
        )


class _Get(_MethodBase):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        args_map = get_arg_mapping(("key", "default"), zip(arg_names, args, strict=True), location)
        item_key = args_map.pop("key")
        default_value = expect_operand_type(
            args_map.pop("default"), self.box_type.content
        ).resolve()
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        key = _box_value_expr(self.box_map_expr, item_key, location, self.box_type.content.wtype)
        result_expr = StateGet(default=default_value, field=key, source_location=location)
        return builder_for_instance(self.box_type.content, result_expr)


class _Maybe(_MethodBase):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        args_map = get_arg_mapping(("key",), zip(arg_names, args, strict=True), location)
        item_key = args_map.pop("key")
        if args_map:
            raise CodeError("Invalid/unexpected args", location)

        result_typ = pytypes.GenericTupleType.parameterise(
            [self.box_type.content, pytypes.BoolType], location
        )
        return TupleExpressionBuilder(
            StateGetEx(
                field=_box_value_expr(
                    self.box_map_expr, item_key, location, self.box_type.content.wtype
                ),
                source_location=location,
            ),
            result_typ,
        )


def _box_value_expr(
    key_prefix: Expression,
    key: NodeBuilder,
    location: SourceLocation,
    content_type: wtypes.WType,
) -> BoxValueExpression:
    key_data = require_instance_builder(key).serialize_bytes(location)
    full_key = intrinsic_factory.concat(key_prefix, key_data, location)
    return BoxValueExpression(
        key=full_key,
        wtype=content_type,
        member_name=None,  # TODO: can/should we set this??
        source_location=location,
    )
