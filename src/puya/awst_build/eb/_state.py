from __future__ import annotations

import typing

from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb.base import ExpressionBuilder, StorageProxyConstructorResult
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from puya.awst.nodes import (
        BytesConstant,
        ContractReference,
        Expression,
        Literal,
        Lvalue,
        Statement,
    )
    from puya.awst_build import pytypes
    from puya.parse import SourceLocation


class StorageProxyDefinitionBuilder(ExpressionBuilder, StorageProxyConstructorResult):
    python_name: str
    is_prefix: bool

    def __init__(
        self,
        location: SourceLocation,
        key_override: BytesConstant | None,
        description: str | None,
        initial_value: Expression | None = None,
    ):
        super().__init__(location)
        self.key_override = key_override
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
        return AppStorageDeclaration(
            description=self.description,
            member_name=member_name,
            key_override=self.key_override,
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
