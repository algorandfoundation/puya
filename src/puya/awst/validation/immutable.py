from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser

logger = log.get_logger(__name__)


class ImmutableValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        validator = cls()
        for module_statement in module:
            module_statement.accept(validator)

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        _validate_lvalue(expr.target)

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        super().visit_assignment_statement(statement)
        _validate_lvalue(statement.target)

    def visit_array_pop(self, expr: awst_nodes.ArrayPop) -> None:
        super().visit_array_pop(expr)
        if expr.base.wtype.immutable:
            logger.error(
                "cannot modify - object is immutable",
                location=expr.source_location,
            )

    def visit_array_extend(self, expr: awst_nodes.ArrayExtend) -> None:
        super().visit_array_extend(expr)
        if expr.base.wtype.immutable:
            logger.error(
                "cannot modify - object is immutable",
                location=expr.source_location,
            )


def _validate_lvalue(lvalue: awst_nodes.Expression) -> None:
    if isinstance(lvalue, awst_nodes.FieldExpression | awst_nodes.IndexExpression):
        if lvalue.base.wtype.immutable:
            logger.error(
                "expression is not valid as an assignment target - object is immutable",
                location=lvalue.source_location,
            )
    elif isinstance(lvalue, awst_nodes.TupleExpression):
        for item in lvalue.items:
            _validate_lvalue(item)
