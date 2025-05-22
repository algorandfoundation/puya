from __future__ import annotations  # needed to break import cycle

import typing as t
from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    import puya.awst.nodes
    import puya.awst.wtypes


class StatementVisitor[T](ABC):
    @abstractmethod
    def visit_block(self, statement: puya.awst.nodes.Block) -> T: ...

    @abstractmethod
    def visit_if_else(self, statement: puya.awst.nodes.IfElse) -> T: ...

    @abstractmethod
    def visit_switch(self, statement: puya.awst.nodes.Switch) -> T: ...

    @abstractmethod
    def visit_while_loop(self, statement: puya.awst.nodes.WhileLoop) -> T: ...

    @abstractmethod
    def visit_loop_exit(self, statement: puya.awst.nodes.LoopExit) -> T: ...

    @abstractmethod
    def visit_return_statement(self, statement: puya.awst.nodes.ReturnStatement) -> T: ...

    @abstractmethod
    def visit_loop_continue(self, statement: puya.awst.nodes.LoopContinue) -> T: ...

    @abstractmethod
    def visit_expression_statement(self, statement: puya.awst.nodes.ExpressionStatement) -> T: ...

    @abstractmethod
    def visit_uint64_augmented_assignment(
        self, statement: puya.awst.nodes.UInt64AugmentedAssignment
    ) -> T: ...

    @abstractmethod
    def visit_biguint_augmented_assignment(
        self, statement: puya.awst.nodes.BigUIntAugmentedAssignment
    ) -> T: ...

    @abstractmethod
    def visit_bytes_augmented_assignment(
        self, statement: puya.awst.nodes.BytesAugmentedAssignment
    ) -> T: ...

    @abstractmethod
    def visit_for_in_loop(self, statement: puya.awst.nodes.ForInLoop) -> T: ...

    @abstractmethod
    def visit_assignment_statement(self, statement: puya.awst.nodes.AssignmentStatement) -> T: ...

    @abstractmethod
    def visit_goto(self, statement: puya.awst.nodes.Goto) -> T: ...


class RootNodeVisitor[T](ABC):
    @abstractmethod
    def visit_subroutine(self, statement: puya.awst.nodes.Subroutine) -> T: ...

    @abstractmethod
    def visit_contract(self, statement: puya.awst.nodes.Contract) -> T: ...

    @abstractmethod
    def visit_logic_signature(self, statement: puya.awst.nodes.LogicSignature) -> T: ...


class ContractMemberVisitor[T](ABC):
    @abstractmethod
    def visit_contract_method(self, statement: puya.awst.nodes.ContractMethod) -> T: ...

    @abstractmethod
    def visit_app_storage_definition(
        self, statement: puya.awst.nodes.AppStorageDefinition
    ) -> T: ...


