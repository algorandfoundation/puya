import typing
from collections.abc import Iterator, Sequence

import attrs

import puya.awst.visitors
from puya import algo_constants, log, utils
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import BigUIntBinaryOperator, TupleExpression, UInt64BinaryOperator
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.awst.txn_fields import TxnField
from puya.awst.wtypes import WInnerTransaction, WInnerTransactionFields
from puya.errors import CodeError, InternalError
from puya.ir.arc4_types import effective_array_encoding, wtype_to_arc4_wtype
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4, arrays, flow_control, mem, storage
from puya.ir.builder._tuple_util import get_tuple_item_values
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    assign,
    assign_intrinsic_op,
    assign_targets,
    assign_temp,
    extract_const_int,
    get_implicit_return_is_original,
    get_implicit_return_out,
    mktemp,
)
from puya.ir.builder.arc4 import ARC4_FALSE, ARC4_TRUE
from puya.ir.builder.assignment import handle_assignment, handle_assignment_expr
from puya.ir.builder.bytes import (
    visit_bytes_intersection_slice_expression,
    visit_bytes_slice_expression,
)
from puya.ir.builder.callsub import (
    visit_puya_lib_call_expression,
    visit_subroutine_call_expression,
)
from puya.ir.builder.iteration import handle_for_in_loop
from puya.ir.builder.itxn import InnerTransactionBuilder
from puya.ir.context import IRBuildContext
from puya.ir.models import (
    AddressConstant,
    ArrayReadIndex,
    BigUIntConstant,
    BytesConstant,
    CompiledContractReference,
    CompiledLogicSigReference,
    Fail,
    Intrinsic,
    InvokeSubroutine,
    MethodConstant,
    Op,
    ProgramExit,
    Subroutine,
    SubroutineReturn,
    TemplateVar,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
    WriteSlot,
)
from puya.ir.types_ import (
    ArrayType,
    AVMBytesEncoding,
    PrimitiveIRType,
    SizedBytesType,
    SlotType,
    bytes_enc_to_avm_bytes_enc,
    wtype_to_ir_type,
    wtype_to_ir_types,
)
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation

TExpression: typing.TypeAlias = ValueProvider | None
TStatement: typing.TypeAlias = None

logger = log.get_logger(__name__)


