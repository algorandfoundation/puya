import contextlib
from collections.abc import Iterator

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.awst.wtypes import WInnerTransaction, WInnerTransactionFields
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

INNER_TRANSACTION_ASSIGNMENT_EXPRESSION_ERROR = (
    "inner transactions cannot be used in assignment expressions"
)
INNER_TRANSACTION_COPY_REQUIRED_ERROR = (
    "inner transaction fields must be copied using .copy() when assigning to a new local"
)
INNER_TRANSACTION_LOOP_MODIFICATION_ERROR = (
    "inner transaction fields cannot be modified after submission while in a loop"
)
INNER_TRANSACTION_MAYBE_STALE_ERROR = (
    "inner transaction array field can not be reliably accessed due to other inner transaction "
    " submissions or subroutine calls, move array field access closer to {stale_var!r} definition"
)
INNER_TRANSACTION_MAYBE_STALE_WARNING = (
    "inner transaction {stale_var!r} potentially becomes stale here"
)
INNER_TRANSACTION_SOURCE_ERROR = "inner transactions can not be used like this"
INNER_TRANSACTION_SUBROUTINE_ERROR = (
    "inner transactions cannot be used as a subroutine argument or return value"
)


class InnerTransactionsValidator(AWSTTraverser):
    """
    Validates that expressions of type WInnerTransaction and WInnerTransactionFields are only
    used in the ways currently supported. Emits errors for:

    Reassigning expressions of type WInnerTransaction
    Reassigning expressions of type WInnerTransactionFields without a copy()
    Using WInnerTransaction or WInnerTransactionFields in a subroutine or assignment expression
    """

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        _check_method_types(statement)
        super().visit_contract_method(statement)

    def visit_subroutine(self, statement: awst_nodes.Subroutine) -> None:
        _check_method_types(statement)
        super().visit_subroutine(statement)

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        self._check_inner_transaction_assignment(statement.value)
        self._check_inner_transaction_fields_assignment(statement.value)
        super().visit_assignment_statement(statement)

    def _check_inner_transaction_assignment(self, value: awst_nodes.Expression) -> None:
        if _is_itxn_wtype(value.wtype) and not _is_assignable_itxn_expr(value):
            logger.debug(
                f"Inner transaction expression is not assignable {value.accept(ToCodeVisitor())}"
            )
            logger.error(INNER_TRANSACTION_SOURCE_ERROR, location=value.source_location)

    def _check_inner_transaction_fields_assignment(self, value: awst_nodes.Expression) -> None:
        match value:
            case awst_nodes.CreateInnerTransaction() | awst_nodes.Copy():
                pass  # ok
            case (
                awst_nodes.VarExpression(wtype=wtype)
                | awst_nodes.TupleItemExpression(wtype=wtype)
            ) if isinstance(wtype, WInnerTransactionFields):
                logger.error(
                    INNER_TRANSACTION_COPY_REQUIRED_ERROR,
                    location=value.source_location,
                )
            case awst_nodes.Expression(wtype=wtype) if (
                isinstance(wtype, WInnerTransactionFields)
            ):
                logger.debug(
                    f"Inner transaction fields are not assignable {value.accept(ToCodeVisitor())}"
                )
                logger.error(
                    INNER_TRANSACTION_SOURCE_ERROR,
                    location=value.source_location,
                )

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        if _is_either_itxn_wtype(expr.wtype):
            logger.error(
                INNER_TRANSACTION_ASSIGNMENT_EXPRESSION_ERROR,
                location=expr.source_location,
            )

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            if _is_either_itxn_wtype(arg.value.wtype):
                logger.error(
                    INNER_TRANSACTION_SUBROUTINE_ERROR,
                    location=expr.source_location,
                )