class ExpressionVisitor[T](ABC):
    @abstractmethod
    def visit_state_delete(self, expr: puya.awst.nodes.StateDelete) -> T: ...

    @abstractmethod
    def visit_assignment_expression(self, expr: puya.awst.nodes.AssignmentExpression) -> T: ...

    @abstractmethod
    def visit_uint64_binary_operation(self, expr: puya.awst.nodes.UInt64BinaryOperation) -> T: ...

    @abstractmethod
    def visit_biguint_binary_operation(
        self, expr: puya.awst.nodes.BigUIntBinaryOperation
    ) -> T: ...

    @abstractmethod
    def visit_integer_constant(self, expr: puya.awst.nodes.IntegerConstant) -> T: ...

    @abstractmethod
    def visit_decimal_constant(self, expr: puya.awst.nodes.DecimalConstant) -> T: ...

    @abstractmethod
    def visit_bool_constant(self, expr: puya.awst.nodes.BoolConstant) -> T: ...

    @abstractmethod
    def visit_bytes_constant(self, expr: puya.awst.nodes.BytesConstant) -> T: ...

    @abstractmethod
    def visit_string_constant(self, expr: puya.awst.nodes.StringConstant) -> T: ...

    @abstractmethod
    def visit_void_constant(self, expr: puya.awst.nodes.VoidConstant) -> T: ...

    @abstractmethod
    def visit_address_constant(self, expr: puya.awst.nodes.AddressConstant) -> T: ...

    @abstractmethod
    def visit_compiled_contract(self, expr: puya.awst.nodes.CompiledContract) -> T: ...

    @abstractmethod
    def visit_compiled_logicsig(self, expr: puya.awst.nodes.CompiledLogicSig) -> T: ...

    @abstractmethod
    def visit_numeric_comparison_expression(
        self, expr: puya.awst.nodes.NumericComparisonExpression
    ) -> T: ...

    @abstractmethod
    def visit_var_expression(self, expr: puya.awst.nodes.VarExpression) -> T: ...

    @abstractmethod
    def visit_intrinsic_call(self, call: puya.awst.nodes.IntrinsicCall) -> T: ...

    @abstractmethod
    def visit_size_of(self, call: puya.awst.nodes.SizeOf) -> T: ...

    @abstractmethod
    def visit_puya_lib_call(self, call: puya.awst.nodes.PuyaLibCall) -> T: ...

    @abstractmethod
    def visit_group_transaction_reference(
        self, ref: puya.awst.nodes.GroupTransactionReference
    ) -> T: ...

    @abstractmethod
    def visit_create_inner_transaction(
        self, create_itxn: puya.awst.nodes.CreateInnerTransaction
    ) -> T: ...

    @abstractmethod
    def visit_update_inner_transaction(
        self, update_itxn: puya.awst.nodes.UpdateInnerTransaction
    ) -> T: ...

    @abstractmethod
    def visit_set_inner_transaction_fields(
        self, node: puya.awst.nodes.SetInnerTransactionFields
    ) -> T: ...

    @abstractmethod
    def visit_submit_inner_transaction(
        self, submit: puya.awst.nodes.SubmitInnerTransaction
    ) -> T: ...

    @abstractmethod
    def visit_inner_transaction_field(
        self, itxn_field: puya.awst.nodes.InnerTransactionField
    ) -> T: ...

    @abstractmethod
    def visit_assert_expression(self, statement: puya.awst.nodes.AssertExpression) -> T: ...

    @abstractmethod
    def visit_checked_maybe(self, call: puya.awst.nodes.CheckedMaybe) -> T: ...

    @abstractmethod
    def visit_arc4_decode(self, expr: puya.awst.nodes.ARC4Decode) -> T: ...

    @abstractmethod
    def visit_arc4_encode(self, expr: puya.awst.nodes.ARC4Encode) -> T: ...

    @abstractmethod
    def visit_array_concat(self, expr: puya.awst.nodes.ArrayConcat) -> T: ...

    @abstractmethod
    def visit_array_extend(self, expr: puya.awst.nodes.ArrayExtend) -> T: ...

    @abstractmethod
    def visit_tuple_expression(self, expr: puya.awst.nodes.TupleExpression) -> T: ...

    @abstractmethod
    def visit_tuple_item_expression(self, expr: puya.awst.nodes.TupleItemExpression) -> T: ...

    @abstractmethod
    def visit_field_expression(self, expr: puya.awst.nodes.FieldExpression) -> T: ...

    @abstractmethod
    def visit_index_expression(self, expr: puya.awst.nodes.IndexExpression) -> T: ...

    @abstractmethod
    def visit_slice_expression(self, expr: puya.awst.nodes.SliceExpression) -> T: ...

    @abstractmethod
    def visit_conditional_expression(self, expr: puya.awst.nodes.ConditionalExpression) -> T: ...

    @abstractmethod
    def visit_single_evaluation(self, expr: puya.awst.nodes.SingleEvaluation) -> T: ...

    @abstractmethod
    def visit_app_state_expression(self, expr: puya.awst.nodes.AppStateExpression) -> T: ...

    @abstractmethod
    def visit_app_account_state_expression(
        self, expr: puya.awst.nodes.AppAccountStateExpression
    ) -> T: ...

    @abstractmethod
    def visit_new_array(self, expr: puya.awst.nodes.NewArray) -> T: ...

    @abstractmethod
    def visit_array_length(self, expr: puya.awst.nodes.ArrayLength) -> T: ...

    @abstractmethod
    def visit_new_struct(self, expr: puya.awst.nodes.NewStruct) -> T: ...

    @abstractmethod
    def visit_bytes_comparison_expression(
        self, expr: puya.awst.nodes.BytesComparisonExpression
    ) -> T: ...

    @abstractmethod
    def visit_subroutine_call_expression(
        self, expr: puya.awst.nodes.SubroutineCallExpression
    ) -> T: ...

    @abstractmethod
    def visit_bytes_binary_operation(self, expr: puya.awst.nodes.BytesBinaryOperation) -> T: ...

    @abstractmethod
    def visit_boolean_binary_operation(
        self, expr: puya.awst.nodes.BooleanBinaryOperation
    ) -> T: ...

    @abstractmethod
    def visit_uint64_unary_operation(self, expr: puya.awst.nodes.UInt64UnaryOperation) -> T: ...

    @abstractmethod
    def visit_bytes_unary_operation(self, expr: puya.awst.nodes.BytesUnaryOperation) -> T: ...

    @abstractmethod
    def visit_not_expression(self, expr: puya.awst.nodes.Not) -> T: ...

    @abstractmethod
    def visit_reinterpret_cast(self, expr: puya.awst.nodes.ReinterpretCast) -> T: ...

    @abstractmethod
    def visit_enumeration(self, expr: puya.awst.nodes.Enumeration) -> T: ...

    @abstractmethod
    def visit_method_constant(self, expr: puya.awst.nodes.MethodConstant) -> T: ...

    @abstractmethod
    def visit_array_pop(self, expr: puya.awst.nodes.ArrayPop) -> T: ...

    @abstractmethod
    def visit_array_replace(self, expr: puya.awst.nodes.ArrayReplace) -> T: ...

    @abstractmethod
    def visit_copy(self, expr: puya.awst.nodes.Copy) -> T: ...

    @abstractmethod
    def visit_reversed(self, expr: puya.awst.nodes.Reversed) -> T: ...

    @abstractmethod
    def visit_state_get(self, expr: puya.awst.nodes.StateGet) -> T: ...

    @abstractmethod
    def visit_state_get_ex(self, expr: puya.awst.nodes.StateGetEx) -> T: ...

    @abstractmethod
    def visit_state_exists(self, expr: puya.awst.nodes.StateExists) -> T: ...

    @abstractmethod
    def visit_template_var(self, expr: puya.awst.nodes.TemplateVar) -> T: ...

    @abstractmethod
    def visit_intersection_slice_expression(
        self, expr: puya.awst.nodes.IntersectionSliceExpression
    ) -> T: ...

    @abstractmethod
    def visit_box_prefixed_key_expression(
        self, expr: puya.awst.nodes.BoxPrefixedKeyExpression
    ) -> T: ...

    @abstractmethod
    def visit_box_value_expression(self, expr: puya.awst.nodes.BoxValueExpression) -> T: ...

    @abstractmethod
    def visit_uint64_postfix_unary_operation(
        self, expr: puya.awst.nodes.UInt64PostfixUnaryOperation
    ) -> T: ...

    @abstractmethod
    def visit_biguint_postfix_unary_operation(
        self, expr: puya.awst.nodes.BigUIntPostfixUnaryOperation
    ) -> T: ...

    @abstractmethod
    def visit_arc4_router(self, expr: puya.awst.nodes.ARC4Router) -> T: ...

    @abstractmethod
    def visit_range(self, node: puya.awst.nodes.Range) -> T: ...

    @abstractmethod
    def visit_emit(self, emit: puya.awst.nodes.Emit) -> T: ...

    @abstractmethod
    def visit_comma_expression(self, expr: puya.awst.nodes.CommaExpression) -> T: ...


