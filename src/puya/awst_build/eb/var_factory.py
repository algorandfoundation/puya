from puya.awst.nodes import Expression
from puya.awst_build import pytypes
from puya.awst_build.eb.base import ExpressionBuilder
from puya.parse import SourceLocation


def builder_for_instance(pytyp: pytypes.PyType, expr: Expression) -> ExpressionBuilder:
    from puya.awst_build.eb import type_registry

    return type_registry.builder_for_instance(pytyp, expr)


def builder_for_type(pytyp: pytypes.PyType, expr_loc: SourceLocation) -> ExpressionBuilder:
    from puya.awst_build.eb import type_registry

    return type_registry.builder_for_type(pytyp, expr_loc)
