from __future__ import annotations

import typing

from puya.awst import wtypes
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
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb.base import ExpressionBuilder, StorageProxyConstructorResult
from puya.errors import CodeError

if typing.TYPE_CHECKING:

    from puya.awst_build import pytypes
    from puya.parse import SourceLocation


class StorageProxyDefinitionBuilder(ExpressionBuilder, StorageProxyConstructorResult):
    python_name: str
    is_prefix: bool

    def __init__(
        self,
        location: SourceLocation,
        description: str | None,
        initial_value: Expression | None = None,
    ):
        super().__init__(location)
        self.description = description
        self._initial_value = initial_value

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
        # if not isinstance(self.key_override, BytesConstant):
        #     raise CodeError(
        #         f"assigning {typ} to a member variable"
        #         f" requires a constant value for key{'_prefix' if self.is_prefix else ''}",
        #         location,
        #     )
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
        raise CodeError(
            f"{self.python_name} is not valid as an assignment target", self.source_location
        )

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise self._assign_first(location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return self._assign_first(location)

    @typing.override
    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._assign_first(location)

    @typing.override
    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._assign_first(location)

    @typing.override
    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        return self._assign_first(location)

    @typing.override
    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._assign_first(location)

    def _assign_first(self, location: SourceLocation) -> typing.Never:
        raise CodeError(
            f"{self.python_name} with inferred key{'_prefix' if self.is_prefix else ''}"
            " must be assigned to an instance variable before being used",
            location,
        )


def extract_key_override(
    key_arg: ExpressionBuilder | Literal | None, location: SourceLocation, *, is_prefix: bool
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
        case ExpressionBuilder(value_type=wtypes.bytes_wtype) as eb:
            key_override = eb.rvalue()
        case ExpressionBuilder(value_type=wtypes.string_wtype) as eb:
            key_override = BytesRaw(expr=eb.rvalue(), source_location=location)
        case _:
            raise CodeError(
                f"invalid type for key{'_prefix' if is_prefix else ''}  argument",
                key_arg.source_location,
            )
    return key_override


def extract_description(descr_arg: ExpressionBuilder | Literal | None) -> str | None:
    match descr_arg:
        case None:
            return None
        case Literal(value=str(str_value)):
            return str_value
        case _:
            raise CodeError("description should be a str literal", descr_arg.source_location)