class FunctionIRBuilder(
    puya.awst.visitors.ExpressionVisitor[TExpression],
    puya.awst.visitors.StatementVisitor[TStatement],
):
    def __init__(
        self, context: IRBuildContext, function: awst_nodes.Function, subroutine: Subroutine
    ):
        self.context = context.for_function(function, subroutine, self)
        self._itxn = InnerTransactionBuilder(self.context)
        self._single_eval_cache = dict[awst_nodes.SingleEvaluation, TExpression]()
        self._visited_exprs = dict[tuple[int, awst_nodes.Expression], TExpression]()

    @classmethod
    def build_body(
        cls,
        ctx: IRBuildContext,
        function: awst_nodes.Function,
        subroutine: Subroutine,
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
                        UInt64Constant(
                            value=1, ir_type=PrimitiveIRType.bool, source_location=None
                        ),
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
                    SubroutineReturn(
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
        # For reference types, we need to clone the data
        # For value types, we can just visit the expression and the resulting read
        # will effectively be a copy. We assign the copy to a new register in case it is
        # mutated.
        match expr.value.wtype:
            case wtypes.ARC4Type():
                # Arc4 encoded types are value types
                original_value = self.visit_and_materialise_single(expr.value)
                return assign_temp(
                    temp_description="copy",
                    source=original_value,
                    source_location=expr.source_location,
                    context=self.context,
                )
            case wtypes.ReferenceArray():
                loc = expr.source_location
                original_slot = self.visit_and_materialise_single(expr.value)
                new_slot = mem.new_slot(self.context, original_slot.ir_type, loc)
                value = mem.read_slot(self.context, original_slot, loc)
                mem.write_slot(self.context, new_slot, value, loc)
                return new_slot

        raise InternalError(
            f"Invalid source wtype for Copy {expr.value.wtype}", expr.source_location
        )

    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> TExpression:
        value = self.visit_and_materialise_single(expr.value)
        assert isinstance(
            expr.value.wtype, wtypes.ARC4Type
        ), f"ARC4Decode node should have value with ARC-4 type, got: {expr.value.wtype}"
        return arc4.decode_arc4_value(
            self.context, value, expr.value.wtype, expr.wtype, expr.source_location
        )

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> TExpression:
        value = self.visit_expr(expr.value)
        return arc4.encode_value_provider(
            self.context, value, expr.value.wtype, expr.wtype, expr.source_location
        )

    def visit_size_of(self, size_of: awst_nodes.SizeOf) -> TExpression:
        wtype = size_of.size_wtype
        if isinstance(wtype, wtypes.WTuple):
            wtype = wtype_to_arc4_wtype(wtype, size_of.source_location)
        ir_type = wtype_to_ir_type(wtype, size_of.source_location)
        if ir_type.num_bytes is None:
            logger.error(
                f"{size_of.size_wtype} is dynamically sized", location=size_of.source_location
            )
        num_bytes = ir_type.num_bytes or 0
        return UInt64Constant(value=num_bytes, source_location=size_of.source_location)

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
            CompiledContractReference(
                artifact=expr.contract,
                field=field,
                program_page=page,
                ir_type=PrimitiveIRType.bytes,
                source_location=expr.source_location,
                template_variables=template_variables,
            )
            for field in (
                TxnField.ApprovalProgramPages,
                TxnField.ClearStateProgramPages,
            )
            for page in (0, 1)
        ]
        return ValueTuple(
            values=program_pages
            + [
                (
                    self.visit_and_materialise_single(expr.allocation_overrides[field])
                    if field in expr.allocation_overrides
                    else CompiledContractReference(
                        artifact=expr.contract,
                        field=field,
                        ir_type=PrimitiveIRType.uint64,
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
        return ValueTuple(
            values=[
                CompiledLogicSigReference(
                    artifact=expr.logic_sig,
                    ir_type=PrimitiveIRType.bytes,
                    source_location=expr.source_location,
                    template_variables=template_variables,
                )
            ],
            source_location=expr.source_location,
        )

    def visit_assignment_statement(self, stmt: awst_nodes.AssignmentStatement) -> TStatement:
        if not self._itxn.handle_inner_transaction_field_assignments(stmt):
            targets = handle_assignment_expr(
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
        result = handle_assignment_expr(
            self.context,
            target=expr.target,
            value=expr.value,
            assignment_location=expr.source_location,
        )
        if not result:
            # HOW DID YOU GET HERE
            raise CodeError("Assignment expression did not return a result", expr.source_location)
        if len(result) == 1:
            return result[0]
        else:
            return ValueTuple(expr.source_location, list(result))

    def visit_biguint_postfix_unary_operation(
        self, expr: awst_nodes.BigUIntPostfixUnaryOperation
    ) -> TExpression:
        target_value = self.visit_and_materialise_single(expr.target)
        rhs = BigUIntConstant(value=1, source_location=expr.source_location)
        match expr.op:
            case awst_nodes.BigUIntPostfixUnaryOperator.increment:
                binary_op = awst_nodes.BigUIntBinaryOperator.add
            case awst_nodes.BigUIntPostfixUnaryOperator.decrement:
                binary_op = awst_nodes.BigUIntBinaryOperator.sub
            case never:
                typing.assert_never(never)

        new_value = create_biguint_binary_op(binary_op, target_value, rhs, expr.source_location)

        handle_assignment(
            self.context,
            target=expr.target,
            value=new_value,
            is_nested_update=False,
            assignment_location=expr.source_location,
        )
        return target_value

    def visit_uint64_postfix_unary_operation(
        self, expr: awst_nodes.UInt64PostfixUnaryOperation
    ) -> TExpression:
        target_value = self.visit_and_materialise_single(expr.target)
        rhs = UInt64Constant(value=1, source_location=expr.source_location)
        match expr.op:
            case awst_nodes.UInt64PostfixUnaryOperator.increment:
                binary_op = awst_nodes.UInt64BinaryOperator.add
            case awst_nodes.UInt64PostfixUnaryOperator.decrement:
                binary_op = awst_nodes.UInt64BinaryOperator.sub
            case never:
                typing.assert_never(never)

        new_value = create_uint64_binary_op(binary_op, target_value, rhs, expr.source_location)

        handle_assignment(
            self.context,
            target=expr.target,
            value=new_value,
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
        return Intrinsic(
            op=AVMOp(expr.op),
            args=[self.visit_and_materialise_single(expr.expr)],
            source_location=expr.source_location,
        )

    def visit_bytes_unary_operation(self, expr: awst_nodes.BytesUnaryOperation) -> TExpression:
        return Intrinsic(
            op=AVMOp(f"b{expr.op}"),
            args=[self.visit_and_materialise_single(expr.expr)],
            source_location=expr.source_location,
        )

    def visit_integer_constant(self, expr: awst_nodes.IntegerConstant) -> TExpression:
        match expr.wtype:
            case wtypes.uint64_wtype:
                if expr.value < 0 or expr.value.bit_length() > 64:
                    raise CodeError(f"invalid {expr.wtype} value", expr.source_location)

                return UInt64Constant(
                    value=expr.value,
                    source_location=expr.source_location,
                    teal_alias=expr.teal_alias,
                )
            case wtypes.biguint_wtype:
                if expr.value < 0 or expr.value.bit_length() > algo_constants.MAX_BIGUINT_BITS:
                    raise CodeError(f"invalid {expr.wtype} value", expr.source_location)

                return BigUIntConstant(value=expr.value, source_location=expr.source_location)
            case wtypes.ARC4UIntN(n=bit_size):
                num_bytes = bit_size // 8
                try:
                    arc4_result = expr.value.to_bytes(num_bytes, "big", signed=False)
                except OverflowError:
                    raise CodeError(f"invalid {expr.wtype} value", expr.source_location) from None
                return BytesConstant(
                    value=arc4_result,
                    encoding=AVMBytesEncoding.base16,
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
                return BytesConstant(
                    source_location=expr.source_location,
                    encoding=AVMBytesEncoding.base16,
                    value=adjusted_int.to_bytes(num_bytes, "big", signed=False),
                )
            case _:
                raise InternalError(
                    f"Unhandled wtype {expr.wtype} for decimal constant {expr.value}",
                    expr.source_location,
                )

    def visit_bool_constant(self, expr: awst_nodes.BoolConstant) -> TExpression:
        match expr.wtype:
            case wtypes.bool_wtype:
                return UInt64Constant(
                    value=int(expr.value),
                    ir_type=PrimitiveIRType.bool,
                    source_location=expr.source_location,
                )
            case wtypes.arc4_bool_wtype:
                return BytesConstant(
                    value=(ARC4_TRUE if expr.value else ARC4_FALSE),
                    encoding=AVMBytesEncoding.base16,
                    source_location=expr.source_location,
                )
            case _:
                raise InternalError(
                    f"Unexpected wtype {expr.wtype} for BoolConstant", expr.source_location
                )

    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> BytesConstant:
        if len(expr.value) > algo_constants.MAX_BYTES_LENGTH:
            raise CodeError(f"invalid {expr.wtype} value", expr.source_location)
        ir_type = wtype_to_ir_type(expr)
        if ir_type is PrimitiveIRType.bytes:
            ir_type = SizedBytesType(num_bytes=len(expr.value))
        return BytesConstant(
            value=expr.value,
            encoding=bytes_enc_to_avm_bytes_enc(expr.encoding),
            ir_type=ir_type,
            source_location=expr.source_location,
        )

    def visit_string_constant(self, expr: awst_nodes.StringConstant) -> BytesConstant:
        try:
            value = expr.value.encode("utf8")
        except UnicodeError:
            value = None
        if value is None:
            raise CodeError(f"invalid {expr.wtype} value", expr.source_location)

        match expr.wtype:
            case wtypes.string_wtype:
                encoding = AVMBytesEncoding.utf8
            case wtypes.arc4_string_alias:
                encoding = AVMBytesEncoding.base16
                value = len(value).to_bytes(2) + value
            case _:
                raise InternalError(
                    f"Unexpected wtype {expr.wtype} for StringConstant", expr.source_location
                )

        if len(value) > algo_constants.MAX_BYTES_LENGTH:
            raise CodeError(f"invalid {expr.wtype} value", expr.source_location)

        return BytesConstant(
            value=value,
            encoding=encoding,
            source_location=expr.source_location,
        )

    @typing.override
    def visit_void_constant(self, expr: awst_nodes.VoidConstant) -> TExpression:
        return None

    def visit_address_constant(self, expr: awst_nodes.AddressConstant) -> TExpression:
        if not utils.valid_address(expr.value):
            # TODO: should this be here, or on IR model? there's pros and cons to each
            raise CodeError("invalid Algorand address", expr.source_location)
        return AddressConstant(
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

        return Intrinsic(
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

    def _expand_tuple_var(
        self, name: str, wtype: wtypes.WTuple, *, default_source_location: SourceLocation
    ) -> Iterator[Value]:
        for idx, wt in enumerate(wtype.types):
            item_name = format_tuple_index(wtype, name, idx)
            if isinstance(wt, wtypes.WTuple):
                yield from self._expand_tuple_var(
                    item_name, wt, default_source_location=default_source_location
                )
            else:
                yield self.context.ssa.read_variable(
                    variable=item_name,
                    ir_type=wtype_to_ir_type(wt, wtype.source_location or default_source_location),
                    block=self.context.block_builder.active_block,
                )

    def visit_var_expression(self, expr: awst_nodes.VarExpression) -> TExpression:
        if isinstance(expr.wtype, wtypes.WTuple):
            values = tuple(
                self._expand_tuple_var(
                    expr.name,
                    expr.wtype,
                    default_source_location=expr.source_location,
                )
            )
            return ValueTuple(values=values, source_location=expr.source_location)
        ir_type = wtype_to_ir_type(expr)
        variable = self.context.ssa.read_variable(
            expr.name, ir_type, self.context.block_builder.active_block
        )
        variable = attrs.evolve(variable, source_location=expr.source_location)
        return variable

    def _add_assert(
        self,
        condition_expr: awst_nodes.Expression | None,
        error_message: str | None,
        loc: SourceLocation,
    ) -> Intrinsic | None:
        condition_value = (
            self.visit_and_materialise_single(condition_expr) if condition_expr else None
        )
        if isinstance(condition_value, UInt64Constant):
            if condition_value.value:
                logger.warning("assertion is always true, ignoring", location=loc)
                return None
            else:
                condition_value = None
        if condition_value is None:
            self.context.block_builder.terminate(
                Fail(source_location=loc, error_message=error_message)
            )
            return None
        else:
            return Intrinsic(
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
                    ProgramExit(source_location=call.source_location, result=exit_value)
                )
                return None
            case "assert":
                (condition_expr,) = call.stack_args
                return self._add_assert(
                    condition_expr=condition_expr, error_message=None, loc=call.source_location
                )
            case _:
                args = [self.visit_and_materialise_single(arg) for arg in call.stack_args]
                return Intrinsic(
                    op=AVMOp(call.op_code),
                    source_location=call.source_location,
                    args=args,
                    immediates=list(call.immediates),
                    types=wtype_to_ir_types(call.wtype, call.source_location),
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
            type_constant = UInt64Constant(
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
        if len(result) == 1:
            return result[0]
        return ValueTuple(
            values=list(result),
            source_location=submit.source_location,
        )

    def visit_update_inner_transaction(self, call: awst_nodes.UpdateInnerTransaction) -> None:
        self._itxn.handle_update_inner_transaction(call)

    def visit_inner_transaction_field(
        self, itxn_field: awst_nodes.InnerTransactionField
    ) -> TExpression:
        return self._itxn.handle_inner_transaction_field(itxn_field)

    def visit_method_constant(self, expr: awst_nodes.MethodConstant) -> TExpression:
        return MethodConstant(value=expr.value, source_location=expr.source_location)

    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> TExpression:
        items = list[Value]()
        for item in expr.items:
            nested_values = self.visit_and_materialise(item)
            items.extend(nested_values)
        return ValueTuple(
            source_location=expr.source_location,
            values=items,
        )

    def visit_tuple_item_expression(self, expr: awst_nodes.TupleItemExpression) -> TExpression:
        if isinstance(expr.base.wtype, wtypes.WTuple):
            tup = self.visit_and_materialise(expr.base)
            return get_tuple_item_values(
                tuple_values=tup,
                tuple_wtype=expr.base.wtype,
                index=expr.index,
                target_wtype=expr.wtype,
                source_location=expr.source_location,
            )
        elif isinstance(expr.base.wtype, wtypes.ARC4Tuple):
            base = self.visit_and_materialise_single(expr.base)
            return arc4.arc4_tuple_index(
                self.context,
                base=base,
                index=expr.index,
                wtype=expr.base.wtype,
                source_location=expr.source_location,
            )
        else:
            raise InternalError(
                f"Tuple indexing operation IR lowering"
                f" not implemented for base type {expr.base.wtype.name}",
                expr.source_location,
            )

    def visit_field_expression(self, expr: awst_nodes.FieldExpression) -> TExpression:
        if isinstance(expr.base.wtype, wtypes.WStructType):
            raise NotImplementedError
        if isinstance(expr.base.wtype, wtypes.WTuple):
            index = expr.base.wtype.name_to_index(expr.name, expr.source_location)
            tup = self.visit_and_materialise(expr.base)
            return get_tuple_item_values(
                tuple_values=tup,
                tuple_wtype=expr.base.wtype,
                index=index,
                target_wtype=expr.wtype,
                source_location=expr.source_location,
            )
        if isinstance(expr.base.wtype, wtypes.ARC4Struct):
            base = self.visit_and_materialise_single(expr.base)
            index = expr.base.wtype.names.index(expr.name)
            return arc4.arc4_tuple_index(
                self.context,
                base=base,
                index=index,
                wtype=expr.base.wtype,
                source_location=expr.source_location,
            )
        else:
            raise InternalError(
                f"Field access IR lowering"
                f" not implemented for base type {expr.base.wtype.name}",
                expr.source_location,
            )

    def visit_intersection_slice_expression(
        self, expr: awst_nodes.IntersectionSliceExpression
    ) -> TExpression:
        sliceable_type = expr.base.wtype
        if isinstance(sliceable_type, wtypes.WTuple):
            return self._visit_tuple_slice(expr, sliceable_type)
        elif isinstance(sliceable_type, wtypes.BytesWType):
            return visit_bytes_intersection_slice_expression(self.context, expr)
        elif isinstance(sliceable_type, wtypes.StackArray):
            if expr.begin_index is not None or expr.end_index != -1:
                raise InternalError(
                    f"IntersectionSlice for {expr.wtype.name} currently only supports [:-1]",
                    expr.source_location,
                )
            arc4_array_type = effective_array_encoding(sliceable_type, expr.base.source_location)
            array = self.context.visitor.visit_and_materialise_single(expr.base)
            _, data = arc4.invoke_arc4_array_pop(
                self.context, arc4_array_type.element_type, array, expr.source_location
            )
            return data
        else:
            raise InternalError(
                f"IntersectionSlice operation IR lowering not implemented for {expr.wtype.name}",
                expr.source_location,
            )

    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> TExpression:
        """Slices an enumerable type."""
        if isinstance(expr.base.wtype, wtypes.WTuple):
            return self._visit_tuple_slice(expr, expr.base.wtype)
        elif isinstance(expr.base.wtype, wtypes.BytesWType):
            return visit_bytes_slice_expression(self.context, expr)
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
        tup = self.visit_and_materialise(expr.base)
        start_i = extract_const_int(expr.begin_index) or 0
        end_i = extract_const_int(expr.end_index)
        return get_tuple_item_values(
            tuple_values=tup,
            tuple_wtype=base_wtype,
            index=(start_i, end_i),
            target_wtype=expr.wtype,
            source_location=expr.source_location,
        )

    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> TExpression:
        index = self.visit_and_materialise_single(expr.index)
        base = self.visit_and_materialise_single(expr.base)

        indexable_wtype = expr.base.wtype
        if isinstance(indexable_wtype, wtypes.BytesWType):
            # note: the below works because Bytes is immutable, so this index expression
            # can never appear as an assignment target
            if isinstance(index, UInt64Constant) and index.value <= 255:
                return Intrinsic(
                    op=AVMOp.extract,
                    args=[base],
                    immediates=[index.value, 1],
                    source_location=expr.source_location,
                )
            else:
                return Intrinsic(
                    op=AVMOp.extract3,
                    args=[
                        base,
                        index,
                        UInt64Constant(value=1, source_location=expr.source_location),
                    ],
                    source_location=expr.source_location,
                )
        elif isinstance(indexable_wtype, wtypes.ReferenceArray):
            slot = mem.read_slot(self.context, base, expr.base.source_location)
            return ArrayReadIndex(array=slot, index=index, source_location=expr.source_location)
        elif isinstance(indexable_wtype, wtypes.StackArray):
            arc4_array_type = effective_array_encoding(indexable_wtype, expr.base.source_location)
            encoded_read_vp = arc4.arc4_array_index(
                self.context,
                array_wtype=arc4_array_type,
                array=base,
                index=index,
                source_location=expr.source_location,
            )
            return arc4.maybe_decode_arc4_value_provider(
                self.context,
                encoded_read_vp,
                arc4_array_type.element_type,
                indexable_wtype.element_type,
                expr.source_location,
                temp_description="arc4_item",
            )
        elif isinstance(indexable_wtype, wtypes.ARC4Array):
            return arc4.arc4_array_index(
                self.context,
                array_wtype=indexable_wtype,
                array=base,
                index=index,
                source_location=expr.source_location,
            )
        else:
            raise InternalError(
                f"Indexing operation IR lowering not implemented for {expr.wtype.name}",
                expr.source_location,
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
            if len(values) == 1:
                (result,) = values
            else:
                result = ValueTuple(values=values, source_location=expr.source_location)
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
        prefix = self.context.visitor.visit_and_materialise_single(
            expr.prefix, temp_description="box_key_prefix"
        )
        key_source = self.context.visitor.visit_and_materialise(
            expr.key, temp_description="materialized_values"
        )
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
        # delegate for ARC-4 arrays
        if isinstance(expr.wtype, wtypes.ARC4Array):
            return arc4.encode_arc4_exprs_as_array(
                self.context, expr.wtype, expr.values, expr.source_location
            )
        # handle native arrays
        if isinstance(expr.wtype, wtypes.StackArray):
            encoded_type = effective_array_encoding(expr.wtype, expr.source_location)
            # stack arrays are effectively ARC-4 encoded, values might need converting
            if not expr.values:
                return arc4.encode_arc4_exprs_as_array(
                    self.context, encoded_type, expr.values, expr.source_location
                )
            empty_array_expr = awst_nodes.NewArray(
                values=(),
                wtype=encoded_type,
                source_location=expr.source_location,
            )
            items_tuple = TupleExpression.from_items(expr.values, expr.source_location)
            return arc4.dynamic_array_concat_and_convert(
                self.context,
                array_wtype=encoded_type,
                array_expr=empty_array_expr,
                iter_expr=items_tuple,
                source_location=expr.source_location,
            )
        else:
            loc = expr.source_location
            array_slot_type = wtype_to_ir_type(expr.wtype, expr.source_location)
            assert isinstance(array_slot_type, SlotType)
            array_type = array_slot_type.contents
            assert isinstance(array_type, ArrayType)
            array_contents = arrays.get_array_encoded_items(
                self.context,
                awst_nodes.TupleExpression.from_items(expr.values, expr.source_location),
                array_type=array_type,
            )
            slot = mem.new_slot(self.context, array_slot_type, loc)
            mem.write_slot(self.context, slot, array_contents, loc)
            return slot

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

        return Intrinsic(
            op=avm_op,
            args=[left, right],
            source_location=expr.source_location,
        )

    def visit_subroutine_call_expression(
        self, expr: awst_nodes.SubroutineCallExpression
    ) -> TExpression:
        return visit_subroutine_call_expression(self.context, expr)

    def visit_puya_lib_call(self, call: awst_nodes.PuyaLibCall) -> TExpression:
        return visit_puya_lib_call_expression(self.context, call)

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
                UInt64Constant(value=1, ir_type=PrimitiveIRType.bool, source_location=None),
                name=tmp_name,
                assignment_location=None,
            )
            self.context.block_builder.goto(merge_block)

            self.context.block_builder.activate_block(false_block)
            assign(
                self.context,
                UInt64Constant(value=0, ir_type=PrimitiveIRType.bool, source_location=None),
                name=tmp_name,
                assignment_location=None,
            )
            self.context.block_builder.goto(merge_block)
            self.context.block_builder.activate_block(merge_block)
            return self.context.ssa.read_variable(
                variable=tmp_name, ir_type=PrimitiveIRType.bool, block=merge_block
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
        return Intrinsic(
            op=op,
            args=[left, right],
            source_location=expr.source_location,
        )

    def visit_not_expression(self, expr: awst_nodes.Not) -> TExpression:
        negated = self.visit_and_materialise_single(expr.expr)
        return Intrinsic(
            op=AVMOp("!"),
            args=[negated],
            source_location=expr.source_location,
        )

    def visit_reinterpret_cast(self, expr: awst_nodes.ReinterpretCast) -> TExpression:
        # should be a no-op for us, but we validate the cast here too
        source = self.visit_expr(expr.expr)
        (inner_ir_type,) = source.types
        outer_ir_type = wtype_to_ir_type(expr)
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
        if block.label:
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
        return_types = [r.ir_type for r in result]
        if [t.avm_type for t in return_types] != [
            t.avm_type for t in self.context.subroutine.returns
        ]:
            raise CodeError(
                f"invalid return type {return_types}, expected {self.context.subroutine.returns}",
                statement.source_location,
            )
        self.context.block_builder.terminate(
            SubroutineReturn(
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
        return TemplateVar(
            name=expr.name,
            ir_type=wtype_to_ir_type(expr.wtype, expr.source_location),
            source_location=expr.source_location,
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
        elif isinstance(result, Op):
            self.context.block_builder.add(result)
        # If we get a Value (e.g. a Register or some such) it's something that's being
        # discarded effectively.
        # The frontend should have already warned about this

    def visit_uint64_augmented_assignment(
        self, statement: awst_nodes.UInt64AugmentedAssignment
    ) -> TStatement:
        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        expr = create_uint64_binary_op(statement.op, target_value, rhs, statement.source_location)

        handle_assignment(
            self.context,
            target=statement.target,
            value=expr,
            is_nested_update=False,
            assignment_location=statement.source_location,
        )

    def visit_biguint_augmented_assignment(
        self, statement: awst_nodes.BigUIntAugmentedAssignment
    ) -> TStatement:
        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        expr = create_biguint_binary_op(statement.op, target_value, rhs, statement.source_location)

        handle_assignment(
            self.context,
            target=statement.target,
            value=expr,
            is_nested_update=False,
            assignment_location=statement.source_location,
        )

    def visit_bytes_augmented_assignment(
        self, statement: awst_nodes.BytesAugmentedAssignment
    ) -> TStatement:
        if statement.target.wtype == wtypes.arc4_string_alias:
            value: ValueProvider = arc4.dynamic_array_concat_and_convert(
                self.context,
                wtypes.arc4_string_alias,
                statement.target,
                statement.value,
                statement.source_location,
            )
        else:
            target_value = self.visit_and_materialise_single(statement.target)
            rhs = self.visit_and_materialise_single(statement.value)
            value = create_bytes_binary_op(
                statement.op, target_value, rhs, statement.source_location
            )

        handle_assignment(
            self.context,
            target=statement.target,
            value=value,
            is_nested_update=False,
            assignment_location=statement.source_location,
        )

    def visit_enumeration(self, expr: awst_nodes.Enumeration) -> TStatement:
        raise CodeError("Nested enumeration is not currently supported", expr.source_location)

    def visit_reversed(self, expr: awst_nodes.Reversed) -> TExpression:
        raise CodeError("Reversed is not valid outside of an enumeration", expr.source_location)

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> TStatement:
        handle_for_in_loop(self.context, statement)

    def visit_new_struct(self, expr: awst_nodes.NewStruct) -> TExpression:
        match expr.wtype:
            case wtypes.WStructType():
                raise NotImplementedError
            case wtypes.ARC4Struct() as arc4_struct_wtype:
                return arc4.encode_arc4_struct(self.context, expr, arc4_struct_wtype)
            case _:
                typing.assert_never(expr.wtype)

    def visit_array_pop(self, expr: awst_nodes.ArrayPop) -> TExpression:
        loc = expr.source_location
        if isinstance(expr.base.wtype, wtypes.ARC4DynamicArray):
            return arc4.pop_arc4_array(self.context, expr, expr.base.wtype)
        elif isinstance(expr.base.wtype, wtypes.ReferenceArray):
            slot = self.context.visitor.visit_and_materialise_single(expr.base)
            contents = mem.read_slot(self.context, slot, expr.base.source_location)
            contents, popped_item = arrays.pop_array(self.context, contents, expr.source_location)
            self.context.add_op(
                WriteSlot(
                    slot=slot,
                    value=contents,
                    source_location=expr.source_location,
                )
            )
            return popped_item
        else:
            raise InternalError(f"Unsupported target for array pop: {expr.base.wtype}", loc)

    def visit_array_replace(self, expr: awst_nodes.ArrayReplace) -> TExpression:
        arc4_wtype = effective_array_encoding(expr.wtype, expr.source_location)
        value = self.context.visitor.visit_expr(expr.value)
        if arc4_wtype.element_type == expr.value.wtype:
            arc4_value = value
        else:
            arc4_value = arc4.encode_value_provider(
                self.context,
                value,
                expr.value.wtype,
                arc4_wtype.element_type,
                expr.source_location,
            )
        return arc4.arc4_replace_array_item(
            self.context,
            base_expr=expr.base,
            index_value_expr=expr.index,
            wtype=arc4_wtype,
            value=arc4_value,
            source_location=expr.source_location,
        )

    def visit_array_concat(self, expr: awst_nodes.ArrayConcat) -> TExpression:
        assert expr.left.wtype == expr.wtype, "AWST validation requires result type == left type"
        match expr.wtype:
            case wtypes.ARC4DynamicArray() as arc4_array_wtype:
                pass
            case wtypes.StackArray():
                arc4_array_wtype = effective_array_encoding(expr.wtype, expr.source_location)

        return arc4.dynamic_array_concat_and_convert(
            self.context,
            array_wtype=arc4_array_wtype,
            array_expr=expr.left,
            iter_expr=expr.right,
            source_location=expr.source_location,
        )

    def visit_array_extend(self, expr: awst_nodes.ArrayExtend) -> TExpression:
        if isinstance(expr.base.wtype, wtypes.ARC4DynamicArray):
            concat_result = arc4.dynamic_array_concat_and_convert(
                self.context,
                array_wtype=expr.base.wtype,
                array_expr=expr.base,
                iter_expr=expr.other,
                source_location=expr.source_location,
            )
            return arc4.handle_arc4_assign(
                self.context,
                target=expr.base,
                value=concat_result,
                is_nested_update=True,
                source_location=expr.source_location,
            )
        elif isinstance(expr.base.wtype, wtypes.ReferenceArray):
            # note: the order things are evaluated is important to be semantically correct
            # 1. base expr
            # 2. other expr
            # 3. read slot to get data
            # 4. concat
            # 5. write slot
            array_slot = self.context.visitor.visit_and_materialise_single(expr.base)
            array_slot_type = array_slot.ir_type
            assert isinstance(array_slot_type, SlotType)
            array_type = array_slot_type.contents
            assert isinstance(array_type, ArrayType)
            values = arrays.get_array_encoded_items(self.context, expr.other, array_type)
            array_contents = mem.read_slot(self.context, array_slot, expr.source_location)
            array_contents = arrays.concat_arrays(
                self.context, array_contents, values, expr.source_location
            )
            mem.write_slot(self.context, array_slot, array_contents, expr.source_location)
            return array_slot
        else:
            raise InternalError("unsupported array type for ArrayExtend", expr.source_location)

    def visit_array_length(self, expr: awst_nodes.ArrayLength) -> TExpression:
        array_or_slot = self.context.visitor.visit_and_materialise_single(expr.array)
        array_wtype = expr.array.wtype
        match array_wtype:
            case wtypes.ARC4Array():
                return arc4.get_arc4_array_length(array_wtype, array_or_slot, expr.source_location)
            case wtypes.StackArray() | wtypes.ReferenceArray():
                return arrays.get_array_length(
                    self.context, array_wtype, array_or_slot, expr.source_location
                )
            case _:
                raise InternalError(f"Unexpected array type {array_wtype}", expr.source_location)

    def visit_arc4_router(self, expr: awst_nodes.ARC4Router) -> TExpression:
        root = self.context.root
        if not isinstance(root, awst_nodes.Contract):
            raise CodeError(
                "cannot create ARC-4 router outside of a contract", expr.source_location
            )

        return InvokeSubroutine(
            target=self.context.routers[root.id],
            args=[],
            source_location=expr.source_location,
        )

    def visit_emit(self, expr: awst_nodes.Emit) -> TExpression:
        factory = OpFactory(self.context, expr.source_location)
        value = self.context.visitor.visit_and_materialise_single(expr.value)
        prefix = MethodConstant(value=expr.signature, source_location=expr.source_location)
        event = factory.concat(prefix, value, "event")

        self.context.block_builder.add(
            Intrinsic(
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

    def visit_and_materialise_single(
        self, expr: awst_nodes.Expression, temp_description: str = "tmp"
    ) -> Value:
        """Translate an AWST Expression into a single Value"""
        values = self.visit_and_materialise(expr, temp_description=temp_description)
        try:
            (value,) = values
        except ValueError as ex:
            raise InternalError(
                "visit_and_materialise_single should not be used when"
                f" an expression could be multi-valued, expression was: {expr}",
                expr.source_location,
            ) from ex
        return value

    def visit_and_materialise(
        self, expr: awst_nodes.Expression, temp_description: str | Sequence[str] = "tmp"
    ) -> Sequence[Value]:
        value_seq_or_provider = self._visit_and_check_for_double_eval(
            expr, materialise_as=temp_description
        )
        if value_seq_or_provider is None:
            raise InternalError(
                "No value produced by expression IR conversion", expr.source_location
            )
        return self.materialise_value_provider(value_seq_or_provider, description=temp_description)

    def visit_expr(self, expr: awst_nodes.Expression) -> ValueProvider:
        """Visit the expression and ensure result is not None"""
        value_seq_or_provider = self._visit_and_check_for_double_eval(expr)
        if value_seq_or_provider is None:
            raise InternalError(
                "No value produced by expression IR conversion", expr.source_location
            )
        return value_seq_or_provider

    def _visit_and_check_for_double_eval(
        self, expr: awst_nodes.Expression, *, materialise_as: str | Sequence[str] | None = None
    ) -> ValueProvider | None:
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
            if isinstance(result, ValueProvider) and not isinstance(result, ValueTuple | Value):
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
            values = self.materialise_value_provider(source, description=materialise_as)
            if len(values) == 1:
                (result,) = values
            else:
                result = ValueTuple(values=values, source_location=expr.source_location)
        self._visited_exprs[expr_id] = result
        return result

    def materialise_value_provider(
        self, provider: ValueProvider, description: str | Sequence[str]
    ) -> list[Value]:
        """
        Given a ValueProvider with arity of N, return a Value sequence of length N.

        Anything which is already a Value is passed through without change.

        Otherwise, the result is assigned to a temporary register, which is returned
        """
        if isinstance(provider, Value):
            return [provider]

        if isinstance(provider, ValueTuple):
            return list(provider.values)

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
        return list[Value](targets)


def create_uint64_binary_op(
    op: UInt64BinaryOperator, left: Value, right: Value, source_location: SourceLocation
) -> Intrinsic:
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
    return Intrinsic(op=avm_op, args=[left, right], source_location=source_location)


def create_biguint_binary_op(
    op: BigUIntBinaryOperator, left: Value, right: Value, source_location: SourceLocation
) -> Intrinsic:
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
    return Intrinsic(
        op=avm_op,
        args=[left, right],
        types=(PrimitiveIRType.biguint,),
        source_location=source_location,
    )


def create_bytes_binary_op(
    op: awst_nodes.BytesBinaryOperator, lhs: Value, rhs: Value, source_location: SourceLocation
) -> ValueProvider:
    match op:
        case awst_nodes.BytesBinaryOperator.add:
            return Intrinsic(
                op=AVMOp.concat,
                args=[lhs, rhs],
                source_location=source_location,
            )
        case awst_nodes.BytesBinaryOperator.bit_and:
            return Intrinsic(
                op=AVMOp.bitwise_and_bytes,
                args=[lhs, rhs],
                source_location=source_location,
            )
        case awst_nodes.BytesBinaryOperator.bit_or:
            return Intrinsic(
                op=AVMOp.bitwise_or_bytes,
                args=[lhs, rhs],
                source_location=source_location,
            )
        case awst_nodes.BytesBinaryOperator.bit_xor:
            return Intrinsic(
                op=AVMOp.bitwise_xor_bytes,
                args=[lhs, rhs],
                source_location=source_location,
            )
    raise InternalError("Unsupported BytesBinaryOperator: " + op)
