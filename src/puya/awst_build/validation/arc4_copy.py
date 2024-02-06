from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst_build.validation.awst_traverser import AWSTTraverser
from puya.context import CompileContext


class ARC4CopyValidator(AWSTTraverser):
    @classmethod
    def validate(cls, context: CompileContext, module_asts: dict[str, awst_nodes.Module]) -> None:
        validator = cls(context)
        for module in module_asts.values():
            for module_statement in module.body:
                module_statement.accept(validator)

    def __init__(self, context: CompileContext) -> None:
        self._context = context

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        super().visit_assignment_statement(statement)
        self._check_for_arc4_copy(statement.value)

    def _check_for_arc4_copy(self, expr: awst_nodes.Expression) -> None:
        match expr.wtype:
            case wtypes.ARC4Array() | wtypes.ARC4Struct():
                match expr:
                    case (
                        awst_nodes.ARC4ArrayEncode()
                        | awst_nodes.ARC4Encode()
                        | awst_nodes.Copy()
                        | awst_nodes.ArrayConcat()
                        | awst_nodes.SubroutineCallExpression()
                        | awst_nodes.ReinterpretCast(wtype=wtypes.ARC4StaticArray(alias="address"))
                    ):
                        return

                self._context.errors.error(
                    f"{expr.wtype} must be copied using .copy() when assigning to a new local"
                    " or being passed to a subroutine.",
                    expr.source_location,
                )

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        self._check_for_arc4_copy(expr.value)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            self._check_for_arc4_copy(arg.value)
