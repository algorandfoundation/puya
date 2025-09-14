import typing
from collections.abc import Sequence

import attrs

import puya.awst.visitors
from puya import algo_constants, log, utils
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import BigUIntBinaryOperator, UInt64BinaryOperator
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.awst.txn_fields import TxnField
from puya.awst.wtypes import WInnerTransaction, WInnerTransactionFields
from puya.errors import CodeError, InternalError
from puya.ir import (
    models as ir,
    types_ as types,
)
from puya.ir._utils import multi_value_to_values
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import (
    assignment,
    bytes,
    callsub,
    dynamic_array,
    flow_control,
    iteration,
    itxn,
    mem,
    sequence,
    storage,
)
from puya.ir.builder._utils import assign, get_implicit_return_is_original, get_implicit_return_out
from puya.ir.context import IRBuildContext
from puya.ir.encodings import wtype_to_encoding
from puya.ir.op_utils import OpFactory, assert_value, assign_intrinsic_op, assign_targets, mktemp
from puya.parse import SourceLocation

TExpression: typing.TypeAlias = ir.ValueProvider | None
TStatement: typing.TypeAlias = None

logger = log.get_logger(__name__)


class FunctionIRBuilder(
    puya.awst.visitors.ExpressionVisitor[TExpression],
    puya.awst.visitors.StatementVisitor[TStatement],
):
    def __init__(
        self, context: IRBuildContext, function: awst_nodes.Function, subroutine: ir.Subroutine
    ):
        self.context = context.for_function(function, subroutine, self)
        self._itxn = itxn.InnerTransactionBuilder(self.context)
        self._single_eval_cache = dict[awst_nodes.SingleEvaluation, TExpression]()
        self._visited_exprs = dict[tuple[int, awst_nodes.Expression], TExpression]()

    @classmethod
    def build_body(
        cls,
        ctx: IRBuildContext,
        function: awst_nodes.Function,
        subroutine: ir.Subroutine,
    ) -> None:
        logger.debug(f"Building IR for function {function.full_name}")
        builder = cls(ctx, function, subroutine)
        func_ctx = builder.context
        with func_ctx.log_exceptions():
            block_builder = func_ctx.block_builder
            for p in subroutine.parameters:
                if p.implicit_return:
                    assign(
                        func_ctx,
                        ir.UInt64Constant(value=1, ir_type=types.bool_, source_location=None),
                        name=get_implicit_return_is_original(p.name),
                        assignment_location=None,
                    )
                    assign(
                        func_ctx,
                        p,
                        name=get_implicit_return_out(p.name),
                        assignment_location=None,
                    )
            function.body.accept(builder)
            final_block = block_builder.active_block
            if not final_block.terminated:
                if function.return_type != wtypes.void_wtype:
                    raise CodeError("not all paths return a value", function.body.source_location)
                block_builder.terminate(
                    ir.SubroutineReturn(
                        result=[
                            block_builder.ssa.read_variable(
                                get_implicit_return_out(p.name), p.ir_type, final_block
                            )
                            for p in subroutine.parameters
                            if p.implicit_return
                        ],
                        source_location=None,
                    )
                )
            subroutine.body = block_builder.finalise()
            subroutine.validate_with_ssa()

    def visit_copy(self, expr: awst_nodes.Copy) -> TExpression:
        loc = expr.source_location
        result_ir_type = types.wtype_to_ir_type(expr.wtype, loc, allow_tuple=True)
        ir_type = types.wtype_to_ir_type(
            expr.value.wtype, expr.value.source_location, allow_tuple=True
        )
        if result_ir_type != ir_type:
            raise InternalError("copy node cannot change the structure of a value", loc)

        # For reference types, we need to clone the data
        # For value types, we can just visit the expression and the resulting read
        # will effectively be a copy.
        if not isinstance(ir_type, types.SlotType):
            return self.visit_and_materialise_as_value_or_tuple(expr.value)
        else:
            original_slot = self.visit_and_materialise_single(expr.value)
            new_slot = mem.new_slot(self.context, original_slot.ir_type, loc)
            value = mem.read_slot(self.context, original_slot, loc)
            mem.write_slot(self.context, new_slot, value, loc)
            return new_slot

    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> TExpression:
        loc = expr.source_location

        ir_type = types.wtype_to_ir_type(expr.wtype, loc, allow_tuple=True)
        encoding = wtype_to_encoding(expr.value.wtype, loc)

        value = self.visit_and_materialise_single(expr.value)
        return ir.DecodeBytes.maybe(
            value=value,
            encoding=encoding,
            ir_type=ir_type,
            error_message_override=expr.error_message,
            source_location=loc,
        )

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> TExpression:
        loc = expr.source_location

        value_ir_type = types.wtype_to_ir_type(expr.value.wtype, loc, allow_tuple=True)
        encoding = wtype_to_encoding(expr.wtype, loc)

        values = self.visit_and_materialise(expr.value)

        return ir.BytesEncode.maybe(
            values=values,
            values_type=value_ir_type,
            encoding=encoding,
            error_message_override=expr.error_message,
            source_location=loc,
        )

    def visit_size_of(self, size_of: awst_nodes.SizeOf) -> TExpression:
        loc = size_of.source_location

        wtype = size_of.size_wtype
        if wtype.is_aggregate:
            num_bytes = wtype_to_encoding(wtype, loc).num_bytes
        else:
            num_bytes = types.wtype_to_ir_type(wtype, loc).num_bytes
        if num_bytes is None:
            logger.error("type is dynamically sized", location=loc)
            return ir.Undefined(ir_type=types.uint64, source_location=loc)
        return ir.UInt64Constant(value=num_bytes, source_location=loc)

    def visit_compiled_contract(self, expr: awst_nodes.CompiledContract) -> TExpression:
        prefix = self.context.options.template_vars_prefix if expr.prefix is None else expr.prefix
        template_variables = {
            prefix + k: self.visit_and_materialise_single(v)
            for k, v in expr.template_variables.items()
        }
        # TODO: remove implicit coupling
        #       the coupling here is between the order of values in the ValueTuple
        #       and the structure of the high level python type
        #       once we support nested tuples, this coupling can be removed
        #       and instead support names on WTuple, then each value can be accessed and lowered
        #       via a FieldExpression
        program_pages = [
            ir.CompiledContractReference(
                artifact=expr.contract,
                field=field,
                program_page=page,
                ir_type=types.bytes_,
                source_location=expr.source_location,
                template_variables=template_variables,
            )
            for field in (
                TxnField.ApprovalProgramPages,
                TxnField.ClearStateProgramPages,
            )
            for page in (0, 1)
        ]
        return ir.ValueTuple(
            values=program_pages
            + [
                (
                    self.visit_and_materialise_single(expr.allocation_overrides[field])
                    if field in expr.allocation_overrides
                    else ir.CompiledContractReference(
                        artifact=expr.contract,
                        field=field,
                        ir_type=types.uint64,
                        source_location=expr.source_location,
                        template_variables=template_variables,
                    )
                )
                for field in (
                    TxnField.ExtraProgramPages,
                    TxnField.GlobalNumUint,
                    TxnField.GlobalNumByteSlice,
                    TxnField.LocalNumUint,
                    TxnField.LocalNumByteSlice,
                )
            ],
            source_location=expr.source_location,
        )

    def visit_compiled_logicsig(self, expr: awst_nodes.CompiledLogicSig) -> TExpression:
        prefix = self.context.options.template_vars_prefix if expr.prefix is None else expr.prefix
        template_variables = {
            prefix + k: self.visit_and_materialise_single(v)
            for k, v in expr.template_variables.items()
        }
        return ir.ValueTuple(
            values=[
                ir.CompiledLogicSigReference(
                    artifact=expr.logic_sig,
                    ir_type=types.bytes_,
                    source_location=expr.source_location,
                    template_variables=template_variables,
                )
            ],
            source_location=expr.source_location,
        )

    def visit_assignment_statement(self, stmt: awst_nodes.AssignmentStatement) -> TStatement:
        if not self._itxn.handle_inner_transaction_field_assignments(stmt):
            targets = assignment.handle_assignment_expr(
                self.context,
                target=stmt.target,
                value=stmt.value,
                assignment_location=stmt.source_location,
            )
            self._itxn.add_inner_transaction_submit_result_assignments(
                targets, stmt.value, stmt.source_location
            )
        return None

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> TExpression:
        result = assignment.handle_assignment_expr(
            self.context,
            target=expr.target,
            value=expr.value,
            assignment_location=expr.source_location,
        )
        ir_type = types.wtype_to_ir_type(expr, allow_tuple=True)
        if isinstance(ir_type, types.TupleIRType):
            return ir.ValueTuple(
                values=list(result),
                ir_type=ir_type,
                source_location=expr.source_location,
            )
        else:
            (result_value,) = result
            return result_value

    def visit_biguint_postfix_unary_operation(
        self, expr: awst_nodes.BigUIntPostfixUnaryOperation
    ) -> TExpression:
        target_value = self.visit_and_materialise_single(expr.target)
        rhs = ir.BigUIntConstant(value=1, source_location=expr.source_location)
        match expr.op:
            case awst_nodes.BigUIntPostfixUnaryOperator.increment:
                binary_op = awst_nodes.BigUIntBinaryOperator.add
            case awst_nodes.BigUIntPostfixUnaryOperator.decrement:
                binary_op = awst_nodes.BigUIntBinaryOperator.sub
            case never:
                typing.assert_never(never)

        new_value = create_biguint_binary_op(binary_op, target_value, rhs, expr.source_location)

        assignment.handle_assignment(
            self.context,
            target=expr.target,
            value=self.materialise_value_provider_as_value_or_tuple(new_value, "tmp"),
            is_nested_update=False,
            assignment_location=expr.source_location,
        )
        return target_value

    def visit_uint64_postfix_unary_operation(
        self, expr: awst_nodes.UInt64PostfixUnaryOperation
    ) -> TExpression:
        target_value = self.visit_and_materialise_single(expr.target)
        rhs = ir.UInt64Constant(value=1, source_location=expr.source_location)
        match expr.op:
            case awst_nodes.UInt64PostfixUnaryOperator.increment:
                binary_op = awst_nodes.UInt64BinaryOperator.add
            case awst_nodes.UInt64PostfixUnaryOperator.decrement:
                binary_op = awst_nodes.UInt64BinaryOperator.sub
            case never:
                typing.assert_never(never)

        new_value = create_uint64_binary_op(binary_op, target_value, rhs, expr.source_location)

        assignment.handle_assignment(
            self.context,
            target=expr.target,
            value=self.materialise_value_provider_as_value_or_tuple(new_value, "tmp"),
            is_nested_update=False,
            assignment_location=expr.source_location,
        )
        return target_value

    def visit_uint64_binary_operation(self, expr: awst_nodes.UInt64BinaryOperation) -> TExpression:
        left = self.visit_and_materialise_single(expr.left)
        right = self.visit_and_materialise_single(expr.right)
        return create_uint64_binary_op(expr.op, left, right, expr.source_location)

    def visit_biguint_binary_operation(
        self, expr: awst_nodes.BigUIntBinaryOperation
    ) -> TExpression:
        left = self.visit_and_materialise_single(expr.left)
        right = self.visit_and_materialise_single(expr.right)
        return create_biguint_binary_op(expr.op, left, right, expr.source_location)

    def visit_uint64_unary_operation(self, expr: awst_nodes.UInt64UnaryOperation) -> TExpression:
        return ir.Intrinsic(
            op=AVMOp(expr.op),
            args=[self.visit_and_materialise_single(expr.expr)],
            source_location=expr.source_location,
        )

    def visit_bytes_unary_operation(self, expr: awst_nodes.BytesUnaryOperation) -> TExpression:
        return ir.Intrinsic(
            op=AVMOp(f"b{expr.op}"),
            args=[self.visit_and_materialise_single(expr.expr)],
            source_location=expr.source_location,
        )

    def visit_integer_constant(self, expr: awst_nodes.IntegerConstant) -> TExpression:
        match expr.wtype:
            case wtypes.uint64_wtype:
                if expr.value < 0 or expr.value.bit_length() > 64:
                    raise CodeError(f"invalid {expr.wtype} value", expr.source_location)

                return ir.UInt64Constant(
                    value=expr.value,
                    source_location=expr.source_location,
                    teal_alias=expr.teal_alias,
                )
            case wtypes.biguint_wtype:
                if expr.value < 0 or expr.value.bit_length() > algo_constants.MAX_BIGUINT_BITS:
                    raise CodeError(f"invalid {expr.wtype} value", expr.source_location)

                return ir.BigUIntConstant(value=expr.value, source_location=expr.source_location)
            case wtypes.ARC4UIntN(n=bit_size):
                num_bytes = bit_size // 8
                try:
                    arc4_result = expr.value.to_bytes(num_bytes, "big", signed=False)
                except OverflowError:
                    raise CodeError(f"invalid {expr.wtype} value", expr.source_location) from None
                return ir.BytesConstant(
                    value=arc4_result,
                    encoding=types.AVMBytesEncoding.base16,
                    source_location=expr.source_location,
                )
            case _:
                raise InternalError(
                    f"Unhandled wtype {expr.wtype} for integer constant {expr.value}",
                    expr.source_location,
                )

    def visit_decimal_constant(self, expr: awst_nodes.DecimalConstant) -> TExpression:
        match expr.wtype:
            case wtypes.ARC4UFixedNxM(n=bit_size, m=precision):
                num_bytes = bit_size // 8
                sign, digits, exponent = expr.value.as_tuple()
                adjusted_int = int("".join(map(str, digits)))
                if (
                    sign != 0  # negative
                    or not isinstance(exponent, int)  # infinite
                    or -exponent > precision  # too precise
                    or adjusted_int.bit_length() > bit_size  # too big
                ):
                    raise CodeError(f"invalid {expr.wtype} value", expr.source_location)
                return ir.BytesConstant(
                    source_location=expr.source_location,
                    encoding=types.AVMBytesEncoding.base16,
                    value=adjusted_int.to_bytes(num_bytes, "big", signed=False),
                )
            case _:
                raise InternalError(
                    f"Unhandled wtype {expr.wtype} for decimal constant {expr.value}",
                    expr.source_location,
                )

    def visit_bool_constant(self, expr: awst_nodes.BoolConstant) -> TExpression:
        loc = expr.source_location

        bool_const = ir.UInt64Constant(
            value=int(expr.value),
            ir_type=types.bool_,
            source_location=loc,
        )
        match expr.wtype:
            case wtypes.bool_wtype:
                return bool_const
            case wtypes.arc4_bool_wtype:
                return ir.BytesEncode.maybe(
                    values=[bool_const],
                    values_type=bool_const.ir_type,
                    encoding=wtype_to_encoding(expr.wtype, loc),
                    source_location=loc,
                )
            case _:
                raise InternalError(
                    f"Unexpected wtype {expr.wtype} for BoolConstant", expr.source_location
                )

    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> ir.BytesConstant:
        if len(expr.value) > algo_constants.MAX_BYTES_LENGTH:
            raise CodeError("bytes constant exceeds stack size limits", expr.source_location)
        ir_type = types.wtype_to_ir_type(expr)
        if ir_type is types.bytes_:
            ir_type = types.SizedBytesType(num_bytes=len(expr.value))
        return ir.BytesConstant(
            value=expr.value,
            encoding=types.bytes_enc_to_avm_bytes_enc(expr.encoding),
            ir_type=ir_type,
            source_location=expr.source_location,
        )

    def visit_string_constant(self, expr: awst_nodes.StringConstant) -> ir.ValueProvider:
        loc = expr.source_location
        ir_type = types.wtype_to_ir_type(expr)

        try:
            value = expr.value.encode("utf8")
        except UnicodeError:
            raise CodeError("invalid UTF-8 constant", loc) from None
        if len(value) > algo_constants.MAX_BYTES_LENGTH:
            raise CodeError("bytes constant exceeds stack size limits", loc)

        const = ir.BytesConstant(
            value=value,
            encoding=types.AVMBytesEncoding.utf8,
            ir_type=types.string,
            source_location=loc,
        )
        if ir_type == const.ir_type:
            return const
        elif isinstance(ir_type, types.EncodedType):
            return ir.BytesEncode.maybe(
                values=[const],
                values_type=const.ir_type,
                encoding=ir_type.encoding,
                source_location=loc,
            )
        else:
            raise InternalError(f"Unexpected {ir_type=} for StringConstant", loc)

    @typing.override
    def visit_void_constant(self, expr: awst_nodes.VoidConstant) -> TExpression:
        return None

    def visit_address_constant(self, expr: awst_nodes.AddressConstant) -> TExpression:
        if not utils.valid_address(expr.value):
            # TODO: should this be here, or on IR model? there's pros and cons to each
            raise CodeError("invalid Algorand address", expr.source_location)
        return ir.AddressConstant(
            value=expr.value,
            source_location=expr.source_location,
        )

    def visit_numeric_comparison_expression(
        self, expr: awst_nodes.NumericComparisonExpression
    ) -> TExpression:
        left = self.visit_and_materialise_single(expr.lhs)
        right = self.visit_and_materialise_single(expr.rhs)
        if left.atype != right.atype:
            raise InternalError(
                "Numeric comparison between different numeric types", expr.source_location
            )
        op_code = expr.operator.value
        if left.atype == AVMType.bytes:
            op_code = "b" + op_code

        try:
            avm_op = AVMOp(op_code)
        except ValueError as ex:
            raise InternalError(
                f"Unmapped numeric comparison operator {expr.operator}", expr.source_location
            ) from ex

        return ir.Intrinsic(
            op=avm_op,
            args=[left, right],
            source_location=expr.source_location,
        )

    def visit_checked_maybe(self, expr: awst_nodes.CheckedMaybe) -> TExpression:
        value, check = self.visit_and_materialise(expr.expr, ("value", "check"))
        assert_value(
            self.context,
            check,
            error_message=expr.comment,
            source_location=expr.source_location,
        )
        return value

    def visit_var_expression(self, expr: awst_nodes.VarExpression) -> TExpression:
        ir_type = types.wtype_to_ir_type(expr, allow_tuple=True)
        active_block = self.context.block_builder.active_block
        if not isinstance(ir_type, types.TupleIRType):
            variable = self.context.ssa.read_variable(expr.name, ir_type, active_block)
            return attrs.evolve(variable, source_location=expr.source_location)
        else:
            item_names = ir_type.build_item_names(expr.name)
            item_ir_types = types.ir_type_to_ir_types(ir_type)
            items = [
                self.context.ssa.read_variable(item_name, item_ir_type, active_block)
                for item_name, item_ir_type in zip(item_names, item_ir_types, strict=True)
            ]
            return ir.ValueTuple(
                values=items, ir_type=ir_type, source_location=expr.source_location
            )

    def _add_assert(
        self,
        condition_expr: awst_nodes.Expression | None,
        error_message: str | None,
        loc: SourceLocation,
    ) -> ir.Intrinsic | None:
        condition_value = (
            self.visit_and_materialise_single(condition_expr) if condition_expr else None
        )
        if isinstance(condition_value, ir.UInt64Constant):
            if condition_value.value:
                logger.warning("assertion is always true, ignoring", location=loc)
                return None
            else:
                condition_value = None
        if condition_value is None:
            self.context.block_builder.terminate(
                ir.Fail(source_location=loc, error_message=error_message)
            )
            return None
        else:
            return ir.Intrinsic(
                op=AVMOp("assert"),
                source_location=loc,
                args=[condition_value],
                error_message=error_message,
            )

    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> TExpression:
        match call.op_code:
            case "err":
                return self._add_assert(
                    condition_expr=None, error_message=None, loc=call.source_location
                )
            case "return":
                assert not call.immediates, f"return intrinsic had immediates: {call.immediates}"
                (arg_expr,) = call.stack_args
                exit_value = self.visit_and_materialise_single(arg_expr)
                self.context.block_builder.terminate(
                    ir.ProgramExit(source_location=call.source_location, result=exit_value)
                )
                return None
            case "assert":
                (condition_expr,) = call.stack_args
                return self._add_assert(
                    condition_expr=condition_expr, error_message=None, loc=call.source_location
                )
            case _:
                args = [self.visit_and_materialise_single(arg) for arg in call.stack_args]
                return ir.Intrinsic(
                    op=AVMOp(call.op_code),
                    source_location=call.source_location,
                    args=args,
                    immediates=list(call.immediates),
                    types=types.wtype_to_ir_types(call.wtype, call.source_location),
                )

    def visit_group_transaction_reference(
        self, ref: awst_nodes.GroupTransactionReference
    ) -> TExpression:
        index = self.visit_and_materialise_single(ref.index, "gtxn_idx")
        if (txn_type := ref.wtype.transaction_type) is not None:
            actual_type = assign_intrinsic_op(
                self.context,
                target="gtxn_type",
                op=AVMOp.gtxns,
                immediates=["TypeEnum"],
                args=[index],
                source_location=ref.source_location,
            )
            type_constant = ir.UInt64Constant(
                value=txn_type.value, teal_alias=txn_type.name, source_location=ref.source_location
            )
            type_matches = assign_intrinsic_op(
                self.context,
                target="gtxn_type_matches",
                op=AVMOp.eq,
                args=[actual_type, type_constant],
                source_location=ref.source_location,
            )
            assert_value(
                self.context,
                type_matches,
                error_message=f"transaction type is {txn_type.name}",
                source_location=ref.source_location,
            )
        return index

    def visit_create_inner_transaction(self, call: awst_nodes.CreateInnerTransaction) -> None:
        # for semantic compatibility, this is an error, since we don't evaluate the args
        # here (there would be no point, if we hit this node on its own and not as part
        # of a submit or an assigment, it does nothing)
        logger.error(
            "statement has no effect, did you forget to submit?", location=call.source_location
        )

    def visit_set_inner_transaction_fields(
        self, node: awst_nodes.SetInnerTransactionFields
    ) -> None:
        self._itxn.handle_set_inner_transaction_fields(node)

    def visit_submit_inner_transaction(
        self, submit: awst_nodes.SubmitInnerTransaction
    ) -> TExpression:
        result = self._itxn.handle_submit_inner_transaction(submit)
        result_ir_type = types.wtype_to_ir_type(submit, allow_tuple=True)
        if isinstance(result_ir_type, types.TupleIRType):
            return ir.ValueTuple(
                values=list(result),
                ir_type=result_ir_type,
                source_location=submit.source_location,
            )
        (result_value,) = result
        return result_value

    def visit_update_inner_transaction(self, call: awst_nodes.UpdateInnerTransaction) -> None:
        self._itxn.handle_update_inner_transaction(call)

    def visit_inner_transaction_field(
        self, itxn_field: awst_nodes.InnerTransactionField
    ) -> TExpression:
        return self._itxn.handle_inner_transaction_field(itxn_field)

    def visit_method_constant(self, expr: awst_nodes.MethodConstant) -> TExpression:
        return ir.MethodConstant(value=expr.value, source_location=expr.source_location)

    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> TExpression:
        items = list[ir.Value]()
        for item in expr.items:
            nested_values = self.visit_and_materialise(item)
            items.extend(nested_values)
        return ir.ValueTuple(
            values=items,
            ir_type=types.wtype_to_ir_type(expr.wtype, expr.source_location, allow_tuple=True),
            source_location=expr.source_location,
        )

    def visit_tuple_item_expression(self, expr: awst_nodes.TupleItemExpression) -> TExpression:
        loc = expr.source_location

        tuple_wtype = expr.base.wtype
        assert isinstance(tuple_wtype, wtypes.WTuple | wtypes.ARC4Tuple), "expected tuple wtype"
        base = self.visit_and_materialise(expr.base)

        return sequence.read_aggregate_index_and_decode(
            self.context, tuple_wtype, base, [expr.index], loc
        )

    def visit_named_tuple_expression(self, expr: awst_nodes.NamedTupleExpression) -> TExpression:
        loc = expr.source_location
        tuple_ir_type = types.wtype_to_ir_type(expr.wtype, loc, allow_tuple=True)

        # evaluate fields in order of declaration
        elements_by_name = {
            name: self.visit_and_materialise(value) for name, value in expr.values.items()
        }
        # ensure elements end up in the correct order
        elements = [
            element for field_name in expr.wtype.fields for element in elements_by_name[field_name]
        ]

        return ir.ValueTuple(
            values=elements,
            ir_type=tuple_ir_type,
            source_location=loc,
        )

    def visit_field_expression(self, expr: awst_nodes.FieldExpression) -> TExpression:
        loc = expr.source_location

        tuple_wtype = expr.base.wtype
        assert isinstance(tuple_wtype, wtypes.WTuple | wtypes.ARC4Struct), "expected struct wtype"
        assert tuple_wtype.names is not None, "expected named tuple"
        base = self.visit_and_materialise(expr.base)
        index = tuple_wtype.names.index(expr.name)

        return sequence.read_aggregate_index_and_decode(
            self.context, tuple_wtype, base, [index], loc
        )

    def visit_intersection_slice_expression(
        self, expr: awst_nodes.IntersectionSliceExpression
    ) -> TExpression:
        loc = expr.source_location
        sliceable_type = expr.base.wtype
        if isinstance(sliceable_type, wtypes.WTuple):
            return self._visit_tuple_slice(expr, sliceable_type)
        elif isinstance(sliceable_type, wtypes.BytesWType):
            return bytes.visit_bytes_intersection_slice_expression(self.context, expr)
        elif isinstance(sliceable_type, wtypes.ARC4DynamicArray):
            if expr.begin_index is not None or expr.end_index != -1:
                raise InternalError(
                    f"IntersectionSlice for {expr.wtype.name} currently only supports [:-1]",
                    expr.source_location,
                )
            array = self.visit_and_materialise_single(expr.base)
            builder = dynamic_array.get_builder(self.context, sliceable_type, loc)
            data, _ = builder.pop(array)
            return data
        else:
            raise InternalError(
                f"IntersectionSlice operation IR lowering not implemented for {expr.wtype.name}",
                loc,
            )

    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> TExpression:
        """Slices an enumerable type."""
        if isinstance(expr.base.wtype, wtypes.WTuple):
            return self._visit_tuple_slice(expr, expr.base.wtype)
        elif isinstance(expr.base.wtype, wtypes.BytesWType):
            return bytes.visit_bytes_slice_expression(self.context, expr)
        else:
            raise InternalError(
                f"Slice operation IR lowering not implemented for {expr.wtype.name}",
                expr.source_location,
            )

    def _visit_tuple_slice(
        self,
        expr: awst_nodes.SliceExpression | awst_nodes.IntersectionSliceExpression,
        base_wtype: wtypes.WTuple,
    ) -> TExpression:
        loc = expr.source_location

        tup_value = self.visit_and_materialise(expr.base)
        start_i = extract_const_int(expr.begin_index) or 0
        end_i = extract_const_int(expr.end_index)
        if end_i is None:
            end_i = len(base_wtype.types)

        values = [
            v
            for index in range(start_i, end_i)
            for v in multi_value_to_values(
                sequence.read_tuple_index(base_wtype, tup_value, index, loc)
            )
        ]
        base_ir_type = types.wtype_to_ir_type(base_wtype, loc, allow_tuple=True)
        slice_elements_ir_types = base_ir_type.elements[start_i:end_i]
        if base_ir_type.fields is None:
            slice_fields = None
        else:
            slice_fields = base_ir_type.fields[start_i:end_i]
        ir_type = types.TupleIRType(elements=slice_elements_ir_types, fields=slice_fields)
        return ir.ValueTuple(values=values, ir_type=ir_type, source_location=loc)

    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> TExpression:
        loc = expr.source_location

        base = self.visit_and_materialise_single(expr.base)
        index = self.visit_and_materialise_single(expr.index)

        indexable_wtype = expr.base.wtype
        factory = OpFactory(self.context, loc)
        if isinstance(indexable_wtype, wtypes.BytesWType):
            # note: the below works because Bytes is immutable, so this index expression
            # can never appear as an assignment target
            return factory.extract3(base, index, 1)

        assert isinstance(
            indexable_wtype, wtypes.ReferenceArray | wtypes.ARC4Array
        ), "expected array type"

        return sequence.read_aggregate_index_and_decode(
            self.context, indexable_wtype, [base], [index], loc
        )

    def visit_conditional_expression(self, expr: awst_nodes.ConditionalExpression) -> TExpression:
        return flow_control.handle_conditional_expression(self.context, expr)

    def visit_single_evaluation(self, expr: awst_nodes.SingleEvaluation) -> TExpression:
        try:
            return self._single_eval_cache[expr]
        except KeyError:
            pass
        source = expr.source.accept(self)
        if not (source and source.types):
            result: TExpression = None
        else:
            values = self.materialise_value_provider(source, description="awst_tmp")
            ir_type = types.wtype_to_ir_type(expr, allow_tuple=True)
            if not isinstance(ir_type, types.TupleIRType):
                (result,) = values
            else:
                result = ir.ValueTuple(
                    values=values, ir_type=ir_type, source_location=expr.source_location
                )
        self._single_eval_cache[expr] = result
        return result

    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> TExpression:
        return storage.visit_app_state_expression(self.context, expr)

    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> TExpression:
        return storage.visit_app_account_state_expression(self.context, expr)

    def visit_box_prefixed_key_expression(
        self, expr: awst_nodes.BoxPrefixedKeyExpression
    ) -> TExpression:
        factory = OpFactory(self.context, expr.source_location)
        prefix = self.visit_and_materialise_single(expr.prefix, temp_description="box_key_prefix")
        key_source = self.visit_and_materialise(expr.key, temp_description="materialized_values")
        codec = storage.get_storage_codec(
            expr.key.wtype, awst_nodes.AppStorageKind.box, expr.key.source_location
        )
        key = codec.encode(self.context, key_source, expr.key.source_location)
        return factory.concat(prefix, key, "box_prefixed_key")

    def visit_box_value_expression(self, expr: awst_nodes.BoxValueExpression) -> TExpression:
        return storage.visit_box_value(self.context, expr)

    def visit_state_get_ex(self, expr: awst_nodes.StateGetEx) -> TExpression:
        return storage.visit_state_get_ex(self.context, expr)

    def visit_state_delete(self, statement: awst_nodes.StateDelete) -> TExpression:
        return storage.visit_state_delete(self.context, statement)

    def visit_state_get(self, expr: awst_nodes.StateGet) -> TExpression:
        return storage.visit_state_get(self.context, expr)

    def visit_state_exists(self, expr: awst_nodes.StateExists) -> TExpression:
        return storage.visit_state_exists(self.context, expr.field, expr.source_location)

    def visit_new_array(self, expr: awst_nodes.NewArray) -> TExpression:
        loc = expr.source_location

        array_encoding = wtype_to_encoding(expr.wtype, loc)
        # initialize array with a tuple of provided elements
        tuple_expr = awst_nodes.TupleExpression.from_items(expr.values, loc)
        tuple_ir_type = types.wtype_to_ir_type(tuple_expr.wtype, loc, allow_tuple=True)
        tuple_values = self.visit_and_materialise(tuple_expr)
        encoded_array_vp = ir.BytesEncode.maybe(
            values=tuple_values,
            values_type=tuple_ir_type,
            encoding=array_encoding,
            source_location=loc,
        )
        (encoded_array,) = self.materialise_value_provider(encoded_array_vp, "encoded_array")
        if isinstance(expr.wtype, wtypes.ARC4Array):
            return encoded_array
        elif isinstance(expr.wtype, wtypes.ReferenceArray):
            array_slot_type = types.wtype_to_ir_type(expr.wtype, expr.source_location)
            slot = mem.new_slot(self.context, array_slot_type, loc)
            mem.write_slot(self.context, slot, encoded_array, loc)
            return slot
        else:
            typing.assert_never(expr.wtype)

    def visit_bytes_comparison_expression(
        self, expr: awst_nodes.BytesComparisonExpression
    ) -> TExpression:
        left = self.visit_and_materialise_single(expr.lhs)
        right = self.visit_and_materialise_single(expr.rhs)
        op_code = expr.operator.value
        try:
            avm_op = AVMOp(op_code)
        except ValueError as ex:
            raise InternalError(
                f"Unmapped bytes comparison operator {expr.operator}", expr.source_location
            ) from ex

        return ir.Intrinsic(
            op=avm_op,
            args=[left, right],
            source_location=expr.source_location,
        )

    def visit_subroutine_call_expression(
        self, expr: awst_nodes.SubroutineCallExpression
    ) -> TExpression:
        return callsub.visit_subroutine_call_expression(self.context, expr)

    def visit_puya_lib_call(self, call: awst_nodes.PuyaLibCall) -> TExpression:
        return callsub.visit_puya_lib_call_expression(self.context, call)

    def visit_bytes_binary_operation(self, expr: awst_nodes.BytesBinaryOperation) -> TExpression:
        left = self.visit_and_materialise_single(expr.left)
        right = self.visit_and_materialise_single(expr.right)
        return create_bytes_binary_op(expr.op, left, right, expr.source_location)

    def visit_boolean_binary_operation(
        self, expr: awst_nodes.BooleanBinaryOperation
    ) -> TExpression:
        if not isinstance(expr.right, awst_nodes.VarExpression | awst_nodes.BoolConstant):
            true_block, false_block, merge_block = self.context.block_builder.mkblocks(
                "bool_true", "bool_false", "bool_merge", source_location=expr.source_location
            )
            tmp_name = self.context.next_tmp_name(f"{expr.op}_result")

            flow_control.process_conditional(
                self.context, expr, true=true_block, false=false_block, loc=expr.source_location
            )
            self.context.block_builder.activate_block(true_block)
            assign(
                self.context,
                ir.UInt64Constant(value=1, ir_type=types.bool_, source_location=None),
                name=tmp_name,
                assignment_location=None,
            )
            self.context.block_builder.goto(merge_block)

            self.context.block_builder.activate_block(false_block)
            assign(
                self.context,
                ir.UInt64Constant(value=0, ir_type=types.bool_, source_location=None),
                name=tmp_name,
                assignment_location=None,
            )
            self.context.block_builder.goto(merge_block)
            self.context.block_builder.activate_block(merge_block)
            return self.context.ssa.read_variable(
                variable=tmp_name, ir_type=types.bool_, block=merge_block
            )

        left = self.visit_and_materialise_single(expr.left)
        right = self.visit_and_materialise_single(expr.right)
        match expr.op:
            case "and":
                op = AVMOp.and_
            case "or":
                op = AVMOp.or_
            case _:
                raise InternalError(
                    f"Unexpected/unimplemented boolean operator in IR builder: {expr.op}",
                    expr.source_location,
                )
        return ir.Intrinsic(
            op=op,
            args=[left, right],
            source_location=expr.source_location,
        )

    def visit_not_expression(self, expr: awst_nodes.Not) -> TExpression:
        negated = self.visit_and_materialise_single(expr.expr)
        return ir.Intrinsic(
            op=AVMOp("!"),
            args=[negated],
            source_location=expr.source_location,
        )

    def visit_reinterpret_cast(self, expr: awst_nodes.ReinterpretCast) -> TExpression:
        # should be a no-op for us, but we validate the cast here too
        source = self.visit_expr(expr.expr)
        (inner_ir_type,) = source.types
        outer_ir_type = types.wtype_to_ir_type(expr)
        # don't need to do anything further if outer type is a super type of inner type
        if outer_ir_type <= inner_ir_type:
            return source
        inner_avm_type = inner_ir_type.avm_type
        outer_avm_type = outer_ir_type.avm_type
        if inner_avm_type != outer_avm_type:
            raise InternalError(
                f"Tried to reinterpret {expr.expr.wtype} as {expr.wtype},"
                " but resulting AVM types are incompatible:"
                f" {inner_avm_type} and {outer_avm_type}, respectively",
                expr.source_location,
            )
        target = mktemp(
            self.context,
            outer_ir_type,
            description=f"reinterpret_{outer_ir_type.name}",
            source_location=expr.source_location,
        )
        assign_targets(
            self.context,
            source=source,
            targets=[target],
            assignment_location=expr.source_location,
        )
        return target

    def visit_block(self, block: awst_nodes.Block) -> TStatement:
        # When traversing, blocks can appear nested arbitrarily, so start
        # a new one if a label is encountered, otherwise there's no difference
        # so we can just keep adding to the current block.
        # However, some looping constructs need to create the block before it can be
        # visited, in which case the block must be activated before this function.
        if block.label != self.context.block_builder.active_block.label:
            ir_block = self.context.block_builder.mkblock(block)
            self.context.block_builder.goto(ir_block)
            self.context.block_builder.activate_block(ir_block)

        for stmt in block.body:
            stmt.accept(self)

    def visit_goto(self, statement: awst_nodes.Goto) -> TStatement:
        self.context.block_builder.goto_label(statement.target, statement.source_location)

    def visit_if_else(self, stmt: awst_nodes.IfElse) -> TStatement:
        flow_control.handle_if_else(self.context, stmt)

    def visit_switch(self, statement: awst_nodes.Switch) -> TStatement:
        flow_control.handle_switch(self.context, statement)

    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> TStatement:
        flow_control.handle_while_loop(self.context, statement)

    def visit_loop_exit(self, statement: awst_nodes.LoopExit) -> TStatement:
        self.context.block_builder.loop_break(statement.source_location)

    def visit_return_statement(self, statement: awst_nodes.ReturnStatement) -> TStatement:
        if statement.value is not None:
            result = list(self.visit_and_materialise(statement.value))
        else:
            result = []

        for param in self.context.subroutine.parameters:
            if param.implicit_return:
                result.append(
                    self.context.ssa.read_variable(
                        param.name,
                        param.ir_type,
                        self.context.block_builder.active_block,
                    )
                )
        actual_return_types = [r.ir_type for r in result]
        expected_return_types = self.context.subroutine.returns
        if [t.avm_type for t in actual_return_types] != [
            t.avm_type for t in expected_return_types
        ]:
            logger.error(
                f"invalid return type {actual_return_types}, expected {expected_return_types}",
                location=statement.source_location,
            )
            result = [
                ir.Undefined(ir_type=ir_type, source_location=statement.source_location)
                for ir_type in expected_return_types
            ]
        self.context.block_builder.terminate(
            ir.SubroutineReturn(
                source_location=statement.source_location,
                result=result,
            )
        )

    def visit_assert_expression(self, expr: awst_nodes.AssertExpression) -> TStatement:
        op = self._add_assert(
            condition_expr=expr.condition,
            error_message=expr.error_message,
            loc=expr.source_location,
        )
        if op:
            self.context.block_builder.add(op)

    def visit_template_var(self, expr: awst_nodes.TemplateVar) -> TExpression:
        loc = expr.source_location

        value_ir_type = types.wtype_to_ir_type(expr.wtype, loc, allow_tuple=True)
        # template variables can be uint64 or bytes
        # so can't just use encoded type in all scenarios
        # so handle TupleIRType specifically as something that will be encoded
        if isinstance(value_ir_type, types.TupleIRType):
            encoding = wtype_to_encoding(expr.wtype, loc)

            return ir.DecodeBytes.maybe(
                value=ir.TemplateVar(
                    name=expr.name,
                    ir_type=types.EncodedType(encoding),
                    source_location=loc,
                ),
                encoding=encoding,
                ir_type=value_ir_type,
                source_location=loc,
            )
        else:
            return ir.TemplateVar(
                name=expr.name,
                ir_type=value_ir_type,
                source_location=loc,
            )

    def visit_loop_continue(self, statement: awst_nodes.LoopContinue) -> TStatement:
        self.context.block_builder.loop_continue(statement.source_location)

    def visit_expression_statement(self, statement: awst_nodes.ExpressionStatement) -> TStatement:
        # NOTE: popping of ignored return values should happen at code gen time
        result = self._visit_and_check_for_double_eval(statement.expr)
        if result is None:
            wtype = statement.expr.wtype
            match wtype:
                case wtypes.void_wtype:
                    pass
                case _ if (isinstance(wtype, WInnerTransaction | WInnerTransactionFields)):
                    # inner transaction wtypes aren't true expressions
                    pass
                case _:
                    raise InternalError(
                        f"Expression statement with type {statement.expr.wtype} "
                        f"generated no result",
                        statement.source_location,
                    )
        elif isinstance(result, ir.Op):
            self.context.block_builder.add(result)
        else:
            # If we get a Value (e.g. a Register or some such) it's something that's being
            # discarded effectively.
            # The frontend should have already warned about this
            # if this value is unused and has no side effects it will get eliminated by the
            # optimizer
            self.materialise_value_provider(result, "tmp")

    def visit_uint64_augmented_assignment(
        self, statement: awst_nodes.UInt64AugmentedAssignment
    ) -> TStatement:
        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        expr = create_uint64_binary_op(statement.op, target_value, rhs, statement.source_location)

        assignment.handle_assignment(
            self.context,
            target=statement.target,
            value=self.materialise_value_provider_as_value_or_tuple(expr, "tmp"),
            is_nested_update=False,
            assignment_location=statement.source_location,
        )

    def visit_biguint_augmented_assignment(
        self, statement: awst_nodes.BigUIntAugmentedAssignment
    ) -> TStatement:
        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        expr = create_biguint_binary_op(statement.op, target_value, rhs, statement.source_location)

        assignment.handle_assignment(
            self.context,
            target=statement.target,
            value=self.materialise_value_provider_as_value_or_tuple(expr, "tmp"),
            is_nested_update=False,
            assignment_location=statement.source_location,
        )

    def visit_bytes_augmented_assignment(
        self, statement: awst_nodes.BytesAugmentedAssignment
    ) -> TStatement:
        loc = statement.source_location

        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        if statement.target.wtype == wtypes.arc4_string_alias:
            builder = dynamic_array.get_builder(self.context, statement.target.wtype, loc)
            value: ir.ValueProvider = builder.concat(target_value, rhs, rhs.ir_type)
        else:
            value = create_bytes_binary_op(statement.op, target_value, rhs, loc)

        assignment.handle_assignment(
            self.context,
            target=statement.target,
            value=self.materialise_value_provider_as_value_or_tuple(value, "tmp"),
            is_nested_update=False,
            assignment_location=loc,
        )

    def visit_enumeration(self, expr: awst_nodes.Enumeration) -> TStatement:
        raise CodeError("Nested enumeration is not currently supported", expr.source_location)

    def visit_reversed(self, expr: awst_nodes.Reversed) -> TExpression:
        raise CodeError("Reversed is not valid outside of an enumeration", expr.source_location)

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> TStatement:
        iteration.handle_for_in_loop(self.context, statement)

    def visit_new_struct(self, expr: awst_nodes.NewStruct) -> TExpression:
        loc = expr.source_location

        # struct is constructed from its tuple equivalent, so get tuple type info
        tuple_wtype = wtypes.WTuple(types=expr.wtype.types, source_location=None)
        tuple_ir_type = types.wtype_to_ir_type(tuple_wtype, loc, allow_tuple=True)
        tuple_encoding = wtype_to_encoding(tuple_wtype, loc)

        # double check encodings match
        struct_encoding = wtype_to_encoding(expr.wtype, loc)
        assert (
            tuple_encoding == struct_encoding
        ), "expected struct encoding to match tuple encoding"

        # evaluate struct in order of declaration
        elements_by_name = {
            name: self.visit_and_materialise(value) for name, value in expr.values.items()
        }
        # ensure elements are in correct order
        elements = [
            element for field_name in expr.wtype.fields for element in elements_by_name[field_name]
        ]

        return ir.BytesEncode.maybe(
            values=elements,
            values_type=tuple_ir_type,
            encoding=tuple_encoding,
            source_location=loc,
        )

    def visit_array_pop(self, expr: awst_nodes.ArrayPop) -> TExpression:
        loc = expr.source_location

        array_wtype = expr.base.wtype
        builder = dynamic_array.get_builder(self.context, array_wtype, loc)

        array_or_slot = self.visit_and_materialise_single(expr.base)
        if isinstance(array_or_slot.ir_type, types.SlotType):
            array = mem.read_slot(self.context, array_or_slot, loc)
        else:
            array = array_or_slot
        updated_array, popped_item = builder.pop(array)

        if isinstance(array_or_slot.ir_type, types.SlotType):
            mem.write_slot(self.context, array_or_slot, updated_array, loc)
        else:
            assignment.handle_assignment(
                self.context,
                expr.base,
                updated_array,
                is_nested_update=True,
                assignment_location=loc,
            )
        return popped_item

    def visit_array_replace(self, expr: awst_nodes.ArrayReplace) -> TExpression:
        loc = expr.source_location

        array_wtype = expr.base.wtype
        assert isinstance(array_wtype, wtypes.ARC4Array), "expected ARC4Array"

        array = self.visit_and_materialise_single(expr.base)
        index = self.visit_and_materialise_single(expr.index)
        values = self.visit_and_materialise(expr.value)

        return sequence.encode_and_write_aggregate_index(
            self.context, array_wtype, array, [index], values, loc
        )

    def visit_array_concat(self, expr: awst_nodes.ArrayConcat) -> TExpression:
        assert expr.left.wtype == expr.wtype, "AWST validation requires result type == left type"
        array, result = self._array_concat(expr.left, expr.right, expr.source_location)
        return result

    def visit_array_extend(self, expr: awst_nodes.ArrayExtend) -> None:
        loc = expr.source_location

        array, result = self._array_concat(expr.base, expr.other, loc)

        # update array reference
        if isinstance(array.ir_type, types.SlotType):
            # note: the order things are evaluated is important to be semantically correct
            #       for reference arrays
            # 1. array expr
            # 2. iterable expr
            # 3. read slot to get contents
            # 4. concat
            # 5. write slot with updated contents
            # _array_concat should do steps 1-4, now need to update slot
            mem.write_slot(self.context, array, result, loc)
        else:
            assignment.handle_assignment(
                self.context,
                target=expr.base,
                value=result,
                is_nested_update=True,
                assignment_location=loc,
            )

    def _array_concat(
        self,
        array_expr: awst_nodes.Expression,
        iter_expr: awst_nodes.Expression,
        loc: SourceLocation,
    ) -> tuple[ir.Value, ir.Value]:
        """
        Concatenates an array and iterable expression

        Returns the original array and the concatenation result
        """

        # materialise expressions
        array_or_slot = self.visit_and_materialise_single(array_expr)
        iterable = self.visit_and_materialise_as_value_or_tuple(iter_expr)

        # read iterable
        iterable_ir_type = types.wtype_to_ir_type(iter_expr.wtype, loc, allow_tuple=True)
        if isinstance(iterable.ir_type, types.SlotType):
            iterable_ir_type = iterable.ir_type.contents
            assert isinstance(iterable, ir.Value), "expected Value for SlotType"
            iterable = mem.read_slot(self.context, iterable, loc)

        # read array
        if isinstance(array_or_slot.ir_type, types.SlotType):
            array = mem.read_slot(self.context, array_or_slot, loc)
        else:
            array = array_or_slot

        # do concat
        builder = dynamic_array.get_builder(self.context, array_expr.wtype, loc)
        return array_or_slot, builder.concat(array, iterable, iterable_ir_type)

    def visit_array_length(self, expr: awst_nodes.ArrayLength) -> TExpression:
        loc = expr.source_location

        array_wtype = expr.array.wtype
        assert isinstance(
            array_wtype, wtypes.ReferenceArray | wtypes.ARC4Array
        ), "expected array wtype"

        array = self.visit_and_materialise_single(expr.array)

        array_encoding = wtype_to_encoding(array_wtype, loc)
        return sequence.get_length(array_encoding, array, loc)

    def visit_arc4_router(self, expr: awst_nodes.ARC4Router) -> TExpression:
        root = self.context.root
        if not isinstance(root, awst_nodes.Contract):
            raise CodeError(
                "cannot create ARC-4 router outside of a contract", expr.source_location
            )

        return ir.InvokeSubroutine(
            target=self.context.routers[root.id],
            args=[],
            source_location=expr.source_location,
        )

    def visit_emit(self, expr: awst_nodes.Emit) -> TExpression:
        factory = OpFactory(self.context, expr.source_location)
        value = self.visit_and_materialise_single(expr.value)
        prefix = ir.MethodConstant(value=expr.signature, source_location=expr.source_location)
        event = factory.concat(prefix, value, "event")

        self.context.block_builder.add(
            ir.Intrinsic(
                op=AVMOp("log"),
                args=[event],
                source_location=expr.source_location,
            )
        )
        return None

    def visit_range(self, node: awst_nodes.Range) -> TExpression:
        raise CodeError("unexpected range location", node.source_location)

    def visit_comma_expression(self, expr: awst_nodes.CommaExpression) -> TExpression:
        results = [inner.accept(self) for inner in expr.expressions]
        return results[-1]

    @typing.override
    def visit_convert_array(self, expr: awst_nodes.ConvertArray) -> TExpression:
        source = self.visit_and_materialise_single(expr.expr)
        source_wtype = expr.expr.wtype
        assert isinstance(
            source_wtype, wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray | wtypes.ReferenceArray
        )
        return sequence.convert_array(
            self.context,
            source,
            source_wtype=source_wtype,
            target_wtype=expr.wtype,
            loc=expr.source_location,
        )

    def visit_and_materialise_single(
        self, expr: awst_nodes.Expression, temp_description: str = "tmp"
    ) -> ir.Value:
        """Translate an AWST Expression into a single Value"""
        values = self.visit_and_materialise(expr, temp_description=temp_description)
        try:
            (value,) = values
        except ValueError as ex:
            expr_str = expr.accept(ToCodeVisitor())
            raise InternalError(
                "visit_and_materialise_single should not be used when"
                f" an expression could be multi-valued, expression was: {expr_str}",
                expr.source_location,
            ) from ex
        return value

    def visit_and_materialise_as_value_or_tuple(
        self, expr: awst_nodes.Expression, temp_description: str | Sequence[str] = "tmp"
    ) -> ir.Value | ir.ValueTuple:
        value_seq_or_provider = self._visit_and_check_for_double_eval(
            expr, materialise_as=temp_description
        )
        if value_seq_or_provider is None:
            raise InternalError(
                "No value produced by expression IR conversion", expr.source_location
            )
        assert isinstance(value_seq_or_provider, ir.Value | ir.ValueTuple)
        return value_seq_or_provider

    def visit_and_materialise(
        self, expr: awst_nodes.Expression, temp_description: str | Sequence[str] = "tmp"
    ) -> Sequence[ir.Value]:
        value_seq_or_provider = self._visit_and_check_for_double_eval(
            expr, materialise_as=temp_description
        )
        if value_seq_or_provider is None:
            raise InternalError(
                "No value produced by expression IR conversion", expr.source_location
            )
        return self.materialise_value_provider(value_seq_or_provider, description=temp_description)

    def visit_expr(self, expr: awst_nodes.Expression) -> ir.ValueProvider:
        """Visit the expression and ensure result is not None"""
        value_seq_or_provider = self._visit_and_check_for_double_eval(expr)
        if value_seq_or_provider is None:
            raise InternalError(
                "No value produced by expression IR conversion", expr.source_location
            )
        return value_seq_or_provider

    def _visit_and_check_for_double_eval(
        self, expr: awst_nodes.Expression, *, materialise_as: str | Sequence[str] | None = None
    ) -> ir.ValueProvider | None:
        # explicit SingleEvaluation nodes already handle this
        if isinstance(expr, awst_nodes.SingleEvaluation):
            return expr.accept(self)
        # include the expression in the key to ensure the lifetime of the
        # expression is as long as the cache.
        # Temporary nodes may end up with the same id if nothing is referencing them
        # e.g. such as used in _update_implicit_out_var
        expr_id = id(expr), expr
        try:
            result = self._visited_exprs[expr_id]
        except KeyError:
            pass
        else:
            if isinstance(result, ir.ValueProvider) and not isinstance(
                result, ir.ValueTuple | ir.Value
            ):
                raise InternalError(
                    "double evaluation of expression without materialization", expr.source_location
                )
            expr_str = expr.accept(ToCodeVisitor())
            logger.debug(
                f"encountered already materialized expression ({expr_str}),"
                f" reusing result: {result!s}",
                location=expr.source_location,
            )
            return result
        source = expr.accept(self)
        if materialise_as is None or not (source and source.types):
            result = source
        else:
            result = self.materialise_value_provider_as_value_or_tuple(
                source, description=materialise_as
            )
        self._visited_exprs[expr_id] = result
        return result

    def materialise_value_provider_as_value_or_tuple(
        self, provider: ir.ValueProvider, description: str | Sequence[str]
    ) -> ir.Value | ir.ValueTuple:
        """
        Given a ValueProvider with arity of N
        return a Value if N = 1, else a ValueTuple of length N.

        Anything which is already a Value or ValueTuple is passed through without change.
        Otherwise, the result is assigned to a temporary register, which is returned
        """
        if isinstance(provider, ir.Value | ir.ValueTuple):
            return provider

        ir_types = provider.types
        if not ir_types:
            raise InternalError(
                "Attempted to assign from expression that has no result", provider.source_location
            )

        if isinstance(description, str):
            temp_description: Sequence[str] = [description] * len(ir_types)
        else:
            temp_description = description
        targets = [
            mktemp(self.context, ir_type, provider.source_location, description=descr)
            for ir_type, descr in zip(ir_types, temp_description, strict=True)
        ]
        assign_targets(
            context=self.context,
            source=provider,
            targets=targets,
            # TODO: should this be the source location of the site forcing materialisation?
            assignment_location=provider.source_location,
        )
        try:
            (value,) = targets
        except ValueError:
            return ir.ValueTuple(values=targets, source_location=provider.source_location)
        else:
            return value

    def materialise_value_provider(
        self, provider: ir.ValueProvider, description: str | Sequence[str]
    ) -> list[ir.Value]:
        """
        Given a ValueProvider with arity of N, return a Value sequence of length N.
        """
        value_or_tuple = self.materialise_value_provider_as_value_or_tuple(provider, description)
        return multi_value_to_values(value_or_tuple)


