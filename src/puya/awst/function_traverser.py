import typing

import puya.awst.visitors
from puya.awst import nodes as awst_nodes


class FunctionTraverser(
    puya.awst.visitors.ExpressionVisitor[None],
    puya.awst.visitors.StatementVisitor[None],
):
    @typing.override
    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    @typing.override
    def visit_copy(self, expr: awst_nodes.Copy) -> None:
        expr.value.accept(self)

    @typing.override
    def visit_goto(self, statement: awst_nodes.Goto) -> None:
        pass

    @typing.override
    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        expr.target.accept(self)
        expr.value.accept(self)

    @typing.override
    def visit_uint64_binary_operation(self, expr: awst_nodes.UInt64BinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    @typing.override
    def visit_biguint_binary_operation(self, expr: awst_nodes.BigUIntBinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    @typing.override
    def visit_reversed(self, expr: awst_nodes.Reversed) -> None:
        if isinstance(expr.expr, awst_nodes.Expression):
            expr.expr.accept(self)

    @typing.override
    def visit_integer_constant(self, expr: awst_nodes.IntegerConstant) -> None:
        pass

    @typing.override
    def visit_decimal_constant(self, expr: awst_nodes.DecimalConstant) -> None:
        pass

    @typing.override
    def visit_bool_constant(self, expr: awst_nodes.BoolConstant) -> None:
        pass

    @typing.override
    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> None:
        pass

    @typing.override
    def visit_string_constant(self, expr: awst_nodes.StringConstant) -> None:
        pass

    @typing.override
    def visit_void_constant(self, expr: awst_nodes.VoidConstant) -> None:
        pass

    @typing.override
    def visit_compiled_contract(self, expr: awst_nodes.CompiledContract) -> None:
        for value in expr.template_variables.values():
            value.accept(self)

    @typing.override
    def visit_compiled_logicsig(self, expr: awst_nodes.CompiledLogicSig) -> None:
        for value in expr.template_variables.values():
            value.accept(self)

    @typing.override
    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> None:
        expr.value.accept(self)

    @typing.override
    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> None:
        expr.value.accept(self)

    @typing.override
    def visit_array_concat(self, expr: awst_nodes.ArrayConcat) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    @typing.override
    def visit_array_pop(self, expr: awst_nodes.ArrayPop) -> None:
        expr.base.accept(self)

    @typing.override
    def visit_array_extend(self, expr: awst_nodes.ArrayExtend) -> None:
        expr.base.accept(self)
        expr.other.accept(self)

    @typing.override
    def visit_array_length(self, expr: awst_nodes.ArrayLength) -> None:
        expr.array.accept(self)

    @typing.override
    def visit_array_replace(self, expr: awst_nodes.ArrayReplace) -> None:
        expr.base.accept(self)
        expr.index.accept(self)
        expr.value.accept(self)

    @typing.override
    def visit_method_constant(self, expr: awst_nodes.MethodConstant) -> None:
        pass

    @typing.override
    def visit_address_constant(self, expr: awst_nodes.AddressConstant) -> None:
        pass

    @typing.override
    def visit_numeric_comparison_expression(
        self, expr: awst_nodes.NumericComparisonExpression
    ) -> None:
        expr.lhs.accept(self)
        expr.rhs.accept(self)

    @typing.override
    def visit_var_expression(self, expr: awst_nodes.VarExpression) -> None:
        pass

    @typing.override
    def visit_assert_expression(self, expr: awst_nodes.AssertExpression) -> None:
        if expr.condition is not None:
            expr.condition.accept(self)

    @typing.override
    def visit_checked_maybe(self, expr: awst_nodes.CheckedMaybe) -> None:
        expr.expr.accept(self)

    @typing.override
    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> None:
        for arg in call.stack_args:
            arg.accept(self)

    @typing.override
    def visit_size_of(self, call: awst_nodes.SizeOf) -> None:
        pass

    @typing.override
    def visit_puya_lib_call(self, call: awst_nodes.PuyaLibCall) -> None:
        for arg in call.args:
            arg.value.accept(self)

    @typing.override
    def visit_group_transaction_reference(self, ref: awst_nodes.GroupTransactionReference) -> None:
        ref.index.accept(self)

    @typing.override
    def visit_create_inner_transaction(self, call: awst_nodes.CreateInnerTransaction) -> None:
        for expr in call.fields.values():
            expr.accept(self)

    @typing.override
    def visit_update_inner_transaction(self, call: awst_nodes.UpdateInnerTransaction) -> None:
        call.itxn.accept(self)
        for value in call.fields.values():
            value.accept(self)

    @typing.override
    def visit_set_inner_transaction_fields(
        self, node: awst_nodes.SetInnerTransactionFields
    ) -> None:
        for expr in node.itxns:
            expr.accept(self)

    @typing.override
    def visit_submit_inner_transaction(self, call: awst_nodes.SubmitInnerTransaction) -> None:
        for expr in call.itxns:
            expr.accept(self)

    @typing.override
    def visit_inner_transaction_field(self, itxn_field: awst_nodes.InnerTransactionField) -> None:
        itxn_field.itxn.accept(self)
        if itxn_field.array_index:
            itxn_field.array_index.accept(self)

    @typing.override
    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> None:
        for item in expr.items:
            item.accept(self)

    @typing.override
    def visit_tuple_item_expression(self, expr: awst_nodes.TupleItemExpression) -> None:
        expr.base.accept(self)

    @typing.override
    def visit_field_expression(self, expr: awst_nodes.FieldExpression) -> None:
        expr.base.accept(self)

    @typing.override
    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> None:
        expr.base.accept(self)
        if isinstance(expr.begin_index, awst_nodes.Expression):
            expr.begin_index.accept(self)
        if isinstance(expr.end_index, awst_nodes.Expression):
            expr.end_index.accept(self)

    @typing.override
    def visit_intersection_slice_expression(
        self, expr: awst_nodes.IntersectionSliceExpression
    ) -> None:
        expr.base.accept(self)
        if isinstance(expr.begin_index, awst_nodes.Expression):
            expr.begin_index.accept(self)
        if isinstance(expr.end_index, awst_nodes.Expression):
            expr.end_index.accept(self)

    @typing.override
    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> None:
        expr.base.accept(self)
        expr.index.accept(self)

    @typing.override
    def visit_conditional_expression(self, expr: awst_nodes.ConditionalExpression) -> None:
        expr.condition.accept(self)
        expr.true_expr.accept(self)
        expr.false_expr.accept(self)

    @typing.override
    def visit_single_evaluation(self, expr: awst_nodes.SingleEvaluation) -> None:
        expr.source.accept(self)

    @typing.override
    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> None:
        expr.key.accept(self)

    @typing.override
    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> None:
        expr.key.accept(self)
        expr.account.accept(self)

    @typing.override
    def visit_new_array(self, expr: awst_nodes.NewArray) -> None:
        for element in expr.values:
            element.accept(self)

    @typing.override
    def visit_new_struct(self, expr: awst_nodes.NewStruct) -> None:
        for element in expr.values.values():
            element.accept(self)

    @typing.override
    def visit_bytes_comparison_expression(
        self, expr: awst_nodes.BytesComparisonExpression
    ) -> None:
        expr.lhs.accept(self)
        expr.rhs.accept(self)

    @typing.override
    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        for arg in expr.args:
            arg.value.accept(self)

    @typing.override
    def visit_bytes_binary_operation(self, expr: awst_nodes.BytesBinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    @typing.override
    def visit_boolean_binary_operation(self, expr: awst_nodes.BooleanBinaryOperation) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    @typing.override
    def visit_uint64_unary_operation(self, expr: awst_nodes.UInt64UnaryOperation) -> None:
        expr.expr.accept(self)

    @typing.override
    def visit_bytes_unary_operation(self, expr: awst_nodes.BytesUnaryOperation) -> None:
        expr.expr.accept(self)

    @typing.override
    def visit_not_expression(self, expr: awst_nodes.Not) -> None:
        expr.expr.accept(self)

    @typing.override
    def visit_block(self, statement: awst_nodes.Block) -> None:
        for stmt in statement.body:
            stmt.accept(self)

    @typing.override
    def visit_if_else(self, statement: awst_nodes.IfElse) -> None:
        statement.condition.accept(self)
        statement.if_branch.accept(self)
        if statement.else_branch:
            statement.else_branch.accept(self)

    @typing.override
    def visit_switch(self, statement: awst_nodes.Switch) -> None:
        statement.value.accept(self)
        for case, block in statement.cases.items():
            case.accept(self)
            block.accept(self)
        if statement.default_case:
            statement.default_case.accept(self)

    @typing.override
    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> None:
        statement.condition.accept(self)
        statement.loop_body.accept(self)

    @typing.override
    def visit_loop_exit(self, statement: awst_nodes.LoopExit) -> None:
        pass

    @typing.override
    def visit_return_statement(self, statement: awst_nodes.ReturnStatement) -> None:
        if statement.value is not None:
            statement.value.accept(self)

    @typing.override
    def visit_loop_continue(self, statement: awst_nodes.LoopContinue) -> None:
        pass

    @typing.override
    def visit_expression_statement(self, statement: awst_nodes.ExpressionStatement) -> None:
        statement.expr.accept(self)

    @typing.override
    def visit_template_var(self, statement: awst_nodes.TemplateVar) -> None:
        pass

    @typing.override
    def visit_uint64_augmented_assignment(
        self, statement: awst_nodes.UInt64AugmentedAssignment
    ) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    @typing.override
    def visit_biguint_augmented_assignment(
        self, statement: awst_nodes.BigUIntAugmentedAssignment
    ) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    @typing.override
    def visit_bytes_augmented_assignment(
        self, statement: awst_nodes.BytesAugmentedAssignment
    ) -> None:
        statement.target.accept(self)
        statement.value.accept(self)

    @typing.override
    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> None:
        statement.sequence.accept(self)
        statement.items.accept(self)
        statement.loop_body.accept(self)

    @typing.override
    def visit_reinterpret_cast(self, expr: awst_nodes.ReinterpretCast) -> None:
        expr.expr.accept(self)

    @typing.override
    def visit_enumeration(self, expr: awst_nodes.Enumeration) -> None:
        expr.expr.accept(self)

    @typing.override
    def visit_state_get_ex(self, expr: awst_nodes.StateGetEx) -> None:
        expr.field.accept(self)

    @typing.override
    def visit_state_delete(self, statement: awst_nodes.StateDelete) -> None:
        statement.field.accept(self)

    @typing.override
    def visit_state_get(self, expr: awst_nodes.StateGet) -> None:
        expr.field.accept(self)
        expr.default.accept(self)

    @typing.override
    def visit_state_exists(self, expr: awst_nodes.StateExists) -> None:
        expr.field.accept(self)

    @typing.override
    def visit_box_prefixed_key_expression(self, expr: awst_nodes.BoxPrefixedKeyExpression) -> None:
        expr.prefix.accept(self)
        expr.key.accept(self)

    @typing.override
    def visit_box_value_expression(self, expr: awst_nodes.BoxValueExpression) -> None:
        expr.key.accept(self)

    @typing.override
    def visit_biguint_postfix_unary_operation(
        self, expr: awst_nodes.BigUIntPostfixUnaryOperation
    ) -> None:
        expr.target.accept(self)

    @typing.override
    def visit_uint64_postfix_unary_operation(
        self, expr: awst_nodes.UInt64PostfixUnaryOperation
    ) -> None:
        expr.target.accept(self)

    @typing.override
    def visit_arc4_router(self, expr: awst_nodes.ARC4Router) -> None:
        pass

    @typing.override
    def visit_range(self, node: awst_nodes.Range) -> None:
        node.start.accept(self)
        node.stop.accept(self)
        node.step.accept(self)

    @typing.override
    def visit_emit(self, expr: awst_nodes.Emit) -> None:
        expr.value.accept(self)

    @typing.override
    def visit_comma_expression(self, expr: awst_nodes.CommaExpression) -> None:
        for inner in expr.expressions:
            inner.accept(self)
