from __future__ import annotations

import typing

from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    BytesRaw,
    ContractReference,
    Expression,
    Literal,
    Lvalue,
    Statement,
)
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb.base import BuilderUnaryOp, NodeBuilder, StorageProxyConstructorResult
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
    def rvalue(self) -> Expression:
        return self._assign_first(self.source_location)

    @typing.override
    def lvalue(self) -> Lvalue:
        raise CodeError(f"{self._typ} is not valid as an assignment target", self.source_location)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise self._assign_first(location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> NodeBuilder:
        return self._assign_first(location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> NodeBuilder:
        return self._assign_first(location)

    @typing.override
    def contains(self, item: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        return self._assign_first(location)

    def _assign_first(self, location: SourceLocation) -> typing.Never:
        raise CodeError(
            f"{self._typ} with inferred"
            f" key{'_prefix' if isinstance(self._typ, pytypes.StorageMapProxyType) else ''}"
            " must be assigned to an instance variable before being used",
            location,
        )


def extract_key_override(
    key_arg: NodeBuilder | Literal | None, location: SourceLocation, *, is_prefix: bool
) -> Expression | None:
    key_override: Expression | None
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
        case NodeBuilder(pytype=pytypes.BytesType) as eb:
            key_override = eb.rvalue()
        case NodeBuilder(pytype=pytypes.StringType) as eb:
            key_override = BytesRaw(expr=eb.rvalue(), source_location=location)
        case _:
            raise CodeError(
                f"invalid type for key{'_prefix' if is_prefix else ''}  argument",
                key_arg.source_location,
            )
    return key_override


def extract_description(descr_arg: NodeBuilder | Literal | None) -> str | None:
    match descr_arg:
        case None:
            return None
        case Literal(value=str(str_value)):
            return str_value
        case _:
            raise CodeError("description should be a str literal", descr_arg.source_location)