def create_uint64_binary_op(
    op: UInt64BinaryOperator,
    left: ir.Value,
    right: ir.Value,
    source_location: SourceLocation,
) -> ir.Intrinsic:
    avm_op: AVMOp
    match op:
        case UInt64BinaryOperator.floor_div:
            avm_op = AVMOp.div_floor
        case UInt64BinaryOperator.pow:
            avm_op = AVMOp.exp
        case UInt64BinaryOperator.lshift:
            avm_op = AVMOp.shl
        case UInt64BinaryOperator.rshift:
            avm_op = AVMOp.shr
        case _:
            try:
                avm_op = AVMOp(op.value)
            except ValueError as ex:
                raise InternalError(
                    f"Unhandled uint64 binary operator: {op}", source_location
                ) from ex
    return ir.Intrinsic(op=avm_op, args=[left, right], source_location=source_location)


def create_biguint_binary_op(
    op: BigUIntBinaryOperator,
    left: ir.Value,
    right: ir.Value,
    source_location: SourceLocation,
) -> ir.Intrinsic:
    avm_op: AVMOp
    match op:
        case BigUIntBinaryOperator.floor_div:
            avm_op = AVMOp.div_floor_bytes
        case _:
            try:
                avm_op = AVMOp("b" + op.value)
            except ValueError as ex:
                raise InternalError(
                    f"Unhandled uint64 binary operator: {op}", source_location
                ) from ex
    return ir.Intrinsic(
        op=avm_op,
        args=[left, right],
        types=(types.biguint,),
        source_location=source_location,
    )


