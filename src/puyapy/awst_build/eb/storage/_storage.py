import typing

import attrs

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BinaryBooleanOperator,
    BytesConstant,
    BytesEncoding,
    Expression,
    Lvalue,
    ReinterpretCast,
    Statement,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    NodeBuilder,
    StorageProxyConstructorArgs,
    StorageProxyConstructorResult,
    TypeBuilder,
)

logger = log.get_logger(__name__)


@typing.final
class StorageProxyDefinitionBuilder(StorageProxyConstructorResult):
    def __init__(
        self,
        args: StorageProxyConstructorArgs,
        typ: pytypes.StorageProxyType | pytypes.StorageMapProxyType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self._typ = typ
        self._args = args

    @typing.override
    @property
    def args(self) -> StorageProxyConstructorArgs:
        return self._args

    @typing.override
    @property
    def pytype(self) -> pytypes.StorageProxyType | pytypes.StorageMapProxyType:
        return self._typ

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return self._assign_first(location)

    @typing.override
    def resolve(self) -> Expression:
        return self._assign_first(self.source_location)

    @typing.override
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        return self.try_resolve_literal(converter)

    @typing.override
    def try_resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        return self

    @typing.override
    def resolve_lvalue(self) -> Lvalue:
        raise CodeError(f"{self._typ} is not valid as an assignment target", self.source_location)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise self._assign_first(location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def iterate(self) -> Expression:
        return self._assign_first(self.source_location)

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self._assign_first(self.source_location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        return self._assign_first(location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        return self._assign_first(location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        return self._assign_first(location)

    def _assign_first(self, location: SourceLocation) -> typing.Never:
        raise CodeError(
            f"{self._typ} with inferred"
            f" key{'_prefix' if isinstance(self._typ, pytypes.StorageMapProxyType) else ''}"
            " must be assigned to an instance variable before being used",
            location,
        )

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        if self._args.initial_value is None:
            return self
        return StorageProxyDefinitionBuilder(
            attrs.evolve(self._args, initial_value=self._args.initial_value.single_eval()),
            typ=self._typ,
            location=self.source_location,
        )


def extract_key_override(
    key_arg: NodeBuilder | None, location: SourceLocation, *, typ: wtypes.WType
) -> Expression | None:
    if key_arg is None:
        return None
    if isinstance(key_arg, InstanceBuilder) and key_arg.pytype.is_type_or_subtype(
        pytypes.StringType,
        pytypes.StrLiteralType,
        pytypes.BytesType,
        pytypes.BytesLiteralType,
    ):
        key_override = key_arg.to_bytes(key_arg.source_location)
        if isinstance(key_override, BytesConstant):
            return attrs.evolve(key_override, wtype=typ)
        else:
            return ReinterpretCast(expr=key_override, wtype=typ, source_location=location)
    else:
        expect.not_this_type(key_arg, default=expect.default_none)
        return BytesConstant(
            value=b"0",
            wtype=typ,
            encoding=BytesEncoding.unknown,
            source_location=key_arg.source_location,
        )


def extract_description(descr_arg: NodeBuilder | None) -> str | None:
    if descr_arg is None:
        return None
    return expect.simple_string_literal(descr_arg, default=expect.default_none)


def parse_storage_proxy_constructor_args(
    arg_mapping: dict[str, NodeBuilder],
    key_wtype: wtypes.WType,
    key_arg_name: str,
    descr_arg_name: str | None,
    location: SourceLocation,
    initial_value: InstanceBuilder | None = None,
) -> StorageProxyConstructorArgs:
    key_arg = arg_mapping.get(key_arg_name)
    key_override = extract_key_override(key_arg, location, typ=key_wtype)

    description = None
    if descr_arg_name is not None:
        descr_arg = arg_mapping.get(descr_arg_name)
        description = extract_description(descr_arg)

    return StorageProxyConstructorArgs(
        key=key_override,
        description=description,
        initial_value=initial_value,
        key_arg_name=key_arg_name,
    )
