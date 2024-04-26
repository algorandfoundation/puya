import contextlib
from collections.abc import Iterator, Sequence

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst_build.validation.awst_traverser import AWSTTraverser
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class InnerTransactionsValidator(AWSTTraverser):
    """Validates that inner transaction parameters and results are only used in the ways currently
    supported. Emits errors for:

    Reassigning inner transaction params without a copy()
    Reassigning inner transactions
    Modifying inner transactions after submission while in a loop
    Using inner transactions and parameters in a subroutine
    Not unpacking the tuple of a submit result
    """

    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        for module_statement in module.body:
            validator = cls()
            module_statement.accept(validator)

    def __init__(self) -> None:
        super().__init__()
        self._current_itxn_var_stack = list[list[str]]()

    @property
    def _current_loop_itxn_vars(self) -> list[str] | None:
        return self._current_itxn_var_stack[-1] if self._current_itxn_var_stack else None

    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        self._check_method_types(statement.args, statement.return_type, statement.source_location)
        super().visit_contract_method(statement)

    def visit_subroutine(self, statement: awst_nodes.Subroutine) -> None:
        self._check_method_types(statement.args, statement.return_type, statement.source_location)
        super().visit_subroutine(statement)

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        self._check_inner_transaction_params_assignment(statement)
        self._check_inner_transaction_assignment(statement)
        super().visit_assignment_statement(statement)

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> None:
        with self._enter_loop():
            super().visit_for_in_loop(statement)

    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> None:
        with self._enter_loop():
            super().visit_while_loop(statement)

    def visit_submit_inner_transaction(self, call: awst_nodes.SubmitInnerTransaction) -> None:
        if self._current_loop_itxn_vars is not None:
            for itxn_params in call.itxns:
                match itxn_params:
                    case awst_nodes.VarExpression(name=var_name):
                        self._current_loop_itxn_vars.append(var_name)
        super().visit_submit_inner_transaction(call)

    def visit_update_inner_transaction(self, call: awst_nodes.UpdateInnerTransaction) -> None:
        super().visit_update_inner_transaction(call)
        self._check_itxn_params_not_submitted_in_loop(call.itxn)

    @contextlib.contextmanager
    def _enter_loop(self) -> Iterator[None]:
        try:
            self._current_itxn_var_stack.append(
                self._current_loop_itxn_vars.copy() if self._current_loop_itxn_vars else []
            )
            yield
        finally:
            self._current_itxn_var_stack.pop()

    def _check_inner_transaction_params_assignment(
        self, stmt: awst_nodes.AssignmentStatement
    ) -> None:
        value = stmt.value
        match value:
            case awst_nodes.CreateInnerTransaction() | awst_nodes.Copy():
                self._check_itxn_params_not_submitted_in_loop(stmt.target)
            case awst_nodes.VarExpression(
                name=var_name, wtype=wtype
            ) if wtypes.is_inner_transaction_field_type(wtype):
                logger.error(
                    f"{value.wtype} must be copied using .copy() when "
                    f"assigning to a new local: {var_name}",
                    location=value.source_location,
                )
            case awst_nodes.Expression(wtype=wtype) if wtypes.is_inner_transaction_field_type(
                wtype
            ):
                logger.error(
                    f"{value.wtype} cannot be aliased",
                    location=value.source_location,
                )

    def _check_itxn_params_not_submitted_in_loop(self, expr: awst_nodes.Expression) -> None:
        if (
            self._current_loop_itxn_vars
            and isinstance(expr, awst_nodes.VarExpression)
            and expr.name in self._current_loop_itxn_vars
        ):
            logger.error(
                f"'{expr.name}' cannot be modified after submission while in a loop ",
                location=expr.source_location,
            )

    def _check_inner_transaction_assignment(self, stmt: awst_nodes.AssignmentStatement) -> None:
        match stmt.value:
            case awst_nodes.SubmitInnerTransaction():
                return
            case awst_nodes.TupleExpression(items=items) if (
                len([item for item in items if wtypes.is_inner_transaction_type(item.wtype)]) == 1
            ):
                return
            case awst_nodes.Expression(wtype=wtype) if not wtypes.is_inner_transaction_type(wtype):
                return
        logger.error(
            f"{stmt.value.wtype} cannot be reassigned",
            location=stmt.value.source_location,
        )

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        if _is_itxn_wtype(expr.wtype):
            logger.error(
                f"{expr.wtype} cannot be used in assignment expressions",
                location=expr.source_location,
            )

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            arg_wtype = arg.value.wtype
            if _is_itxn_wtype(arg_wtype) or wtypes.is_inner_transaction_tuple_type(arg_wtype):
                logger.error(
                    f"{arg.value.wtype} cannot be passed to a subroutine",
                    location=expr.source_location,
                )

    def _check_method_types(
        self,
        args: Sequence[awst_nodes.SubroutineArgument],
        return_type: wtypes.WType,
        return_loc: SourceLocation,
    ) -> None:
        for arg in args:
            if _is_itxn_wtype(arg.wtype):
                logger.error(
                    f"{arg.wtype} cannot be used as a subroutine argument type: {arg.name}",
                    location=arg.source_location,
                )
        if _is_itxn_wtype(return_type):
            logger.error(
                f"{return_type} cannot be used as a subroutine return type",
                location=return_loc,
            )


