import typing
from collections.abc import Sequence

import puya.awst.visitors
from puya import log
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import BigUIntBinaryOperator, UInt64BinaryOperator
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4, flow_control, state
from puya.ir.builder._utils import (
    assert_value,
    assign,
    assign_targets,
    extract_const_int,
    mkblocks,
    mktemp,
)
from puya.ir.builder.assignment import handle_assignment, handle_assignment_expr
from puya.ir.builder.bytes import (
    visit_bytes_intersection_slice_expression,
    visit_bytes_slice_expression,
)
from puya.ir.builder.callsub import visit_subroutine_call_expression
from puya.ir.builder.iteration import handle_for_in_loop
from puya.ir.builder.itxn import InnerTransactionBuilder
from puya.ir.context import IRBuildContext, IRFunctionBuildContext
from puya.ir.models import (
    AddressConstant,
    BigUIntConstant,
    BytesConstant,
    ConditionalBranch,
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
)
from puya.ir.types_ import (
    AVMBytesEncoding,
    IRType,
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
        self._single_eval_registers = dict[awst_nodes.SingleEvaluation, TExpression]()

    @classmethod
    def build_body(
        cls,
        ctx: IRBuildContext,
        function: awst_nodes.Function,
        subroutine: Subroutine,
        on_create: Subroutine | None,
    ) -> None:
        builder = cls(ctx, function, subroutine)
        func_ctx = builder.context
        with func_ctx.log_exceptions():
            if on_create is not None:
                insert_on_create_call(func_ctx, to=on_create)
            function.body.accept(builder)
            if function.return_type == wtypes.void_wtype:
                func_ctx.block_builder.maybe_add_implicit_subroutine_return(subroutine.parameters)
            func_ctx.ssa.verify_complete()
            func_ctx.block_builder.validate_block_predecessors()
            result = list(func_ctx.block_builder.blocks)
            if not result[-1].terminated:
                raise CodeError(
                    "Expected a return statement",
                    (
                        function.body.body[-1].source_location
                        if function.body.body
                        else function.source_location
                    ),
                )
            subroutine.body = result
            subroutine.validate_with_ssa()

    def visit_copy(self, expr: puya.awst.nodes.Copy) -> TExpression:
        # For reference types, we need to clone the data
        # For value types, we can just visit the expression and the resulting read
        # will effectively be a copy. We assign the copy to a new register in case it is
        # mutated.
        match expr.value.wtype:
            case wtypes.ARC4Type(immutable=False):
                # Arc4 encoded types are value types
                original_value = self.visit_and_materialise_single(expr.value)
                (copy,) = assign(
                    temp_description="copy",
                    source=original_value,
                    source_location=expr.source_location,
                    context=self.context,
                )
                return copy
        raise InternalError(
            f"Invalid source wtype for Copy {expr.value.wtype}", expr.source_location
        )

    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> TExpression:
        return arc4.decode_expr(self.context, expr)

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> TExpression:
        return arc4.encode_expr(self.context, expr)

    def visit_assignment_statement(self, stmt: awst_nodes.AssignmentStatement) -> TStatement:
        if self._itxn.handle_inner_transaction_field_assignments(stmt):  # noqa: SIM114
            pass
        elif self._itxn.handle_inner_transaction_submit_assignments(
            stmt.target, stmt.value, stmt.source_location
        ):
            pass
        else:
            handle_assignment_expr(
                self.context,
                target=stmt.target,
                value=stmt.value,
                assignment_location=stmt.source_location,
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
                return UInt64Constant(
                    value=expr.value,
                    source_location=expr.source_location,
                    teal_alias=expr.teal_alias,
                )
            case wtypes.biguint_wtype:
                return BigUIntConstant(value=expr.value, source_location=expr.source_location)
            case wtypes.ARC4UIntN(n=bit_size):
                num_bytes = bit_size // 8
                return BytesConstant(
                    source_location=expr.source_location,
                    encoding=AVMBytesEncoding.base16,
                    value=expr.value.to_bytes(num_bytes, "big", signed=False),
                )
            case _:
                raise InternalError(
                    f"Unhandled wtype {expr.wtype} for integer constant {expr.value}",
                    expr.source_location,
                )

    def visit_decimal_constant(self, expr: awst_nodes.DecimalConstant) -> TExpression:
        match expr.wtype:
            case wtypes.ARC4UFixedNxM(n=bit_size):
                num_bytes = bit_size // 8
                _, digits, _ = expr.value.as_tuple()
                adjusted_int = int("".join(map(str, digits)))
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
        return UInt64Constant(
            value=int(expr.value), ir_type=IRType.bool, source_location=expr.source_location
        )

    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> BytesConstant:
        return BytesConstant(
            value=expr.value,
            encoding=bytes_enc_to_avm_bytes_enc(expr.encoding),
            source_location=expr.source_location,
        )

    def visit_string_constant(self, expr: awst_nodes.StringConstant) -> BytesConstant:
        return BytesConstant(
            value=expr.value.encode("utf8"),
            encoding=AVMBytesEncoding.utf8,
            source_location=expr.source_location,
        )

    def visit_address_constant(self, expr: awst_nodes.AddressConstant) -> TExpression:
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
        value_with_check = self.visit_expr(expr.expr)
        value, check = assign(
            self.context,
            value_with_check,
            temp_description=("value", "check"),
            source_location=expr.source_location,
        )
        assert_value(
            self.context,
            check,
            comment=expr.comment,
            source_location=expr.source_location,
        )
        return value

    def visit_var_expression(self, expr: awst_nodes.VarExpression) -> TExpression:
        if isinstance(expr.wtype, wtypes.WTuple):
            return ValueTuple(
                source_location=expr.source_location,
                values=[
                    self.context.ssa.read_variable(
                        variable=format_tuple_index(expr.name, idx),
                        ir_type=wtype_to_ir_type(wt, expr.source_location),
                        block=self.context.block_builder.active_block,
                    )
                    for idx, wt in enumerate(expr.wtype.types)
                ],
            )
        ir_type = wtype_to_ir_type(expr)
        variable = self.context.ssa.read_variable(
            expr.name, ir_type, self.context.block_builder.active_block
        )
        return variable

    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> TExpression:
        match call.op_code:
            case "err":
                self.context.block_builder.terminate(
                    Fail(source_location=call.source_location, comment=None)
                )
                return None
            case "return":
                assert not call.immediates, f"return intrinsic had immediates: {call.immediates}"
                (arg_expr,) = call.stack_args
                exit_value = self.visit_and_materialise_single(arg_expr)
                self.context.block_builder.terminate(
                    ProgramExit(source_location=call.source_location, result=exit_value)
                )
                return None
            case _:
                args = [self.visit_and_materialise_single(arg) for arg in call.stack_args]
                return Intrinsic(
                    op=AVMOp(call.op_code),
                    source_location=call.source_location,
                    args=args,
                    immediates=list(call.immediates),
                    types=wtype_to_ir_types(call.wtype),
                )

    def visit_create_inner_transaction(self, call: awst_nodes.CreateInnerTransaction) -> None:
        # for semantic compatibility, this is an error, since we don't evaluate the args
        # here (there would be no point, if we hit this node on its own and not as part
        # of a submit or an assigment, it does nothing)
        logger.error(
            "statement has no effect, did you forget to submit?", location=call.source_location
        )

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

    def visit_method_constant(self, expr: puya.awst.nodes.MethodConstant) -> TExpression:
        return MethodConstant(value=expr.value, source_location=expr.source_location)

    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> TExpression:
        items = []
        for item in expr.items:
            # TODO: don't rely on a pure function's side effects (raising) for validation
            wtype_to_ir_type(item)
            items.append(self.visit_and_materialise_single(item))
        return ValueTuple(
            source_location=expr.source_location,
            values=items,
        )

    def visit_tuple_item_expression(self, expr: awst_nodes.TupleItemExpression) -> TExpression:
        if isinstance(expr.base.wtype, wtypes.WTuple):
            tup = self.visit_and_materialise(expr.base)
            return tup[expr.index]
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
        elif isinstance(expr.base.wtype, wtypes.ARC4Struct):  # noqa: RET506
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
        if isinstance(expr.wtype, wtypes.WTuple):
            values = list(self.visit_and_materialise(expr.base))
            start_i = extract_const_int(expr.begin_index)
            end_i = extract_const_int(expr.end_index)
            return ValueTuple(source_location=expr.source_location, values=values[start_i:end_i])
        elif expr.base.wtype == wtypes.bytes_wtype:
            return visit_bytes_intersection_slice_expression(self.context, expr)
        else:
            raise InternalError(
                f"IntersectionSlice operation IR lowering not implemented for {expr.wtype.name}",
                expr.source_location,
            )

    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> TExpression:
        """Slices an enumerable type."""
        if isinstance(expr.wtype, wtypes.WTuple):
            values = list(self.visit_and_materialise(expr.base))
            start_i = extract_const_int(expr.begin_index)
            end_i = extract_const_int(expr.end_index)
            return ValueTuple(source_location=expr.source_location, values=values[start_i:end_i])
        elif expr.base.wtype == wtypes.bytes_wtype:
            return visit_bytes_slice_expression(self.context, expr)
        else:
            raise InternalError(
                f"Slice operation IR lowering not implemented for {expr.wtype.name}",
                expr.source_location,
            )

    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> TExpression:
        index = self.visit_and_materialise_single(expr.index)
        base = self.visit_and_materialise_single(expr.base)

        if expr.base.wtype == wtypes.bytes_wtype:
            # note: the below works because Bytes is immutable, so this index expression
            # can never appear as an assignment target
            if isinstance(index, UInt64Constant):
                return Intrinsic(
                    op=AVMOp.extract,
                    args=[base],
                    immediates=[index.value, 1],
                    source_location=expr.source_location,
                )
            (index_plus_1,) = assign(
                self.context,
                Intrinsic(
                    op=AVMOp.add,
                    source_location=expr.source_location,
                    args=[
                        index,
                        UInt64Constant(value=1, source_location=expr.source_location),
                    ],
                ),
                temp_description="index_plus_1",
                source_location=expr.source_location,
            )
            return Intrinsic(
                op=AVMOp.substring3,
                args=[base, index, index_plus_1],
                source_location=expr.source_location,
            )
        elif isinstance(expr.base.wtype, wtypes.WArray):
            raise NotImplementedError
        elif isinstance(expr.base.wtype, wtypes.ARC4StaticArray | wtypes.ARC4DynamicArray):
            return arc4.arc4_array_index(
                self.context,
                array_wtype=expr.base.wtype,
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
            return self._single_eval_registers[expr]
        except KeyError:
            pass
        source = expr.source.accept(self)
        result: TExpression
        if source is None:
            result = None
        else:
            registers = assign(
                self.context,
                source=source,
                temp_description="awst_tmp",
                source_location=expr.source_location,
            )
            if len(registers) == 1:
                (result,) = registers
            else:
                result = ValueTuple(
                    values=list[Value](registers), source_location=expr.source_location
                )
        self._single_eval_registers[expr] = result
        return result

    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> TExpression:
        return state.visit_app_state_expression(self.context, expr)

    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> TExpression:
        return state.visit_app_account_state_expression(self.context, expr)

    def visit_state_get_ex(self, expr: awst_nodes.StateGetEx) -> TExpression:
        return state.visit_state_get_ex(self.context, expr)

    def visit_state_delete(self, statement: awst_nodes.StateDelete) -> TStatement:
        return state.visit_state_delete(self.context, statement)

    def visit_state_get(self, expr: awst_nodes.StateGet) -> TExpression:
        return state.visit_state_get(self.context, expr)

    def visit_state_exists(self, expr: awst_nodes.StateExists) -> TExpression:
        return state.visit_state_exists(self.context, expr)

    def visit_new_array(self, expr: awst_nodes.NewArray) -> TExpression:
        match expr.wtype:
            case wtypes.ARC4Array():
                return arc4.encode_arc4_array(self.context, expr)
            case wtypes.WArray():
                raise NotImplementedError
            case _:
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

        return Intrinsic(
            op=avm_op,
            args=[left, right],
            source_location=expr.source_location,
        )

    def visit_subroutine_call_expression(
        self, expr: awst_nodes.SubroutineCallExpression
    ) -> TExpression:
        return visit_subroutine_call_expression(self.context, expr)

    def visit_bytes_binary_operation(self, expr: awst_nodes.BytesBinaryOperation) -> TExpression:
        left = self.visit_and_materialise_single(expr.left)
        right = self.visit_and_materialise_single(expr.right)
        return create_bytes_binary_op(expr.op, left, right, expr.source_location)

    def visit_boolean_binary_operation(
        self, expr: awst_nodes.BooleanBinaryOperation
    ) -> TExpression:
        if not isinstance(expr.right, awst_nodes.VarExpression | awst_nodes.BoolConstant):
            true_block, false_block, merge_block = mkblocks(
                expr.source_location, "bool_true", "bool_false", "bool_merge"
            )

            flow_control.process_conditional(
                self.context, expr, true=true_block, false=false_block, loc=expr.source_location
            )
            self.context.ssa.seal_block(true_block)
            self.context.ssa.seal_block(false_block)

            tmp_name = self.context.next_tmp_name(f"{expr.op}_result")
            self.context.block_builder.activate_block(true_block)
            assign(
                self.context,
                UInt64Constant(value=1, ir_type=IRType.bool, source_location=None),
                names=[(tmp_name, None)],
                source_location=None,
            )
            self.context.block_builder.goto(merge_block)

            self.context.block_builder.activate_block(false_block)
            assign(
                self.context,
                UInt64Constant(value=0, ir_type=IRType.bool, source_location=None),
                names=[(tmp_name, None)],
                source_location=None,
            )
            self.context.block_builder.goto_and_activate(merge_block)
            self.context.ssa.seal_block(merge_block)
            return self.context.ssa.read_variable(
                variable=tmp_name, ir_type=IRType.bool, block=merge_block
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

    def visit_contains_expression(self, expr: awst_nodes.Contains) -> TExpression:
        item_register = self.visit_and_materialise_single(expr.item)

        if not isinstance(expr.sequence.wtype, wtypes.WTuple):
            raise InternalError(
                f"Containment operation IR lowering"
                f" not implemented for sequence type {expr.sequence.wtype.name}",
                expr.source_location,
            )
        items_sequence = [
            item
            for item, item_wtype in zip(
                self.visit_and_materialise(expr.sequence), expr.sequence.wtype.types, strict=True
            )
            if item_wtype == expr.item.wtype
        ]

        condition = None
        for item in items_sequence:
            equal_i = Intrinsic(
                op=get_comparison_op_for_wtype(awst_nodes.NumericComparison.eq, expr.item.wtype),
                args=[
                    item_register,
                    item,
                ],
                source_location=expr.source_location,
            )
            if not condition:
                condition = equal_i
                continue
            (left_var,) = assign(
                self.context,
                source=condition,
                temp_description="contains",
                source_location=expr.source_location,
            )
            (right_var,) = assign(
                self.context,
                source=equal_i,
                temp_description="is_equal",
                source_location=expr.source_location,
            )
            condition = Intrinsic(
                op=AVMOp.or_, args=[left_var, right_var], source_location=expr.source_location
            )

        return condition or UInt64Constant(source_location=expr.source_location, value=0)

    def visit_reinterpret_cast(self, expr: awst_nodes.ReinterpretCast) -> TExpression:
        # should be a no-op for us, but we validate the cast here too
        source = self.visit_expr(expr.expr)
        (inner_ir_type,) = source.types
        outer_ir_type = wtype_to_ir_type(expr)
        # don't need to do anything further if ir types are the same
        if inner_ir_type == outer_ir_type:
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
            source_location=expr.source_location,
            description=f"reinterpret_{outer_ir_type.name}",
        )
        assign_targets(
            self.context,
            source=source,
            targets=[target],
            assignment_location=expr.source_location,
        )
        return target

    def visit_block(self, block: awst_nodes.Block) -> TStatement:
        for stmt in block.body:
            stmt.accept(self)

    def visit_if_else(self, stmt: awst_nodes.IfElse) -> TStatement:
        flow_control.handle_if_else(self.context, stmt)

    def visit_switch(self, statement: awst_nodes.Switch) -> TStatement:
        flow_control.handle_switch(self.context, statement)

    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> TStatement:
        flow_control.handle_while_loop(self.context, statement)

    def visit_break_statement(self, statement: awst_nodes.BreakStatement) -> TStatement:
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
        if return_types != self.context.subroutine.returns:
            raise CodeError(
                f"Invalid return type {return_types} in {self.context.function.full_name},"
                f" should be {self.context.subroutine.returns}",
                statement.source_location,
            )
        self.context.block_builder.terminate(
            SubroutineReturn(
                source_location=statement.source_location,
                result=result,
            )
        )

    def visit_template_var(self, expr: puya.awst.nodes.TemplateVar) -> TExpression:
        return TemplateVar(
            name=expr.name,
            ir_type=wtype_to_ir_type(expr.wtype),
            source_location=expr.source_location,
        )

    def visit_continue_statement(self, statement: awst_nodes.ContinueStatement) -> TStatement:
        self.context.block_builder.loop_continue(statement.source_location)

    def visit_expression_statement(self, statement: awst_nodes.ExpressionStatement) -> TStatement:
        # NOTE: popping of ignored return values should happen at code gen time
        result = statement.expr.accept(self)
        if result is None:
            wtype = statement.expr.wtype
            match wtype:
                case wtypes.void_wtype:
                    pass
                case _ if (
                    wtypes.is_inner_transaction_type(wtype)
                    or wtypes.is_inner_transaction_field_type(wtype)
                    or wtypes.is_inner_transaction_tuple_type(wtype)
                ):
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

    def visit_assert_statement(self, statement: awst_nodes.AssertStatement) -> TStatement:
        condition_value = self.visit_and_materialise_single(statement.condition)
        if isinstance(condition_value, UInt64Constant):
            if condition_value.value:
                logger.warning(
                    "assertion is always true, ignoring", location=statement.source_location
                )
            else:
                self.context.block_builder.terminate(
                    Fail(source_location=statement.source_location, comment=statement.comment)
                )
            return
        self.context.block_builder.add(
            Intrinsic(
                op=AVMOp("assert"),
                source_location=statement.source_location,
                args=[condition_value],
                comment=statement.comment,
            )
        )

    def visit_uint64_augmented_assignment(
        self, statement: puya.awst.nodes.UInt64AugmentedAssignment
    ) -> TStatement:
        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        expr = create_uint64_binary_op(statement.op, target_value, rhs, statement.source_location)

        handle_assignment(
            self.context,
            target=statement.target,
            value=expr,
            assignment_location=statement.source_location,
        )

    def visit_biguint_augmented_assignment(
        self, statement: puya.awst.nodes.BigUIntAugmentedAssignment
    ) -> TStatement:
        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        expr = create_biguint_binary_op(statement.op, target_value, rhs, statement.source_location)

        handle_assignment(
            self.context,
            target=statement.target,
            value=expr,
            assignment_location=statement.source_location,
        )

    def visit_bytes_augmented_assignment(
        self, statement: awst_nodes.BytesAugmentedAssignment
    ) -> TStatement:
        target_value = self.visit_and_materialise_single(statement.target)
        rhs = self.visit_and_materialise_single(statement.value)
        expr = create_bytes_binary_op(statement.op, target_value, rhs, statement.source_location)

        handle_assignment(
            self.context,
            target=statement.target,
            value=expr,
            assignment_location=statement.source_location,
        )

    def visit_enumeration(self, expr: awst_nodes.Enumeration) -> TStatement:
        raise CodeError("Nested enumeration is not currently supported", expr.source_location)

    def visit_reversed(self, expr: puya.awst.nodes.Reversed) -> TExpression:
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

    def visit_array_pop(self, expr: puya.awst.nodes.ArrayPop) -> TExpression:
        source_location = expr.source_location
        match expr.base.wtype:
            case wtypes.ARC4DynamicArray() as array_wtype:
                return arc4.pop_arc4_array(self.context, expr, array_wtype)
            case _:
                raise InternalError(
                    f"Unsupported target for array pop: {expr.base.wtype}", source_location
                )

    def visit_array_concat(self, expr: puya.awst.nodes.ArrayConcat) -> TExpression:
        return arc4.concat_values(
            self.context,
            left=expr.left,
            right=expr.right,
            source_location=expr.source_location,
        )

    def visit_array_extend(self, expr: puya.awst.nodes.ArrayExtend) -> TExpression:
        return arc4.handle_arc4_assign(
            self.context,
            target=expr.base,
            value=arc4.concat_values(
                self.context,
                left=expr.base,
                right=expr.other,
                source_location=expr.source_location,
            ),
            source_location=expr.source_location,
        )

    def visit_and_materialise_single(self, expr: awst_nodes.Expression) -> Value:
        """Translate an AWST Expression into a single Value"""
        values = self.visit_and_materialise(expr)
        try:
            (value,) = values
        except ValueError as ex:
            raise InternalError(
                "_visit_and_materialise_single should not be used when"
                f" an expression could be multi-valued, expression was: {expr}",
                expr.source_location,
            ) from ex
        return value

    def visit_and_materialise(self, expr: awst_nodes.Expression) -> Sequence[Value]:
        value_provider = self.visit_expr(expr)
        return self.materialise_value_provider(value_provider, description="tmp")

    def visit_expr(self, expr: awst_nodes.Expression) -> ValueProvider:
        """Visit the expression and ensure result is not None"""
        value_seq_or_provider = expr.accept(self)
        if value_seq_or_provider is None:
            raise InternalError(
                "No value produced by expression IR conversion", expr.source_location
            )
        return value_seq_or_provider

    def materialise_value_provider(
        self, provider: ValueProvider, description: str
    ) -> Sequence[Value]:
        """
        Given a ValueProvider with arity of N, return a Value sequence of length N.

        Anything which is already a Value is passed through without change.

        Otherwise, the result is assigned to a temporary register, which is returned
        """
        if isinstance(provider, Value):
            return (provider,)

        if isinstance(provider, ValueTuple):
            return provider.values

        # TODO: should this be the source location of the site forcing materialisation?
        return assign(
            self.context,
            source=provider,
            temp_description=description,
            source_location=provider.source_location,
        )


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
    return Intrinsic(op=avm_op, args=[left, right], source_location=source_location)


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


def get_comparison_op_for_wtype(
    numeric_comparison_equivalent: awst_nodes.NumericComparison, wtype: wtypes.WType
) -> AVMOp:
    match wtype:
        case wtypes.biguint_wtype:
            return AVMOp("b" + numeric_comparison_equivalent)
        case wtypes.uint64_wtype:
            return AVMOp(numeric_comparison_equivalent)
        case wtypes.bytes_wtype:
            match numeric_comparison_equivalent:
                case awst_nodes.NumericComparison.eq:
                    return AVMOp.eq
                case awst_nodes.NumericComparison.ne:
                    return AVMOp.neq
    raise InternalError(
        f"Unsupported operation of {numeric_comparison_equivalent} on type of {wtype}"
    )


def insert_on_create_call(context: IRFunctionBuildContext, to: Subroutine) -> None:
    txn_app_id_intrinsic = Intrinsic(
        source_location=None, op=AVMOp("txn"), immediates=["ApplicationID"]
    )
    (app_id_r,) = assign(
        context,
        source=txn_app_id_intrinsic,
        temp_description="app_id",
        source_location=None,
    )
    on_create_block, entrypoint_block = mkblocks(
        to.source_location or context.function.source_location, "on_create", "entrypoint"
    )
    context.block_builder.terminate(
        ConditionalBranch(
            source_location=None,
            condition=app_id_r,
            zero=on_create_block,
            non_zero=entrypoint_block,
        )
    )
    context.ssa.seal_block(on_create_block)
    context.block_builder.activate_block(on_create_block)
    context.block_builder.add(InvokeSubroutine(source_location=None, target=to, args=[]))
    context.block_builder.goto_and_activate(entrypoint_block)
    context.ssa.seal_block(entrypoint_block)