class ARC4WTypeVisitor[T](ABC):
    @abstractmethod
    def visit_basic_arc4_type(self, wtype: puya.awst.wtypes.ARC4Type) -> T: ...

    @abstractmethod
    def visit_arc4_uint(self, wtype: puya.awst.wtypes.ARC4UIntN) -> T: ...

    @abstractmethod
    def visit_arc4_ufixed(self, wtype: puya.awst.wtypes.ARC4UFixedNxM) -> T: ...

    @abstractmethod
    def visit_arc4_tuple(self, wtype: puya.awst.wtypes.ARC4Tuple) -> T: ...

    @abstractmethod
    def visit_arc4_dynamic_array(self, wtype: puya.awst.wtypes.ARC4DynamicArray) -> T: ...

    @abstractmethod
    def visit_arc4_static_array(self, wtype: puya.awst.wtypes.ARC4StaticArray) -> T: ...

    @abstractmethod
    def visit_arc4_struct(self, wtype: puya.awst.wtypes.ARC4Struct) -> T: ...


class WTypeVisitor[T](ARC4WTypeVisitor[T]):
    @abstractmethod
    def visit_basic_type(self, wtype: puya.awst.wtypes.WType) -> T: ...

    @abstractmethod
    def visit_enumeration_type(self, wtype: puya.awst.wtypes.WEnumeration) -> T: ...

    @abstractmethod
    def visit_group_transaction_type(self, wtype: puya.awst.wtypes.WGroupTransaction) -> T: ...

    @abstractmethod
    def visit_inner_transaction_type(self, wtype: puya.awst.wtypes.WInnerTransaction) -> T: ...

    @abstractmethod
    def visit_bytes_type(self, wtype: puya.awst.wtypes.BytesWType) -> T: ...

    @abstractmethod
    def visit_inner_transaction_fields_type(
        self, wtype: puya.awst.wtypes.WInnerTransactionFields
    ) -> T: ...

    @abstractmethod
    def visit_struct_type(self, wtype: puya.awst.wtypes.WStructType) -> T: ...

    @abstractmethod
    def visit_stack_array(self, wtype: puya.awst.wtypes.StackArray) -> T: ...

    @abstractmethod
    def visit_reference_array(self, wtype: puya.awst.wtypes.ReferenceArray) -> T: ...

    @abstractmethod
    def visit_tuple_type(self, wtype: puya.awst.wtypes.WTuple) -> T: ...