class InnerTransactionFieldsValidator(AWSTTraverser):
    """
    Validates that inner transaction fields are only used in the ways currently
    supported. Emits errors for:

    Reassigning inner transaction fields without a copy()
    Modifying inner transaction fields after submission while in a loop
    Using inner transactions fields in a subroutine
    """

    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        for module_statement in module.body:
            validator = cls()
            module_statement.accept(validator)

    def __init__(self) -> None:
        super().__init__()
        self._current_itxn_var_stack = list[list[str]]()

    @property
    def _current_loop_itxn_vars(self) -> list[str] | None:
        return self._current_itxn_var_stack[-1] if self._current_itxn_var_stack else None

    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        self._check_method_types(statement.args, statement.return_type, statement.source_location)
        super().visit_contract_method(statement)

    def visit_subroutine(self, statement: awst_nodes.Subroutine) -> None:
        self._check_method_types(statement.args, statement.return_type, statement.source_location)
        super().visit_subroutine(statement)

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        self._check_inner_transaction_params_assignment(statement)
        super().visit_assignment_statement(statement)

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> None:
        with self._enter_loop():
            super().visit_for_in_loop(statement)

    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> None:
        with self._enter_loop():
            super().visit_while_loop(statement)

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

    @contextlib.contextmanager
    def _enter_loop(self) -> Iterator[None]:
        try:
            self._current_itxn_var_stack.append(
                self._current_loop_itxn_vars.copy() if self._current_loop_itxn_vars else []
            )
            yield
        finally:
            self._current_itxn_var_stack.pop()

    def _check_inner_transaction_params_assignment(
        self, stmt: awst_nodes.AssignmentStatement
    ) -> None:
        value = stmt.value
        match value:
            case awst_nodes.CreateInnerTransaction() | awst_nodes.Copy():
                self._check_itxn_params_not_submitted_in_loop(stmt.target)
            case awst_nodes.VarExpression(wtype=wtype) | awst_nodes.TupleItemExpression(
                wtype=wtype
            ) if wtypes.is_inner_transaction_field_type(wtype):
                logger.error(
                    f"{value.wtype} must be copied using .copy() when "
                    f"assigning to a new local",
                    location=value.source_location,
                )
            case awst_nodes.Expression(wtype=wtype) if (
                wtypes.is_inner_transaction_field_type(wtype)
            ):
                logger.error(
                    f"{value.wtype} can only be assigned to local variables",
                    location=value.source_location,
                )

    def _check_itxn_params_not_submitted_in_loop(self, expr: awst_nodes.Expression) -> None:
        if (
            self._current_loop_itxn_vars
            and isinstance(expr, awst_nodes.VarExpression)
            and expr.name in self._current_loop_itxn_vars
        ):
            logger.error(
                f"'{expr.name}' cannot be modified after submission while in a loop ",
                location=expr.source_location,
            )

    def _check_inner_transaction_assignment(self, stmt: awst_nodes.AssignmentStatement) -> None:
        match stmt.value:
            case awst_nodes.SubmitInnerTransaction():
                return
            case awst_nodes.TupleExpression(items=items) if (
                len([item for item in items if wtypes.is_inner_transaction_type(item.wtype)]) == 1
            ):
                return
            case awst_nodes.Expression(wtype=wtype) if not wtypes.is_inner_transaction_type(wtype):
                return
        logger.error(
            f"{stmt.value.wtype} cannot be reassigned",
            location=stmt.value.source_location,
        )

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        if _is_itxn_wtype(expr.wtype):
            logger.error(
                f"{expr.wtype} cannot be used in assignment expressions",
                location=expr.source_location,
            )

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            arg_wtype = arg.value.wtype
            if _is_itxn_wtype(arg_wtype) or wtypes.is_inner_transaction_tuple_type(arg_wtype):
                logger.error(
                    f"{arg.value.wtype} cannot be passed to a subroutine",
                    location=expr.source_location,
                )

    def _check_method_types(
        self,
        args: Sequence[awst_nodes.SubroutineArgument],
        return_type: wtypes.WType,
        return_loc: SourceLocation,
    ) -> None:
        for arg in args:
            if _is_itxn_wtype(arg.wtype):
                logger.error(
                    f"{arg.wtype} cannot be used as a subroutine argument type: {arg.name}",
                    location=arg.source_location,
                )
        if _is_itxn_wtype(return_type):
            logger.error(
                f"{return_type} cannot be used as a subroutine return type",
                location=return_loc,
            )


def _is_itxn_wtype(wtype: wtypes.WType) -> bool:
    return wtypes.is_inner_transaction_field_type(wtype) or wtypes.is_inner_transaction_type(wtype)


class StaleInnerTransactionsValidator(AWSTTraverser):
    """Validates that inner transaction array access are not stale"""

    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        for module_statement in module.body:
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
                wtypes.is_inner_transaction_type(item.wtype) for item in items
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
            case awst_nodes.VarExpression(name=var_name):
                pass
            case awst_nodes.TupleItemExpression(base=awst_nodes.VarExpression(name=var_name)):
                pass
            case _:
                return
        if itxn_field.field.is_array and var_name in self._maybe_stale_itxn_vars:
            logger.error(
                f"Inner Transaction referred to by {var_name!r} may no longer be valid due"
                " to other inner transaction submissions, or subroutine calls."
                " This means array field access may not give expected results,"
                f" move array field access after {var_name!r} definition and before expression"
                f" indicated.",
                location=itxn_field.itxn.source_location,
            )
            var_name_loc = self._maybe_stale_itxn_vars[var_name]
            logger.warning(f"{var_name!r} becomes potentially stale here", location=var_name_loc)

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
