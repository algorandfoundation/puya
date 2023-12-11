import puya.awst.visitors
from puya.awst import nodes as awst_nodes


class FunctionTraverser(
    puya.awst.visitors.ExpressionVisitor[None],
    puya.awst.visitors.StatementVisitor[None],
):
    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        expr.target.accept(self)
        expr.value.accept(self)

    def visit_uint64_binary_operation(self, expr: awst_nodes.UInt64BinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_biguint_binary_operation(self, expr: awst_nodes.BigUIntBinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_integer_constant(self, expr: awst_nodes.IntegerConstant) -> None:
        pass

    def visit_decimal_constant(self, expr: awst_nodes.DecimalConstant) -> None:
        pass

    def visit_bool_constant(self, expr: awst_nodes.BoolConstant) -> None:
        pass

    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> None:
        pass

    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> None:
        expr.value.accept(self)

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> None:
        expr.value.accept(self)

    def visit_arc4_array_encode(self, expr: awst_nodes.ARC4ArrayEncode) -> None:
        for value in expr.values:
            value.accept(self)

    def visit_method_constant(self, expr: awst_nodes.MethodConstant) -> None:
        pass

    def visit_address_constant(self, expr: awst_nodes.AddressConstant) -> None:
        pass

    def visit_numeric_comparison_expression(
        self, expr: awst_nodes.NumericComparisonExpression
    ) -> None:
        expr.lhs.accept(self)
        expr.rhs.accept(self)

    def visit_var_expression(self, expr: awst_nodes.VarExpression) -> None:
        pass

    def visit_checked_maybe(self, expr: awst_nodes.CheckedMaybe) -> None:
        expr.expr.accept(self)

    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> None:
        for arg in call.stack_args:
            arg.accept(self)

    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> None:
        for item in expr.items:
            item.accept(self)

    def visit_tuple_item_expression(self, expr: awst_nodes.TupleItemExpression) -> None:
        expr.base.accept(self)

    def visit_field_expression(self, expr: awst_nodes.FieldExpression) -> None:
        expr.base.accept(self)

    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> None:
        expr.base.accept(self)
        if isinstance(expr.begin_index, awst_nodes.Expression):
            expr.begin_index.accept(self)
        if isinstance(expr.end_index, awst_nodes.Expression):
            expr.end_index.accept(self)

    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> None:
        expr.base.accept(self)
        expr.index.accept(self)

    def visit_conditional_expression(self, expr: awst_nodes.ConditionalExpression) -> None:
        expr.condition.accept(self)
        expr.true_expr.accept(self)
        expr.false_expr.accept(self)

    def visit_temporary_variable(self, expr: awst_nodes.TemporaryVariable) -> None:
        pass

    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> None:
        pass

    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> None:
        expr.account.accept(self)

    def visit_new_array(self, expr: awst_nodes.NewArray) -> None:
        for element in expr.elements:
            element.accept(self)

    def visit_bytes_comparison_expression(
        self, expr: awst_nodes.BytesComparisonExpression
    ) -> None:
        expr.lhs.accept(self)
        expr.rhs.accept(self)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        for arg in expr.args:
            arg.value.accept(self)

    def visit_bytes_binary_operation(self, expr: awst_nodes.BytesBinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_boolean_binary_operation(self, expr: awst_nodes.BooleanBinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_uint64_unary_operation(self, expr: awst_nodes.UInt64UnaryOperation) -> None:
        expr.expr.accept(self)

    def visit_bytes_unary_operation(self, expr: awst_nodes.BytesUnaryOperation) -> None:
        expr.expr.accept(self)

    def visit_not_expression(self, expr: awst_nodes.Not) -> None:
        expr.expr.accept(self)

    def visit_contains_expression(self, expr: awst_nodes.Contains) -> None:
        expr.item.accept(self)
        expr.sequence.accept(self)

    def visit_block(self, statement: awst_nodes.Block) -> None:
        for stmt in statement.body:
            stmt.accept(self)

    def visit_if_else(self, statement: awst_nodes.IfElse) -> None:
        statement.condition.accept(self)
        statement.if_branch.accept(self)
        if statement.else_branch:
            statement.else_branch.accept(self)

    def visit_switch(self, statement: awst_nodes.Switch) -> None:
        statement.value.accept(self)
        for case, block in statement.cases.items():
            case.accept(self)
            block.accept(self)
        if statement.default_case:
            statement.default_case.accept(self)

    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> None:
        statement.condition.accept(self)
        statement.loop_body.accept(self)

    def visit_break_statement(self, statement: awst_nodes.BreakStatement) -> None:
        pass

    def visit_return_statement(self, statement: awst_nodes.ReturnStatement) -> None:
        if statement.value is not None:
            statement.value.accept(self)

    def visit_continue_statement(self, statement: awst_nodes.ContinueStatement) -> None:
        pass

    def visit_expression_statement(self, statement: awst_nodes.ExpressionStatement) -> None:
        statement.expr.accept(self)

    def visit_assert_statement(self, statement: awst_nodes.AssertStatement) -> None:
        statement.condition.accept(self)

    def visit_uint64_augmented_assignment(
        self, statement: awst_nodes.UInt64AugmentedAssignment
    ) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    def visit_biguint_augmented_assignment(
        self, statement: awst_nodes.BigUIntAugmentedAssignment
    ) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    def visit_bytes_augmented_assignment(
        self, statement: awst_nodes.BytesAugmentedAssignment
    ) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> None:
        if isinstance(statement.sequence, awst_nodes.Range):
            range_ = statement.sequence
            range_.start.accept(self)
            range_.stop.accept(self)
            range_.step.accept(self)
        else:
            statement.sequence.accept(self)
        statement.items.accept(self)
        statement.loop_body.accept(self)

    def visit_reinterpret_cast(self, expr: awst_nodes.ReinterpretCast) -> None:
        expr.expr.accept(self)

    def visit_enumeration(self, expr: awst_nodes.Enumeration) -> None:
        if isinstance(expr.expr, awst_nodes.Range):
            range_ = expr.expr
            range_.start.accept(self)
            range_.stop.accept(self)
            range_.step.accept(self)
        else:
            expr.expr.accept(self)
