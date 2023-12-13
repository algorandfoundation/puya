import typing
from collections.abc import Sequence

import structlog

import puya.awst.visitors
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import (
    BigUIntBinaryOperator,
    UInt64BinaryOperator,
)
from puya.errors import CodeError, InternalError, TodoError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4, flow_control
from puya.ir.builder.assignment import handle_assignment, handle_assignment_expr
from puya.ir.builder.iteration import handle_for_in_loop
from puya.ir.builder.itxn import InnerTransactionBuilder
from puya.ir.builder.utils import (
    assign,
    assign_targets,
    format_tuple_index,
    mkblocks,
    mktemp,
)
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
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.types_ import (
    AVMBytesEncoding,
    bytes_enc_to_avm_bytes_enc,
    wtype_to_avm_type,
)
from puya.parse import SourceLocation

TExpression: typing.TypeAlias = ValueProvider | None
TStatement: typing.TypeAlias = None

logger = structlog.get_logger(__name__)


class FunctionIRBuilder(
    puya.awst.visitors.ExpressionVisitor[TExpression],
    puya.awst.visitors.StatementVisitor[TStatement],
):
    def __init__(
        self, context: IRBuildContext, function: awst_nodes.Function, subroutine: Subroutine
    ):
        self.context = context.for_function(function, subroutine, self)
        self._itxn = InnerTransactionBuilder(self.context)
        self._awst_temp_var_names = dict[awst_nodes.TemporaryVariable, str]()

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
                func_ctx.block_builder.maybe_add_implicit_subroutine_return()
            func_ctx.ssa.verify_complete()
            func_ctx.block_builder.validate_block_predecessors()
            result = list(func_ctx.block_builder.blocks)
            if not result[-1].terminated:
                raise CodeError(
                    "Expected a return statement",
                    function.body.body[-1].source_location
                    if function.body.body
                    else function.source_location,
                )
            subroutine.body = result
            subroutine.validate_with_ssa()

    def visit_copy(self, expr: puya.awst.nodes.Copy) -> TExpression:
        # For reference types, we need to clone the data
        # For value types, we can just visit the expression and the resulting read
        # will effectively be a copy
        match expr.value.wtype:
            case wtypes.ARC4Array() | wtypes.ARC4Struct():
                # Arc4 encoded types are value types
                return self.visit_and_materialise_single(expr.value)
        raise InternalError(
            f"Invalid source wtype for Copy {expr.value.wtype}", expr.source_location
        )

    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> TExpression:
        return arc4.decode_expr(self.context, expr)

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> TExpression:
        return arc4.encode_expr(self.context, expr)

    def visit_assignment_statement(self, stmt: awst_nodes.AssignmentStatement) -> TStatement:
        if not self._itxn.handle_inner_transaction_assignments(stmt):
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
                adjusted_int = int(str(expr.value).replace(".", ""))
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
        return UInt64Constant(value=int(expr.value), source_location=expr.source_location)

    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> BytesConstant:
        return BytesConstant(
            value=expr.value,
            encoding=bytes_enc_to_avm_bytes_enc(expr.encoding),
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
        if not (left.atype & right.atype):
            raise InternalError(
                "Numeric comparison between different numeric types", expr.source_location
            )
        if left.atype != AVMType.any:
            atype = left.atype
        elif right.atype != AVMType.any:
            atype = right.atype
        else:
            raise InternalError("Numeric comparison mapped to any type", expr.source_location)
        op_code = expr.operator.value
        if atype == AVMType.bytes:
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
        value_atype = wtype_to_avm_type(expr.wtype)
        value_tmp = mktemp(
            self.context,
            atype=value_atype,
            source_location=expr.source_location,
            description="maybe_value",
        )
        did_exist_tmp = mktemp(
            self.context,
            atype=AVMType.uint64,
            source_location=expr.source_location,
            description="maybe_value_did_exist",
        )
        maybe_value = self.visit_expr(expr.expr)
        assign_targets(
            self.context,
            source=maybe_value,
            targets=[value_tmp, did_exist_tmp],
            assignment_location=expr.source_location,
        )
        self.context.block_builder.add(
            Intrinsic(
                op=AVMOp.assert_,
                args=[did_exist_tmp],
                comment=expr.comment or "check value exists",
                source_location=expr.source_location,
            )
        )

        return value_tmp

    def visit_var_expression(self, expr: awst_nodes.VarExpression) -> TExpression:
        if isinstance(expr.wtype, wtypes.WTuple):
            return ValueTuple(
                source_location=expr.source_location,
                values=[
                    self.context.ssa.read_variable(
                        variable=format_tuple_index(expr.name, idx),
                        atype=wtype_to_avm_type(wt, expr.source_location),
                        block=self.context.block_builder.active_block,
                    )
                    for idx, wt in enumerate(expr.wtype.types)
                ],
            )
        atype = wtype_to_avm_type(expr)
        variable = self.context.ssa.read_variable(
            expr.name, atype, self.context.block_builder.active_block
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
                )

    def visit_create_inner_transaction(self, call: awst_nodes.CreateInnerTransaction) -> None:
        raise InternalError(
            "Inner transaction parameters can only be assigned to local variables",
            call.source_location,
        )

    def visit_submit_inner_transaction(
        self, submit: awst_nodes.SubmitInnerTransaction
    ) -> TExpression:
        self._itxn.handle_submit_inner_transaction(submit)
        return None

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
            try:
                # TODO: don't rely on a pure function's side effects (raising) for validation
                wtype_to_avm_type(item)
            except InternalError:
                raise CodeError(
                    "Nested tuples or other compound types are not supported yet",
                    item.source_location,
                ) from None
            items.append(self.visit_and_materialise_single(item))
        return ValueTuple(
            source_location=expr.source_location,
            values=items,
        )

    def visit_tuple_item_expression(self, expr: awst_nodes.TupleItemExpression) -> TExpression:
        tup = self.visit_and_materialise(expr.base)
        return tup[expr.index]

    def visit_field_expression(self, expr: awst_nodes.FieldExpression) -> TExpression:
        raise TodoError(expr.source_location, "TODO: IR building: visit_field_expression")

    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> TExpression:
        """Slices an enumerable type."""
        if isinstance(expr.wtype, wtypes.WTuple):
            values = list(self.visit_and_materialise(expr.base))
            start_i = extract_const_int(expr.begin_index)
            end_i = extract_const_int(expr.end_index)
            return ValueTuple(source_location=expr.source_location, values=values[start_i:end_i])
        elif expr.base.wtype == wtypes.bytes_wtype:
            base = self.visit_and_materialise_single(expr.base)
            if expr.begin_index is None and expr.end_index is None:
                return base

            if expr.begin_index is not None:
                start_value = self.visit_and_materialise_single(expr.begin_index)
            else:
                start_value = UInt64Constant(value=0, source_location=expr.source_location)

            if expr.end_index is not None:
                stop_value = self.visit_and_materialise_single(expr.end_index)
                return Intrinsic(
                    op=AVMOp.substring3,
                    args=[base, start_value, stop_value],
                    source_location=expr.source_location,
                )
            elif isinstance(start_value, UInt64Constant):
                # we can use extract without computing the length when the start index is
                # a constant value and the end index is None (ie end of array)
                return Intrinsic(
                    op=AVMOp.extract,
                    immediates=[start_value.value, 0],
                    args=[base],
                    source_location=expr.source_location,
                )
            else:
                (base_length,) = assign(
                    self.context,
                    source_location=expr.source_location,
                    source=Intrinsic(
                        op=AVMOp.len_, args=[base], source_location=expr.source_location
                    ),
                    temp_description="base_length",
                )
                return Intrinsic(
                    op=AVMOp.substring3,
                    args=[base, start_value, base_length],
                    source_location=expr.source_location,
                )
        else:
            raise TodoError(expr.source_location, f"TODO: IR Slice {expr.wtype}")

    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> TExpression:
        index = self.visit_and_materialise_single(expr.index)
        base = self.visit_and_materialise_single(expr.base)

        if expr.index.wtype != wtypes.uint64_wtype:
            raise CodeError(
                f"Only {wtypes.uint64_wtype} indexes are supported", expr.index.source_location
            )
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
        elif value_provider := arc4.maybe_arc4_index_expr(self.context, expr, base, index):
            return value_provider
        else:
            raise CodeError(f"Indexing {expr.base.wtype} is not support", expr.source_location)

    def visit_conditional_expression(self, expr: awst_nodes.ConditionalExpression) -> TExpression:
        return flow_control.handle_conditional_expression(self.context, expr)

    def visit_temporary_variable(self, expr: awst_nodes.TemporaryVariable) -> TExpression:
        tmp_name = self.context.get_awst_tmp_name(expr)
        if not isinstance(expr.wtype, wtypes.WTuple):
            atype = wtype_to_avm_type(expr)
            return self.context.ssa.read_variable(
                tmp_name, atype, self.context.block_builder.active_block
            )
        else:
            registers: list[Value] = [
                self.context.ssa.read_variable(
                    format_tuple_index(tmp_name, idx),
                    wtype_to_avm_type(t),
                    self.context.block_builder.active_block,
                )
                for idx, t in enumerate(expr.wtype.types)
            ]
            return ValueTuple(expr.source_location, registers)

    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> TExpression:
        # TODO: add specific (unsafe) optimisation flag to allow skipping this check
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        # TODO: keep encoding? modify AWST to add source location for key?
        key = BytesConstant(
            value=expr.key,
            source_location=expr.source_location,
            encoding=bytes_enc_to_avm_bytes_enc(expr.key_encoding),
        )

        # note: we manually construct temporary targets here since atype is any,
        #       but we "know" the type from the expression
        value_atype = wtype_to_avm_type(expr.wtype)
        value_tmp = mktemp(
            self.context,
            atype=value_atype,
            source_location=expr.source_location,
            description="app_global_get_ex_value",
        )
        did_exist_tmp = mktemp(
            self.context,
            atype=AVMType.uint64,
            source_location=expr.source_location,
            description="app_global_get_ex_did_exist",
        )
        assign_targets(
            self.context,
            source=Intrinsic(
                op=AVMOp.app_global_get_ex,
                args=[current_app_offset, key],
                source_location=expr.source_location,
            ),
            targets=[value_tmp, did_exist_tmp],
            assignment_location=expr.source_location,
        )
        self.context.block_builder.add(
            Intrinsic(
                op=AVMOp.assert_,
                args=[did_exist_tmp],
                comment="check value exists",  # TODO: add field name here
                source_location=expr.source_location,
            )
        )

        return value_tmp

    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> TExpression:
        account = self.visit_and_materialise_single(expr.account)

        # TODO: add specific (unsafe) optimisation flag to allow skipping this check
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        # TODO: keep encoding? modify AWST to add source location for key?
        key = BytesConstant(
            value=expr.key,
            source_location=expr.source_location,
            encoding=bytes_enc_to_avm_bytes_enc(expr.key_encoding),
        )

        # note: we manually construct temporary targets here since atype is any,
        #       but we "know" the type from the expression
        value_tmp = mktemp(
            self.context,
            atype=wtype_to_avm_type(expr.wtype),
            source_location=expr.source_location,
            description="app_local_get_ex_value",
        )
        did_exist_tmp = mktemp(
            self.context,
            atype=AVMType.uint64,
            source_location=expr.source_location,
            description="app_local_get_ex_did_exist",
        )
        assign_targets(
            self.context,
            source=Intrinsic(
                op=AVMOp.app_local_get_ex,
                args=[account, current_app_offset, key],
                source_location=expr.source_location,
            ),
            targets=[value_tmp, did_exist_tmp],
            assignment_location=expr.source_location,
        )
        self.context.block_builder.add(
            Intrinsic(
                op=AVMOp.assert_,
                args=[did_exist_tmp],
                comment="check value exists",  # TODO: add field name here
                source_location=expr.source_location,
            )
        )
        return value_tmp

    def visit_new_array(self, expr: awst_nodes.NewArray) -> TExpression:
        raise TodoError(expr.source_location, "TODO: visit_new_array")

    def visit_arc4_array_encode(self, expr: awst_nodes.ARC4ArrayEncode) -> TExpression:
        return arc4.encode_arc4_array(self.context, expr)

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
        sref = self.context.resolve_function_reference(expr.target, expr.source_location)
        target = self.context.subroutines[sref]
        # TODO: what if args are multi-valued?
        args_expanded = list[tuple[str | None, Value]]()
        for expr_arg in expr.args:
            if not isinstance(expr_arg.value.wtype, wtypes.WTuple):
                arg = self.visit_and_materialise_single(expr_arg.value)
                args_expanded.append((expr_arg.name, arg))
            else:
                tup_args = self.visit_and_materialise(expr_arg.value)
                for tup_idx, tup_arg in enumerate(tup_args):
                    if expr_arg.name is None:
                        tup_name: str | None = None
                    else:
                        tup_name = format_tuple_index(expr_arg.name, tup_idx)
                    args_expanded.append((tup_name, tup_arg))
        target_name_to_index = {par.name: idx for idx, par in enumerate(target.parameters)}
        resolved_args = [val for name, val in args_expanded]
        for name, val in args_expanded:
            if name is not None:
                name_idx = target_name_to_index[name]
                resolved_args[name_idx] = val
        return InvokeSubroutine(
            source_location=expr.source_location, args=resolved_args, target=target
        )

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
                UInt64Constant(value=1, source_location=None),
                names=[(tmp_name, None)],
                source_location=None,
            )
            self.context.block_builder.goto(merge_block)

            self.context.block_builder.activate_block(false_block)
            assign(
                self.context,
                UInt64Constant(value=0, source_location=None),
                names=[(tmp_name, None)],
                source_location=None,
            )
            self.context.block_builder.goto_and_activate(merge_block)
            self.context.ssa.seal_block(merge_block)
            return self.context.ssa.read_variable(
                variable=tmp_name, atype=AVMType.uint64, block=merge_block
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
            raise TodoError(
                expr.source_location,
                "TODO: IR building: visit_contains_expression handle non tuple contains",
            )
        items_sequence = [
            item
            for item, item_wtype in zip(
                self.visit_and_materialise(expr.sequence), expr.sequence.wtype.types
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
        inner_avm_type = wtype_to_avm_type(expr.expr)
        outer_avm_type = wtype_to_avm_type(expr)
        if inner_avm_type != outer_avm_type:
            raise InternalError(
                f"Tried to reinterpret {expr.expr.wtype} as {expr.wtype},"
                " but resulting AVM types are incompatible:"
                f" {inner_avm_type} and {outer_avm_type}, respectively",
                expr.source_location,
            )
        return expr.expr.accept(self)

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
        return_types = [r.atype for r in result]
        if not (
            len(return_types) == len(self.context.subroutine.returns)
            and all(
                a & b for a, b in zip(return_types, self.context.subroutine.returns, strict=True)
            )
        ):
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
                    or wtypes.is_inner_transaction_params_type(wtype)
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
                self.context.errors.warning(
                    "assertion is always true, ignoring", statement.source_location
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
        raise TodoError(expr.source_location, "TODO: visit_new_struct")

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


def extract_const_int(expr: awst_nodes.Expression | None) -> int | None:
    """Check expr is an IntegerConstant or None, and return constant value (or None)"""
    match expr:
        case None:
            return None
        case awst_nodes.IntegerConstant(value=value):
            return value
        case _:
            raise InternalError(
                f"Expected either constant or None for index, got {type(expr).__name__}",
                expr.source_location,
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
