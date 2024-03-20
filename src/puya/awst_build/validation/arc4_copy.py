import structlog

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst_build.validation.awst_traverser import AWSTTraverser

logger = structlog.get_logger(__name__)


class ARC4CopyValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        validator = cls()
        for module_statement in module.body:
            module_statement.accept(validator)

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        super().visit_assignment_statement(statement)
        self._check_for_arc4_copy(statement.value)

    def _check_for_arc4_copy(self, expr: awst_nodes.Expression) -> None:
        match expr.wtype:
            case wtypes.ARC4Type(immutable=False):
                match expr:
                    case (
                        awst_nodes.ARC4ArrayEncode()
                        | awst_nodes.ARC4Encode()
                        | awst_nodes.Copy()
                        | awst_nodes.ArrayConcat()
                        | awst_nodes.SubroutineCallExpression()
                        | awst_nodes.ReinterpretCast()
                    ):
                        return

                logger.error(
                    f"{expr.wtype} must be copied using .copy() when assigning to a new local"
                    " or being passed to a subroutine.",
                    location=expr.source_location,
                )

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        self._check_for_arc4_copy(expr.value)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            if isinstance(arg.value, awst_nodes.VarExpression):
                continue
            self._check_for_arc4_copy(arg.value)

    def visit_arc4_array_encode(self, expr: awst_nodes.ARC4ArrayEncode) -> None:
        super().visit_arc4_array_encode(expr)
        for v in expr.values:
            self._check_for_arc4_copy(v)

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> None:
        super().visit_arc4_encode(expr)

        match expr.value:
            case awst_nodes.TupleExpression(items=items):
                for item in items:
                    self._check_for_arc4_copy(item)
            case _:
                self._check_for_arc4_copy(expr.value)
