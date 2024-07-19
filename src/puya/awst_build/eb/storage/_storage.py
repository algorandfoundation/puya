import typing

import attrs

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    Expression,
    Lvalue,
    ReinterpretCast,
    Statement,
)
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    Iteration,
    NodeBuilder,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puya.errors import CodeError
from puya.models import ContractReference
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


@typing.final
class StorageProxyDefinitionBuilder(StorageProxyConstructorResult):
    def __init__(
        self,
        typ: pytypes.StorageProxyType | pytypes.StorageMapProxyType,
        location: SourceLocation,
        description: str | None,
        initial_value: InstanceBuilder | None = None,
    ):
        super().__init__(location)
        self._typ = typ
        self.description = description
        self._initial_value = initial_value

    @property
    def pytype(self) -> pytypes.StorageProxyType | pytypes.StorageMapProxyType:
        return self._typ

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
        return AppStorageDeclaration(
            description=self.description,
            member_name=member_name,
            key_override=None,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )

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
    def iterate(self) -> Iteration:
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
        return StorageProxyDefinitionBuilder(
            typ=self._typ,
            location=self.source_location,
            description=self.description,
            initial_value=(self._initial_value and self._initial_value.single_eval()),
        )


def extract_key_override(
    key_arg: NodeBuilder | None, location: SourceLocation, *, typ: wtypes.WType
) -> Expression | None:
    if key_arg is None:
        return None
    if isinstance(key_arg, InstanceBuilder) and key_arg.pytype in (
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
    logger.error("unexpected argument type", location=key_arg.source_location)
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
