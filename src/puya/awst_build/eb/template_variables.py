from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import Literal, TemplateVar
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import get_arg_mapping
from puya.errors import CodeError
from puya.parse import SourceLocation


class GenericTemplateVariableExpressionBuilder(GenericClassExpressionBuilder):
    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> ExpressionBuilder:
        match indexes:
            case [TypeClassExpressionBuilder() as eb]:
                wtype = eb.produces()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        return TemplateVariableExpressionBuilder(location=location, wtype=wtype)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        raise CodeError("TemplateVar usage requires type parameter", location)


class TemplateVariableExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.WType):
        super().__init__(location)
        self.wtype = wtype

    def produces(self) -> wtypes.WType:
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        var_name_arg_name = "variable_name"
        arg_mapping = get_arg_mapping(
            positional_arg_names=[var_name_arg_name],
            args=zip(arg_names, args, strict=True),
            location=location,
        )

        try:
            var_name = arg_mapping.pop(var_name_arg_name)
        except KeyError as ex:
            raise CodeError("Required positional argument missing", location) from ex

        prefix_arg = arg_mapping.pop("prefix", None)
        if arg_mapping:
            raise CodeError(
                f"Unrecognised keyword argument(s): {", ".join(arg_mapping)}", location
            )
        match prefix_arg:
            case Literal(value=str(prefix_value)):
                pass
            case None:
                prefix_value = "TMPL_"
            case _:
                raise CodeError("Invalid value for prefix argument", location)

        match var_name:
            case Literal(value=str(str_value)):
                return var_expression(
                    TemplateVar(
                        name=prefix_value + str_value, source_location=location, wtype=self.wtype
                    )
                )
            case _:
                raise CodeError(
                    "TemplateVars must be declared using a string literal for the variable name"
                )