class InnerTransactionUsedInALoopValidator(AWSTTraverser):
    """
    Validates that expressions of type WInnerTransactionFields are not modified after submission
    while in a loop
    Modifying after submission while in a loop
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_itxn_var_stack = list[list[str]]()

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    @property
    def _current_loop_itxn_vars(self) -> list[str] | None:
        return self._current_itxn_var_stack[-1] if self._current_itxn_var_stack else None

    @contextlib.contextmanager
    def _enter_loop(self) -> Iterator[None]:
        self._current_itxn_var_stack.append(
            self._current_loop_itxn_vars.copy() if self._current_loop_itxn_vars else []
        )
        try:
            yield
        finally:
            self._current_itxn_var_stack.pop()

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> None:
        with self._enter_loop():
            super().visit_for_in_loop(statement)

    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> None:
        with self._enter_loop():
            super().visit_while_loop(statement)

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        value = statement.value
        match value:
            case awst_nodes.CreateInnerTransaction() | awst_nodes.Copy():
                self._check_itxn_params_not_submitted_in_loop(statement.target)
        super().visit_assignment_statement(statement)

    def visit_submit_inner_transaction(self, call: awst_nodes.SubmitInnerTransaction) -> None:
        if self._current_loop_itxn_vars is not None:
            for itxn_params in call.itxns:
                match itxn_params:
                    case awst_nodes.TupleItemExpression(
                        base=awst_nodes.VarExpression(name=var_name)
                    ):
                        self._current_loop_itxn_vars.append(var_name)
                    case awst_nodes.VarExpression(name=var_name):
                        self._current_loop_itxn_vars.append(var_name)
        super().visit_submit_inner_transaction(call)

    def visit_update_inner_transaction(self, call: awst_nodes.UpdateInnerTransaction) -> None:
        super().visit_update_inner_transaction(call)
        self._check_itxn_params_not_submitted_in_loop(call.itxn)

    def _check_itxn_params_not_submitted_in_loop(self, expr: awst_nodes.Expression) -> None:
        if (
            self._current_loop_itxn_vars
            and isinstance(expr, awst_nodes.VarExpression)
            and expr.name in self._current_loop_itxn_vars
        ):
            logger.error(
                INNER_TRANSACTION_LOOP_MODIFICATION_ERROR,
                location=expr.source_location,
            )


def _check_method_types(stmt: awst_nodes.Function) -> None:
    for arg in stmt.args:
        if _is_either_itxn_wtype(arg.wtype):
            logger.error(
                INNER_TRANSACTION_SUBROUTINE_ERROR,
                location=arg.source_location,
            )
    if _is_either_itxn_wtype(stmt.return_type):
        logger.error(
            INNER_TRANSACTION_SUBROUTINE_ERROR,
            location=stmt.source_location,
        )


def _is_assignable_itxn_expr(expr: awst_nodes.Expression) -> bool:
    if not _is_itxn_wtype(expr.wtype):  # non itxn expressions are assignable
        return True
    match expr:
        case awst_nodes.VarExpression():  # local itxn expressions can be copied
            return True
        case awst_nodes.SubmitInnerTransaction():  # submit expressions are assignable
            return True
        case awst_nodes.TupleExpression(
            items=items
        ):  # tuple expressions composed of assignable expressions are assignable
            return all(map(_is_assignable_itxn_expr, items))
        case awst_nodes.TupleItemExpression(
            base=base
        ):  # tuple items are assignable if their base is assignable
            return _is_assignable_itxn_expr(base)
        case awst_nodes.FieldExpression(
            base=awst_nodes.Expression(wtype=wtypes.WTuple()) as base
        ):  # named tuple fields are assignable if their base is assignable
            return _is_assignable_itxn_expr(base)
        case awst_nodes.SingleEvaluation(source=source):
            return _is_assignable_itxn_expr(source)
        case awst_nodes.SliceExpression(
            base=base, wtype=wtypes.WTuple()
        ):  # tuple slices can be assigned if base can be
            return _is_assignable_itxn_expr(base)
    # anything else is not considered assignable
    expr_str = expr.accept(ToCodeVisitor())
    logger.debug(f"not assignable: {expr_str=}, {type(expr)=}")
    return False


def _is_either_itxn_wtype(wtype: wtypes.WType) -> bool:
    return _is_itxn_wtype(wtype) or _is_itxn_fields_wtype(wtype)


def _is_itxn_wtype(wtype: wtypes.WType) -> bool:
    return isinstance(wtype, WInnerTransaction) or (
        isinstance(wtype, wtypes.WTuple) and any(map(_is_itxn_wtype, wtype.types))
    )


def _is_itxn_fields_wtype(wtype: wtypes.WType) -> bool:
    return isinstance(wtype, WInnerTransactionFields) or (
        isinstance(wtype, wtypes.WTuple) and any(map(_is_itxn_fields_wtype, wtype.types))
    )


class StaleInnerTransactionsValidator(AWSTTraverser):
    """Validates that inner transaction array access are not stale"""

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    def __init__(self) -> None:
        super().__init__()
        self._maybe_stale_itxn_vars = dict[str, SourceLocation]()
        self._active_itxn_vars = list[str]()

    def visit_assignment_statement(self, stmt: awst_nodes.AssignmentStatement) -> None:
        super().visit_assignment_statement(stmt)
        match stmt.value:
            case awst_nodes.SubmitInnerTransaction():
                new_itxn_var_names = self._get_var_names(stmt.target)
                self._update_active_var_names(new_itxn_var_names)
            case awst_nodes.TupleExpression(items=items) if any(
                isinstance(item.wtype, WInnerTransaction) for item in items
            ):
                var_names = self._get_var_names(stmt.target)
                self._update_active_var_names(var_names)

    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> None:
        super().visit_intrinsic_call(call)
        if call.op_code == "itxn_submit":
            self._update_maybe_stale_itxn_vars(call.source_location)

    def visit_submit_inner_transaction(self, call: awst_nodes.SubmitInnerTransaction) -> None:
        super().visit_submit_inner_transaction(call)
        self._update_maybe_stale_itxn_vars(call.source_location)

    def visit_inner_transaction_field(self, itxn_field: awst_nodes.InnerTransactionField) -> None:
        super().visit_inner_transaction_field(itxn_field)
        match itxn_field.itxn:
            case awst_nodes.VarExpression(name=stale_var):
                pass
            case awst_nodes.TupleItemExpression(base=awst_nodes.VarExpression(name=stale_var)):
                pass
            case _:
                return
        if itxn_field.field.is_array:
            try:
                stale_var_loc = self._maybe_stale_itxn_vars[stale_var]
            except KeyError:
                return
            logger.error(
                INNER_TRANSACTION_MAYBE_STALE_ERROR.format(stale_var=stale_var),
                location=itxn_field.itxn.source_location,
            )
            logger.warning(
                INNER_TRANSACTION_MAYBE_STALE_WARNING.format(stale_var=stale_var),
                location=stale_var_loc,
            )

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        self._update_maybe_stale_itxn_vars(expr.source_location)

    def _get_var_names(self, expr: awst_nodes.Expression) -> list[str]:
        match expr:
            case awst_nodes.VarExpression(name=name):
                return [name]
            case awst_nodes.TupleExpression(items=items):
                return [self._get_var_names(item)[0] for item in items]
            case _:
                return []

    def _update_active_var_names(self, var_names: list[str]) -> None:
        self._active_itxn_vars = var_names
        # if a var_name is reassigned then it is not considered stale
        for var_name in self._active_itxn_vars:
            with contextlib.suppress(KeyError):
                del self._maybe_stale_itxn_vars[var_name]

    def _update_maybe_stale_itxn_vars(self, staling_expr_loc: SourceLocation) -> None:
        for stale_var_name in self._active_itxn_vars:
            self._maybe_stale_itxn_vars[stale_var_name] = staling_expr_loc
        self._active_itxn_vars = []
