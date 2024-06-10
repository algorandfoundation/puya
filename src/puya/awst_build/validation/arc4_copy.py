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

    def __init__(self) -> None:
        super().__init__()
        self._for_items: awst_nodes.Lvalue | None = None

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        _check_assignment(statement.target, statement.value)
        statement.value.accept(self)

    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> None:
        super().visit_tuple_expression(expr)
        if expr is not self._for_items:
            for item in expr.items:
                _check_for_arc4_copy(item, "being passed to a tuple expression")

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> None:
        self._for_items = statement.items
        super().visit_for_in_loop(statement)
        self._for_items = None

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        _check_assignment(expr.target, expr.value)
        expr.value.accept(self)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            match arg.value:
                case awst_nodes.VarExpression():
                    # Var expressions don't need copy as we implicitly return the latest value and
                    # update the var
                    continue
                case awst_nodes.AppStateExpression() | awst_nodes.AppAccountStateExpression():
                    message = "being passed to a subroutine from state"
                case _:
                    message = "being passed to a subroutine"
            _check_for_arc4_copy(arg.value, message)

    def visit_new_array(self, expr: awst_nodes.NewArray) -> None:
        super().visit_new_array(expr)
        if isinstance(expr.wtype, wtypes.ARC4Array):
            for v in expr.values:
                _check_for_arc4_copy(v, "being passed to an array constructor")

    def visit_new_struct(self, expr: awst_nodes.NewStruct) -> None:
        super().visit_new_struct(expr)
        if isinstance(expr.wtype, wtypes.ARC4Struct):
            for v in expr.values.values():
                _check_for_arc4_copy(v, "being passed to a struct constructor")

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> None:
        super().visit_arc4_encode(expr)

        for item in _expand_tuple_items(expr.value):
            _check_for_arc4_copy(item, "being passed to a constructor")


def _is_referable_expression(expr: awst_nodes.Expression) -> bool:
    """
    Returns True if expr represents something that can be referenced multiple times.
    """
    match expr:
        case (
            awst_nodes.VarExpression()
            | awst_nodes.AppStateExpression()
            | awst_nodes.AppAccountStateExpression()
            | awst_nodes.StateGet()
            | awst_nodes.StateGetEx()
        ):
            return True
        case (
            awst_nodes.IndexExpression(base=base_expr)
            | awst_nodes.TupleItemExpression(base=base_expr)
            | awst_nodes.FieldExpression(base=base_expr)
        ):
            return _is_referable_expression(base_expr)
    return False


def _check_assignment(target: awst_nodes.Expression, value: awst_nodes.Expression) -> None:
    if not isinstance(target, awst_nodes.TupleExpression):
        _check_for_arc4_copy(value, "being assigned to another variable")
    elif _is_referable_expression(value):
        problem_type = next((i for i in target.wtype.types if _is_arc4_mutable(i)), None)
        if problem_type:
            logger.error(
                f"Tuple cannot be destructured as it contains an item of type"
                f" {problem_type} which requires copying. Use index access instead",
                location=value.source_location,
            )


def _check_for_arc4_copy(expr: awst_nodes.Expression, context_desc: str) -> None:
    if _is_arc4_mutable(expr.wtype) and _is_referable_expression(expr):
        logger.error(
            f"{expr.wtype} must be copied using .copy() when {context_desc}",
            location=expr.source_location,
        )


def _expand_tuple_items(expr: awst_nodes.Expression) -> Iterator[awst_nodes.Expression]:
    match expr:
        case awst_nodes.TupleExpression(items=items):
            yield from items
        case _:
            yield expr


def _is_arc4_mutable(wtype: wtypes.WType) -> bool:
    """
    Returns True if expr represents an arc4 type that is mutable
    """
    match wtype:
        case wtypes.ARC4Type(immutable=False):
            return True
        case wtypes.WTuple(types=types):
            return any(_is_arc4_mutable(t) for t in types)
    return False
