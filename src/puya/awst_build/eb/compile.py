from __future__ import annotations

import typing

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import CompiledReference
from puya.awst_build import pytypes
from puya.awst_build.eb._base import (
    FunctionBuilder,
)
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puya.awst_build.eb.logicsig import LogicSigExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.errors import CodeError
from puya.log import get_logger
from puya.models import CompiledReferenceField

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from puya.parse import SourceLocation

logger = get_logger(__name__)


class GetCompiledProgramExpressionBuilder(FunctionBuilder):
    def __init__(self, location: SourceLocation, field: CompiledReferenceField):
        super().__init__(location)
        self.field = field

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        try:
            type_reference, *template_values = args
        except ValueError:
            raise CodeError("expected at least 1 argument, got 0", location) from None
        match type_reference:
            case NodeBuilder(
                pytype=pytypes.TypeType(typ=typ)
            ) if pytypes.ContractBaseType in typ.mro:
                artifact = typ.name
            case LogicSigExpressionBuilder(fullname=artifact):
                pass
            case _:
                artifact = ""
                logger.error("invalid program reference", location=type_reference.source_location)
        template_names = arg_names[1:]
        kwargs = dict(zip(template_names, template_values, strict=True))
        prefix = None
        template_vars = dict[str, int | bytes]()
        for template_name, template_value in kwargs.items():
            if template_name is None:
                logger.error("expected named argument", location=template_value.source_location)
            elif (
                template_name == "prefix"
                and isinstance(template_value, LiteralBuilder)
                and isinstance(template_value.value, str)
            ):
                prefix = template_value.value
            elif (
                template_name != "prefix"
                and isinstance(template_value, LiteralBuilder)
                and isinstance(template_value.value, int | bytes)
            ):
                template_vars[template_name] = template_value.value
            else:
                logger.error("unexpected argument type", location=template_value.source_location)

        if self.field in (CompiledReferenceField.approval, CompiledReferenceField.clear_state):
            return TupleExpressionBuilder(
                CompiledReference.pages_tuple(
                    artifact=artifact,
                    prefix=prefix,
                    field=self.field,
                    template_variables=template_vars,
                    source_location=location,
                ),
                pytypes.GenericTupleType.parameterise(
                    (pytypes.BytesType, pytypes.BytesType), location
                ),
            )
        elif self.field == CompiledReferenceField.account:
            return BytesExpressionBuilder(
                CompiledReference(
                    wtype=wtypes.bytes_wtype,
                    artifact=artifact,
                    prefix=prefix,
                    field=self.field,
                    template_variables=template_vars,
                    source_location=location,
                )
            )
        else:
            return UInt64ExpressionBuilder(
                CompiledReference(
                    wtype=wtypes.uint64_wtype,
                    artifact=artifact,
                    prefix=prefix,
                    field=self.field,
                    template_variables=template_vars,
                    source_location=location,
                )
            )
