import contextlib
from collections.abc import Iterator, Sequence

import attrs

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst_build.validation.awst_traverser import AWSTTraverser
from puya.context import CompileContext
from puya.parse import SourceLocation


@attrs.define
class InnerTransactionsValidator(AWSTTraverser):
    """Validates that inner transaction parameters and results are only used in the ways currently
    supported. Emits errors for:

    Reassigning inner transaction params without a copy()
    Reassigning inner transactions
    Modifying inner transactions after submission while in a loop
    Using inner transactions and parameters in a subroutine
    Not unpacking the tuple of a submit result
    """

    context: CompileContext
    _current_itxn_var_stack: list[list[str]] = attrs.field(factory=list)

    @property
    def _current_loop_itxn_vars(self) -> list[str] | None:
        return self._current_itxn_var_stack[-1] if self._current_itxn_var_stack else None

    @classmethod
    def validate(cls, context: CompileContext, module_asts: dict[str, awst_nodes.Module]) -> None:
        for module in module_asts.values():
            for module_statement in module.body:
                validator = cls(context)
                module_statement.accept(validator)

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
            ) if wtypes.is_inner_transaction_params_type(wtype):
                self.context.errors.error(
                    f"{value.wtype} must be copied using .copy() when "
                    f"assigning to a new local: {var_name}",
                    value.source_location,
                )
            case awst_nodes.Expression(wtype=wtype) if wtypes.is_inner_transaction_params_type(
                wtype
            ):
                self.context.errors.error(
                    f"{value.wtype} cannot be aliased",
                    value.source_location,
                )

    def _check_itxn_params_not_submitted_in_loop(self, expr: awst_nodes.Expression) -> None:
        if (
            self._current_loop_itxn_vars
            and isinstance(expr, awst_nodes.VarExpression)
            and expr.name in self._current_loop_itxn_vars
        ):
            self.context.errors.error(
                f"'{expr.name}' cannot be modified after submission while in a loop ",
                expr.source_location,
            )

    def _check_inner_transaction_assignment(self, stmt: awst_nodes.AssignmentStatement) -> None:
        match stmt.value:
            case awst_nodes.SubmitInnerTransaction() as submit:
                match stmt.target:
                    case awst_nodes.VarExpression() if len(submit.itxns) > 1:
                        pass
                    case awst_nodes.TupleExpression(items=items) if len(items) != len(
                        submit.itxns
                    ):
                        pass
                    case _:
                        return
                self.context.errors.error(
                    f"Inner Transactions cannot be part of an unpacked tuple: {stmt.value.wtype}",
                    stmt.value.source_location,
                )
            case awst_nodes.Expression(wtype=wtype) if wtypes.is_inner_transaction_type(wtype):
                self.context.errors.error(
                    f"{stmt.value.wtype} cannot be aliased",
                    stmt.value.source_location,
                )

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        if _is_itxn_wtype(expr.wtype):
            self.context.errors.error(
                f"{expr.wtype} cannot be used in assignment expressions",
                expr.source_location,
            )

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            arg_wtype = arg.value.wtype
            if _is_itxn_wtype(arg_wtype) or wtypes.is_inner_transaction_tuple_type(arg_wtype):
                self.context.errors.error(
                    f"{arg.value.wtype} cannot be passed to a subroutine",
                    expr.source_location,
                )

    def _check_method_types(
        self,
        args: Sequence[awst_nodes.SubroutineArgument],
        return_type: wtypes.WType,
        return_loc: SourceLocation,
    ) -> None:
        for arg in args:
            if _is_itxn_wtype(arg.wtype):
                self.context.errors.error(
                    f"{arg.wtype} cannot be used as a subroutine argument type: {arg.name}",
                    location=arg.source_location,
                )
        if _is_itxn_wtype(return_type):
            self.context.errors.error(
                f"{return_type} cannot be used as a subroutine return type",
                location=return_loc,
            )


def _is_itxn_wtype(wtype: wtypes.WType) -> bool:
    return wtypes.is_inner_transaction_params_type(wtype) or wtypes.is_inner_transaction_type(
        wtype
    )
