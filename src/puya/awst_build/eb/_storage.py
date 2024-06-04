from __future__ import annotations

import typing

from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    ContractReference,
    Expression,
    Lvalue,
    Statement,
)
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._utils import cast_to_bytes
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    Iteration,
    LiteralBuilder,
    NodeBuilder,
    StorageProxyConstructorResult,
)
from puya.errors import CodeError

if typing.TYPE_CHECKING:

    from puya.parse import SourceLocation


class StorageProxyDefinitionBuilder(StorageProxyConstructorResult):
    def __init__(
        self,
        typ: pytypes.StorageProxyType | pytypes.StorageMapProxyType,
        location: SourceLocation,
        description: str | None,
        initial_value: Expression | None = None,
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
        return AppStorageDeclaration(
            description=self.description,
            member_name=member_name,
            key_override=None,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )

    @typing.override
    def serialize_bytes(self, location: SourceLocation) -> Expression:
        return self._assign_first(location)

    @typing.override
    def resolve(self) -> Expression:
        return self._assign_first(self.source_location)

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


def extract_key_override(
    key_arg: NodeBuilder | None, location: SourceLocation, *, is_prefix: bool
) -> Expression | None:
    key_override: Expression | None
    match key_arg:
        case None:
            key_override = None
        case LiteralBuilder(value=bytes(bytes_value), source_location=key_lit_loc):
            key_override = BytesConstant(
                value=bytes_value, encoding=BytesEncoding.unknown, source_location=key_lit_loc
            )
        case LiteralBuilder(value=str(str_value), source_location=key_lit_loc):
            key_override = BytesConstant(
                value=str_value.encode("utf8"),
                encoding=BytesEncoding.utf8,
                source_location=key_lit_loc,
            )
        case InstanceBuilder(pytype=pytypes.BytesType) as eb:
            key_override = eb.resolve()
        case InstanceBuilder(pytype=pytypes.StringType) as eb:
            key_override = cast_to_bytes(eb, location)
        case _:
            raise CodeError(
                f"invalid type for key{'_prefix' if is_prefix else ''}  argument",
                key_arg.source_location,
            )
    return key_override


def extract_description(descr_arg: NodeBuilder | None) -> str | None:
    match descr_arg:
        case None:
            return None
        case LiteralBuilder(value=str(str_value)):
            return str_value
        case _:
            raise CodeError("description should be a str literal", descr_arg.source_location)