def create_bytes_binary_op(
    op: awst_nodes.BytesBinaryOperator,
    lhs: ir.Value,
    rhs: ir.Value,
    source_location: SourceLocation,
) -> ir.ValueProvider:
    match op:
        case awst_nodes.BytesBinaryOperator.add:
            return ir.Intrinsic(
                op=AVMOp.concat,
                args=[lhs, rhs],
                source_location=source_location,
            )
        case awst_nodes.BytesBinaryOperator.bit_and:
            return ir.Intrinsic(
                op=AVMOp.bitwise_and_bytes,
                args=[lhs, rhs],
                source_location=source_location,
            )
        case awst_nodes.BytesBinaryOperator.bit_or:
            return ir.Intrinsic(
                op=AVMOp.bitwise_or_bytes,
                args=[lhs, rhs],
                source_location=source_location,
            )
        case awst_nodes.BytesBinaryOperator.bit_xor:
            return ir.Intrinsic(
                op=AVMOp.bitwise_xor_bytes,
                args=[lhs, rhs],
                source_location=source_location,
            )
    raise InternalError("Unsupported BytesBinaryOperator: " + op)


def extract_const_int(expr: awst_nodes.Expression | int | None) -> int | None:
    """
    Check expr is an IntegerConstant, int literal, or None, and return constant value (or None)
    """
    match expr:
        case None:
            return None
        case awst_nodes.IntegerConstant(value=value):
            return value
        case int(value):
            return value
        case _:
            raise InternalError(
                f"Expected either constant or None for index, got {type(expr).__name__}",
                expr.source_location,
            )
