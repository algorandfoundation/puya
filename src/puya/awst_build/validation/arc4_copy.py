from collections.abc import Iterator

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst_build.validation.awst_traverser import AWSTTraverser

logger = log.get_logger(__name__)


class ARC4CopyValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        validator = cls()
        for module_statement in module.body:
            module_statement.accept(validator)

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        self._check_for_arc4_tuple_destructure(statement.target, statement.value)
        statement.value.accept(self)
        self._check_for_arc4_copy(statement.value, "being assigned to another variable")

    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> None:
        super().visit_tuple_expression(expr)
        for item in expr.items:
            self._check_for_arc4_copy(item, "being passed to a tuple expression")

    @staticmethod
    def _is_referable_expression(expr: awst_nodes.Expression) -> bool:
        """
        Returns True if expr represents something that can be referenced multiple times.
        """
        match expr:
            case (
                awst_nodes.VarExpression()
                | awst_nodes.AppStateExpression()
                | awst_nodes.AppAccountStateExpression()
            ):
                return True
        return False

    @staticmethod
    def _is_arc4_mutable(wtype: wtypes.WType) -> bool:
        """
        Returns True if expr represents an arc4 type that is mutable
        """
        match wtype:
            case wtypes.ARC4Type(immutable=False):
                return True
        return False

    def _check_for_arc4_tuple_destructure(
        self, target: awst_nodes.Expression, value: awst_nodes.Expression
    ) -> None:
        if not isinstance(target, awst_nodes.TupleExpression):
            return
        match value.wtype:
            case wtypes.WTuple(types=item_types):
                if self._is_referable_expression(value):
                    problem_type = next((i for i in item_types if self._is_arc4_mutable(i)), None)
                    if problem_type:
                        logger.error(
                            f"Tuple cannot be destructured as it contains an item of type"
                            f" {problem_type} which requires copying. Use index access instead",
                            location=value.source_location,
                        )

    def _check_for_arc4_copy(self, expr: awst_nodes.Expression, context_desc: str) -> None:
        if self._is_arc4_mutable(expr.wtype):
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
                f"{expr.wtype} must be copied using .copy() when {context_desc}",
                location=expr.source_location,
            )

    @staticmethod
    def _expand_tuple_items(expr: awst_nodes.Expression) -> Iterator[awst_nodes.Expression]:
        match expr:
            case awst_nodes.TupleExpression(items=items):
                yield from items
            case _:
                yield expr

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> None:
        if not isinstance(statement.sequence, awst_nodes.Range):
            statement.sequence.accept(self)
        statement.loop_body.accept(self)

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        self._check_for_arc4_tuple_destructure(expr.target, expr.value)

        expr.value.accept(self)
        self._check_for_arc4_copy(expr.value, "being assigned to another variable")

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            match arg.value:
                case awst_nodes.VarExpression():
                    # Var expressions don't need copy as we implicitly return the latest value and
                    # update the var
                    continue
                case (awst_nodes.AppStateExpression() | awst_nodes.AppAccountStateExpression()):
                    message = "being passed to a subroutine from state"
                case _:
                    message = "being passed to a subroutine"
            self._check_for_arc4_copy(arg.value, message)

    def visit_arc4_array_encode(self, expr: awst_nodes.ARC4ArrayEncode) -> None:
        super().visit_arc4_array_encode(expr)
        for v in expr.values:
            self._check_for_arc4_copy(v, "being passed to an array constructor")

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> None:
        super().visit_arc4_encode(expr)

        for item in self._expand_tuple_items(expr.value):
            self._check_for_arc4_copy(item, "being passed to a constructor")
