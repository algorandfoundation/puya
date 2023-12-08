from wyvern.awst.nodes import Expression
from wyvern.awst_build.eb.base import ExpressionBuilder


def var_expression(expr: Expression) -> ExpressionBuilder:
    from wyvern.awst_build.eb import type_registry

    return type_registry.var_expression(expr)
