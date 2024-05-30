import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst.nodes import TemplateVar
from puya.awst_build import pytypes
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puya.awst_build.utils import get_arg_mapping
from puya.errors import CodeError
from puya.parse import SourceLocation


class GenericTemplateVariableExpressionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("TemplateVar usage requires type parameter", location)


class TemplateVariableExpressionBuilder(FunctionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.PseudoGenericFunctionType)
        self.result_type = typ.return_type
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
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
            case LiteralBuilder(value=str(prefix_value)):
                pass
            case None:
                prefix_value = "TMPL_"
            case _:
                raise CodeError("Invalid value for prefix argument", location)

        match var_name:
            case LiteralBuilder(value=str(str_value)):
                result_expr = TemplateVar(
                    name=prefix_value + str_value,
                    wtype=self.result_type.wtype,
                    source_location=location,
                )
                return builder_for_instance(self.result_type, result_expr)
            case _:
                raise CodeError(
                    "TemplateVars must be declared using a string literal for the variable name"
                )
