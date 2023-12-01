from __future__ import annotations  # needed to break import cycle

import typing as t
from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    import wyvern.awst.nodes

T = t.TypeVar("T")


class StatementVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_block(self, statement: wyvern.awst.nodes.Block) -> T:
        ...

    @abstractmethod
    def visit_if_else(self, statement: wyvern.awst.nodes.IfElse) -> T:
        ...

    @abstractmethod
    def visit_while_loop(self, statement: wyvern.awst.nodes.WhileLoop) -> T:
        ...

    @abstractmethod
    def visit_break_statement(self, statement: wyvern.awst.nodes.BreakStatement) -> T:
        ...

    @abstractmethod
    def visit_return_statement(self, statement: wyvern.awst.nodes.ReturnStatement) -> T:
        ...

    @abstractmethod
    def visit_continue_statement(self, statement: wyvern.awst.nodes.ContinueStatement) -> T:
        ...

    @abstractmethod
    def visit_expression_statement(self, statement: wyvern.awst.nodes.ExpressionStatement) -> T:
        ...

    @abstractmethod
    def visit_assert_statement(self, statement: wyvern.awst.nodes.AssertStatement) -> T:
        ...

    @abstractmethod
    def visit_uint64_augmented_assignment(
        self, statement: wyvern.awst.nodes.UInt64AugmentedAssignment
    ) -> T:
        ...

    @abstractmethod
    def visit_biguint_augmented_assignment(
        self, statement: wyvern.awst.nodes.BigUIntAugmentedAssignment
    ) -> T:
        ...

    @abstractmethod
    def visit_bytes_augmented_assignment(
        self, statement: wyvern.awst.nodes.BytesAugmentedAssignment
    ) -> T:
        ...

    @abstractmethod
    def visit_for_in_loop(self, statement: wyvern.awst.nodes.ForInLoop) -> T:
        ...

    @abstractmethod
    def visit_assignment_statement(self, statement: wyvern.awst.nodes.AssignmentStatement) -> T:
        ...


class ModuleStatementVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_constant_declaration(self, statement: wyvern.awst.nodes.ConstantDeclaration) -> T:
        ...

    @abstractmethod
    def visit_subroutine(self, statement: wyvern.awst.nodes.Subroutine) -> T:
        ...

    @abstractmethod
    def visit_contract_fragment(self, statement: wyvern.awst.nodes.ContractFragment) -> T:
        ...

    @abstractmethod
    def visit_structure_definition(self, statement: wyvern.awst.nodes.StructureDefinition) -> T:
        ...

    @abstractmethod
    def visit_contract_method(self, statement: wyvern.awst.nodes.ContractMethod) -> T:
        ...


class ExpressionVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_assignment_expression(self, expr: wyvern.awst.nodes.AssignmentExpression) -> T:
        ...

    @abstractmethod
    def visit_uint64_binary_operation(self, expr: wyvern.awst.nodes.UInt64BinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_biguint_binary_operation(self, expr: wyvern.awst.nodes.BigUIntBinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_uint64_constant(self, expr: wyvern.awst.nodes.UInt64Constant) -> T:
        ...

    @abstractmethod
    def visit_biguint_constant(self, expr: wyvern.awst.nodes.BigUIntConstant) -> T:
        ...

    @abstractmethod
    def visit_bool_constant(self, expr: wyvern.awst.nodes.BoolConstant) -> T:
        ...

    @abstractmethod
    def visit_bytes_constant(self, expr: wyvern.awst.nodes.BytesConstant) -> T:
        ...

    @abstractmethod
    def visit_address_constant(self, expr: wyvern.awst.nodes.AddressConstant) -> T:
        ...

    @abstractmethod
    def visit_numeric_comparison_expression(
        self, expr: wyvern.awst.nodes.NumericComparisonExpression
    ) -> T:
        ...

    @abstractmethod
    def visit_var_expression(self, expr: wyvern.awst.nodes.VarExpression) -> T:
        ...

    @abstractmethod
    def visit_intrinsic_call(self, call: wyvern.awst.nodes.IntrinsicCall) -> T:
        ...

    @abstractmethod
    def visit_bytes_decode(self, expr: wyvern.awst.nodes.BytesDecode) -> T:
        ...

    @abstractmethod
    def visit_abi_decode(self, expr: wyvern.awst.nodes.AbiDecode) -> T:
        ...

    @abstractmethod
    def visit_abi_constant(self, expr: wyvern.awst.nodes.AbiConstant) -> T:
        ...

    @abstractmethod
    def visit_abi_encode(self, expr: wyvern.awst.nodes.AbiEncode) -> T:
        ...

    @abstractmethod
    def visit_tuple_expression(self, expr: wyvern.awst.nodes.TupleExpression) -> T:
        ...

    @abstractmethod
    def visit_tuple_item_expression(self, expr: wyvern.awst.nodes.TupleItemExpression) -> T:
        ...

    @abstractmethod
    def visit_field_expression(self, expr: wyvern.awst.nodes.FieldExpression) -> T:
        ...

    @abstractmethod
    def visit_index_expression(self, expr: wyvern.awst.nodes.IndexExpression) -> T:
        ...

    @abstractmethod
    def visit_slice_expression(self, expr: wyvern.awst.nodes.SliceExpression) -> T:
        ...

    @abstractmethod
    def visit_conditional_expression(self, expr: wyvern.awst.nodes.ConditionalExpression) -> T:
        ...

    @abstractmethod
    def visit_temporary_variable(self, expr: wyvern.awst.nodes.TemporaryVariable) -> T:
        ...

    @abstractmethod
    def visit_app_state_expression(self, expr: wyvern.awst.nodes.AppStateExpression) -> T:
        ...

    @abstractmethod
    def visit_app_account_state_expression(
        self, expr: wyvern.awst.nodes.AppAccountStateExpression
    ) -> T:
        ...

    def visit_new_array(self, expr: wyvern.awst.nodes.NewArray) -> T:
        raise NotImplementedError

    def visit_array_append(self, expr: wyvern.awst.nodes.ArrayAppend) -> T:
        raise NotImplementedError

    def visit_new_struct(self, expr: wyvern.awst.nodes.NewStruct) -> T:
        raise NotImplementedError

    @abstractmethod
    def visit_bytes_comparison_expression(
        self, expr: wyvern.awst.nodes.BytesComparisonExpression
    ) -> T:
        ...

    @abstractmethod
    def visit_subroutine_call_expression(
        self, expr: wyvern.awst.nodes.SubroutineCallExpression
    ) -> T:
        ...

    @abstractmethod
    def visit_bytes_binary_operation(self, expr: wyvern.awst.nodes.BytesBinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_boolean_binary_operation(self, expr: wyvern.awst.nodes.BooleanBinaryOperation) -> T:
        ...

    @abstractmethod
    def visit_uint64_unary_operation(self, expr: wyvern.awst.nodes.UInt64UnaryOperation) -> T:
        ...

    @abstractmethod
    def visit_bytes_unary_operation(self, expr: wyvern.awst.nodes.BytesUnaryOperation) -> T:
        ...

    @abstractmethod
    def visit_not_expression(self, expr: wyvern.awst.nodes.Not) -> T:
        ...

    @abstractmethod
    def visit_contains_expression(self, expr: wyvern.awst.nodes.Contains) -> T:
        ...

    @abstractmethod
    def visit_reinterpret_cast(self, expr: wyvern.awst.nodes.ReinterpretCast) -> T:
        ...

    @abstractmethod
    def visit_is_substring(self, expr: wyvern.awst.nodes.IsSubstring) -> T:
        ...

    @abstractmethod
    def visit_enumeration(self, expr: wyvern.awst.nodes.Enumeration) -> T:
        ...

    @abstractmethod
    def visit_new_abi_array(self, expr: wyvern.awst.nodes.NewAbiArray) -> T:
        ...
