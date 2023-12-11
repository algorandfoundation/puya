from __future__ import annotations  # needed to break import cycle

import typing as t
from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    import puya.awst.nodes

T = t.TypeVar("T")


class StatementVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_block(self, statement: puya.awst.nodes.Block) -> T:
        ...

    @abstractmethod
    def visit_if_else(self, statement: puya.awst.nodes.IfElse) -> T:
        ...

    @abstractmethod
    def visit_switch(self, statement: puya.awst.nodes.Switch) -> T:
        ...

    @abstractmethod
    def visit_while_loop(self, statement: puya.awst.nodes.WhileLoop) -> T:
        ...

    @abstractmethod
    def visit_break_statement(self, statement: puya.awst.nodes.BreakStatement) -> T:
        ...

    @abstractmethod
    def visit_return_statement(self, statement: puya.awst.nodes.ReturnStatement) -> T:
        ...

    @abstractmethod
    def visit_continue_statement(self, statement: puya.awst.nodes.ContinueStatement) -> T:
        ...

    @abstractmethod
    def visit_expression_statement(self, statement: puya.awst.nodes.ExpressionStatement) -> T:
        ...

    @abstractmethod
    def visit_assert_statement(self, statement: puya.awst.nodes.AssertStatement) -> T:
        ...

    @abstractmethod
    def visit_uint64_augmented_assignment(
        self, statement: puya.awst.nodes.UInt64AugmentedAssignment
    ) -> T:
        ...

    @abstractmethod
    def visit_biguint_augmented_assignment(
        self, statement: puya.awst.nodes.BigUIntAugmentedAssignment
    ) -> T:
        ...

    @abstractmethod
    def visit_bytes_augmented_assignment(
        self, statement: puya.awst.nodes.BytesAugmentedAssignment
    ) -> T:
        ...

    @abstractmethod
    def visit_for_in_loop(self, statement: puya.awst.nodes.ForInLoop) -> T:
        ...

    @abstractmethod
    def visit_assignment_statement(self, statement: puya.awst.nodes.AssignmentStatement) -> T:
        ...


class ModuleStatementVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_constant_declaration(self, statement: puya.awst.nodes.ConstantDeclaration) -> T:
        ...

    @abstractmethod
    def visit_subroutine(self, statement: puya.awst.nodes.Subroutine) -> T:
        ...

    @abstractmethod
    def visit_contract_fragment(self, statement: puya.awst.nodes.ContractFragment) -> T:
        ...

    @abstractmethod
    def visit_structure_definition(self, statement: puya.awst.nodes.StructureDefinition) -> T:
        ...

    @abstractmethod
    def visit_contract_method(self, statement: puya.awst.nodes.ContractMethod) -> T:
        ...


class ExpressionVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_assignment_expression(self, expr: puya.awst.nodes.AssignmentExpression) -> T:
        ...

    @abstractmethod
    def visit_uint64_binary_operation(self, expr: puya.awst.nodes.UInt64BinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_biguint_binary_operation(self, expr: puya.awst.nodes.BigUIntBinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_integer_constant(self, expr: puya.awst.nodes.IntegerConstant) -> T:
        ...

    @abstractmethod
    def visit_decimal_constant(self, expr: puya.awst.nodes.DecimalConstant) -> T:
        ...

    @abstractmethod
    def visit_bool_constant(self, expr: puya.awst.nodes.BoolConstant) -> T:
        ...

    @abstractmethod
    def visit_bytes_constant(self, expr: puya.awst.nodes.BytesConstant) -> T:
        ...

    @abstractmethod
    def visit_address_constant(self, expr: puya.awst.nodes.AddressConstant) -> T:
        ...

    @abstractmethod
    def visit_numeric_comparison_expression(
        self, expr: puya.awst.nodes.NumericComparisonExpression
    ) -> T:
        ...

    @abstractmethod
    def visit_var_expression(self, expr: puya.awst.nodes.VarExpression) -> T:
        ...

    @abstractmethod
    def visit_intrinsic_call(self, call: puya.awst.nodes.IntrinsicCall) -> T:
        ...

    @abstractmethod
    def visit_checked_maybe(self, call: puya.awst.nodes.CheckedMaybe) -> T:
        ...

    @abstractmethod
    def visit_arc4_decode(self, expr: puya.awst.nodes.ARC4Decode) -> T:
        ...

    @abstractmethod
    def visit_arc4_encode(self, expr: puya.awst.nodes.ARC4Encode) -> T:
        ...

    @abstractmethod
    def visit_arc4_array_encode(self, expr: puya.awst.nodes.ARC4ArrayEncode) -> T:
        ...

    @abstractmethod
    def visit_tuple_expression(self, expr: puya.awst.nodes.TupleExpression) -> T:
        ...

    @abstractmethod
    def visit_tuple_item_expression(self, expr: puya.awst.nodes.TupleItemExpression) -> T:
        ...

    @abstractmethod
    def visit_field_expression(self, expr: puya.awst.nodes.FieldExpression) -> T:
        ...

    @abstractmethod
    def visit_index_expression(self, expr: puya.awst.nodes.IndexExpression) -> T:
        ...

    @abstractmethod
    def visit_slice_expression(self, expr: puya.awst.nodes.SliceExpression) -> T:
        ...

    @abstractmethod
    def visit_conditional_expression(self, expr: puya.awst.nodes.ConditionalExpression) -> T:
        ...

    @abstractmethod
    def visit_temporary_variable(self, expr: puya.awst.nodes.TemporaryVariable) -> T:
        ...

    @abstractmethod
    def visit_app_state_expression(self, expr: puya.awst.nodes.AppStateExpression) -> T:
        ...

    @abstractmethod
    def visit_app_account_state_expression(
        self, expr: puya.awst.nodes.AppAccountStateExpression
    ) -> T:
        ...

    def visit_new_array(self, expr: puya.awst.nodes.NewArray) -> T:
        raise NotImplementedError

    def visit_array_append(self, expr: puya.awst.nodes.ArrayAppend) -> T:
        raise NotImplementedError

    def visit_new_struct(self, expr: puya.awst.nodes.NewStruct) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_bytes_comparison_expression(
        self, expr: puya.awst.nodes.BytesComparisonExpression
    ) -> T:
        ...

    @abstractmethod
    def visit_subroutine_call_expression(
        self, expr: puya.awst.nodes.SubroutineCallExpression
    ) -> T:
        ...

    @abstractmethod
    def visit_bytes_binary_operation(self, expr: puya.awst.nodes.BytesBinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_boolean_binary_operation(self, expr: puya.awst.nodes.BooleanBinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_uint64_unary_operation(self, expr: puya.awst.nodes.UInt64UnaryOperation) -> T:
        ...

    @abstractmethod
    def visit_bytes_unary_operation(self, expr: puya.awst.nodes.BytesUnaryOperation) -> T:
        ...

    @abstractmethod
    def visit_not_expression(self, expr: puya.awst.nodes.Not) -> T:
        ...

    @abstractmethod
    def visit_contains_expression(self, expr: puya.awst.nodes.Contains) -> T:
        ...

    @abstractmethod
    def visit_reinterpret_cast(self, expr: puya.awst.nodes.ReinterpretCast) -> T:
        ...

    @abstractmethod
    def visit_enumeration(self, expr: puya.awst.nodes.Enumeration) -> T:
        ...

    @abstractmethod
    def visit_method_constant(self, expr: puya.awst.nodes.MethodConstant) -> T:
        ...
