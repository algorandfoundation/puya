import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import TemplateVar
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


class GenericTemplateVariableExpressionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
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
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        var_name_arg_name = "variable_name"
        prefix_arg_name = "prefix"
        arg_mapping, any_missing = get_arg_mapping(
            required_positional_names=[var_name_arg_name],
            optional_kw_only=[prefix_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(self.result_type, location)

        var_name = expect.simple_string_literal(
            arg_mapping[var_name_arg_name], default=expect.default_fixed_value("")
        )

        if (prefix_arg := arg_mapping.get(prefix_arg_name)) is None:
            prefix_value = "TMPL_"
        else:
            prefix_value = expect.simple_string_literal(
                prefix_arg, default=expect.default_fixed_value("")
            )

        result_expr = TemplateVar(
            name=prefix_value + var_name,
            wtype=self.result_type.checked_wtype(location),
            source_location=location,
        )
        return builder_for_instance(self.result_type, result_expr)
