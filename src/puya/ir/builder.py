import itertools
import typing
from collections.abc import Iterator, Sequence

import structlog

import puya.awst.visitors
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import (
    BigUIntBinaryOperator,
    Expression,
    UInt64BinaryOperator,
)
from puya.errors import CodeError, InternalError, TodoError
from puya.ir.arc4_util import (
    determine_arc4_tuple_head_size,
    get_arc4_fixed_bit_size,
    is_arc4_dynamic_size,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.blocks_builder import BlocksBuilder
from puya.ir.context import IRBuildContext, IRFunctionBuildContext
from puya.ir.models import (
    AddressConstant,
    Assignment,
    BasicBlock,
    BigUIntConstant,
    BytesConstant,
    ConditionalBranch,
    Fail,
    GotoNth,
    Intrinsic,
    InvokeSubroutine,
    MethodConstant,
    Op,
    ProgramExit,
    Register,
    Subroutine,
    SubroutineReturn,
    Switch,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.ssa import BraunSSA
from puya.ir.types_ import (
    AVMBytesEncoding,
    bytes_enc_to_avm_bytes_enc,
    wtype_to_avm_type,
)
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes, lazy_setdefault

TExpression: typing.TypeAlias = ValueProvider | None
TStatement: typing.TypeAlias = None

logger = structlog.get_logger(__name__)

TMP_VAR_INDICATOR = "%"


class FunctionIRBuilder(
    puya.awst.visitors.ExpressionVisitor[TExpression],
    puya.awst.visitors.StatementVisitor[TStatement],
):
    def __init__(self, context: IRFunctionBuildContext):
        self.context = context
        self.block_builder = BlocksBuilder(context)
        self._tmp_counter = itertools.count()
        self._awst_temp_var_names = dict[awst_nodes.TemporaryVariable, str]()

    @property
    def ssa(self) -> BraunSSA:
        return self.block_builder.ssa

    def _seal(self, block: BasicBlock) -> None:
        self.ssa.seal_block(block)

    @classmethod
    def build_body(
        cls,
        context: IRBuildContext,
        subroutine: Subroutine,
        function: awst_nodes.Function,
        on_create: Subroutine | None,
    ) -> None:
        ctx = context.for_function(function=function, subroutine=subroutine)
        builder = cls(ctx)
        with ctx.log_exceptions():
            if on_create is not None:
                builder.insert_on_create_call(to=on_create)
            function.body.accept(builder)
            if function.return_type == wtypes.void_wtype:
                builder.block_builder.maybe_add_implicit_subroutine_return()
            builder.ssa.verify_complete()
            builder.block_builder.validate_block_predecessors()
            result = list(builder.block_builder.blocks)
            if not result[-1].terminated:
                raise CodeError(
                    "Expected a return statement",
                    function.body.body[-1].source_location
                    if function.body.body
                    else function.source_location,
                )
            subroutine.body = result
            subroutine.validate_with_ssa()

    def insert_on_create_call(self, to: Subroutine) -> None:
        txn_app_id_intrinsic = Intrinsic(
            source_location=None, op=AVMOp("txn"), immediates=["ApplicationID"]
        )
        (app_id_r,) = self.assign(
            source=txn_app_id_intrinsic, temp_description="app_id", source_location=None
        )
        on_create_block, entrypoint_block = mkblocks(
            to.source_location or self.context.function.source_location, "on_create", "entrypoint"
        )
        self.block_builder.terminate(
            ConditionalBranch(
                source_location=None,
                condition=app_id_r,
                zero=on_create_block,
                non_zero=entrypoint_block,
            )
        )
        self._seal(on_create_block)
        self.block_builder.activate_block(on_create_block)
        self.block_builder.add(InvokeSubroutine(source_location=None, target=to, args=[]))
        self.block_builder.goto_and_activate(entrypoint_block)
        self._seal(entrypoint_block)

    def _next_tmp_name(self, description: str) -> str:
        return f"{description}{TMP_VAR_INDICATOR}{next(self._tmp_counter)}"

    def _mktemp(
        self,
        atype: AVMType,
        source_location: SourceLocation | None,
        *,
        description: str,
    ) -> Register:
        register = self.ssa.new_register(
            name=self._next_tmp_name(description),
            atype=atype,
            location=source_location,
        )
        return register

    def _awst_tmp_name(self, tmp_var: awst_nodes.TemporaryVariable) -> str:
        """
        Returns a unique and consistent name for a given AWST TemporaryVariable node.
        """
        try:
            return self._awst_temp_var_names[tmp_var]
        except KeyError:
            pass
        name = self._next_tmp_name("awst_tmp")
        self._awst_temp_var_names[tmp_var] = name
        return name

    def _visit_and_materialise_single(self, expr: awst_nodes.Expression) -> Value:
        """Translate an AWST Expression into a single Value"""
        values = self._visit_and_materialise(expr)
        try:
            (value,) = values
        except ValueError as ex:
            raise InternalError(
                "_visit_and_materialise_single should not be used when"
                f" an expression could be multi-valued, expression was: {expr}",
                expr.source_location,
            ) from ex
        return value

    def _visit_and_materialise(self, expr: awst_nodes.Expression) -> Sequence[Value]:
        value_provider = self._visit_expr(expr)
        return self._materialise_value_provider(value_provider, description="tmp")

    def _visit_expr(self, expr: awst_nodes.Expression) -> ValueProvider:
        """Visit the expression and ensure result is not None"""
        value_seq_or_provider = expr.accept(self)
        if value_seq_or_provider is None:
            raise InternalError(
                "No value produced by expression IR conversion", expr.source_location
            )
        return value_seq_or_provider

    def _materialise_value_provider(
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
        return self.assign(
            source=provider, temp_description=description, source_location=provider.source_location
        )

    def assign(
        self,
        source: ValueProvider,
        *,
        names: Sequence[tuple[str, SourceLocation | None]] | None = None,
        temp_description: str | None = None,
        source_location: SourceLocation | None,
    ) -> Sequence[Register]:
        atypes = source.types
        if not atypes:
            raise InternalError(
                "Attempted to assign from expression that has no result", source_location
            )

        if temp_description is not None:
            assert (
                names is None
            ), "One and only one of names and temp_description should be supplied"
            targets = [
                self._mktemp(atype, source_location, description=temp_description)
                for atype in atypes
            ]
        else:
            assert (
                names is not None
            ), "One and only one of names and temp_description should be supplied"
            # non-temporary assignment, so in the case of a multi-valued returning source/provider,
            # names should either be a single value (ie a tuple var name),
            # or it should match the length (ie unpack the tuple)
            if len(names) != len(atypes):
                try:
                    ((name, var_loc),) = names
                except ValueError as ex:
                    raise InternalError(
                        "Incompatible multi-assignment lengths", source_location
                    ) from ex
                names = [(format_tuple_index(name, idx), var_loc) for idx, _ in enumerate(atypes)]
            targets = [
                self.ssa.new_register(name, atype, var_loc)
                for (name, var_loc), atype in zip(names, atypes, strict=True)
            ]

        self._assign_targets(
            source=source,
            targets=targets,
            assignment_location=source_location,
        )

        return targets

    def _reassign(
        self, reg: Register, source: ValueProvider, source_location: SourceLocation | None
    ) -> Register:
        (updated,) = self.assign(
            source=source,
            names=[(reg.name, reg.source_location)],
            source_location=source_location,
        )
        return updated

    def _assign_targets(
        self,
        source: ValueProvider,
        targets: list[Register],
        assignment_location: SourceLocation | None,
    ) -> None:
        for target in targets:
            self.ssa.write_variable(target.name, self.block_builder.active_block, target)
        self.block_builder.add(
            Assignment(targets=targets, source=source, source_location=assignment_location)
        )

    def _refresh_mutated_variable(self, reg: Register) -> Register:
        """
        Given a register pointing to an underlying root operand (ie name) that is mutated,
        do an SSA read in the current block.

        This is *only* required when there is control flow involved in the generated IR,
        if it's only the builder that needs to loop then it should usually have an updated
        reference to the most recent assigned register which will still be valid because it's
        within the same block.
        """
        return self.ssa.read_variable(reg.name, reg.atype, self.block_builder.active_block)

    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> TExpression:
        value = self._visit_and_materialise_single(expr.value)
        match expr.value.wtype:
            case wtypes.ARC4UIntN(n=scale) | wtypes.ARC4UFixedNxM(n=scale):
                if scale > 64:
                    return value
                else:
                    return Intrinsic(
                        op=AVMOp.btoi,
                        args=[value],
                        source_location=expr.source_location,
                    )
            case wtypes.arc4_bool_wtype:
                return Intrinsic(
                    op=AVMOp.getbit,
                    args=[value, UInt64Constant(value=0, source_location=None)],
                    source_location=expr.source_location,
                )
            case wtypes.arc4_string_wtype:
                return Intrinsic(
                    op=AVMOp.extract,
                    immediates=[2, 0],
                    args=[value],
                    source_location=expr.source_location,
                )
            case wtypes.ARC4Tuple() as arc4_tuple:
                return self._visit_arc4_tuple_decode(
                    arc4_tuple, value, source_location=expr.source_location
                )
            case _:
                raise InternalError(
                    f"Unsupported wtype for ARC4Decode: {expr.value.wtype}",
                    location=expr.source_location,
                )

    def _visit_arc4_tuple_decode(
        self,
        wtype: wtypes.ARC4Tuple | wtypes.ARC4Struct,
        value: Value,
        source_location: SourceLocation,
    ) -> ValueProvider:
        items = list[Value]()

        for index in range(len(wtype.types)):
            index_const = UInt64Constant(value=index, source_location=source_location)
            item_value = self._read_nth_item_of_arc4_heterogeneous_container(
                array_bytes_sans_length_header=value,
                tuple_type=wtype,
                index=index_const,
                source_location=source_location,
            )
            (item,) = self.assign(
                temp_description=f"item{index}",
                source=item_value,
                source_location=source_location,
            )

            items.append(item)
        return ValueTuple(source_location=source_location, values=items)

    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> TExpression:
        match expr.wtype:
            case wtypes.arc4_bool_wtype:
                value = self._visit_and_materialise_single(expr.value)
                return encode_arc4_bool(value, expr.source_location)
            case wtypes.ARC4UIntN() | wtypes.ARC4UFixedNxM() as wt:
                value = self._visit_and_materialise_single(expr.value)
                num_bytes = wt.n // 8
                return self._itob_fixed(value, num_bytes, expr.source_location)
            case wtypes.ARC4Tuple(types=item_types) | wtypes.ARC4Struct(types=item_types):
                return self._visit_arc4_tuple_encode(expr, item_types)
            case wtypes.arc4_string_wtype:
                if isinstance(expr.value, awst_nodes.BytesConstant):
                    ir_const = self.visit_bytes_constant(expr.value)
                    prefix = len(ir_const.value).to_bytes(2, "big")
                    value_prefixed = prefix + ir_const.value
                    return BytesConstant(
                        source_location=expr.source_location,
                        value=value_prefixed,
                        encoding=ir_const.encoding,
                    )
                value = self._visit_and_materialise_single(expr.value)
                (length,) = self.assign(
                    temp_description="length",
                    source_location=expr.source_location,
                    source=Intrinsic(
                        op=AVMOp.len_,
                        args=[value],
                        source_location=expr.source_location,
                    ),
                )
                return Intrinsic(
                    op=AVMOp.concat,
                    args=[self._value_as_uint16(length), value],
                    source_location=expr.source_location,
                )
            case wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray():
                raise InternalError(
                    "ARC4ArrayEncode should be used instead of ARC4Encode for arrays",
                    expr.source_location,
                )
            case _:
                raise InternalError(
                    f"Unsupported wtype for ARC4Encode: {expr.wtype}",
                    location=expr.source_location,
                )

    def _itob_fixed(
        self, value: Value, num_bytes: int, source_location: SourceLocation
    ) -> ValueProvider:
        if value.atype == AVMType.uint64:
            (val_as_bytes,) = self.assign(
                temp_description="val_as_bytes",
                source=Intrinsic(op=AVMOp.itob, args=[value], source_location=source_location),
                source_location=source_location,
            )

            if num_bytes == 8:
                return val_as_bytes
            if num_bytes < 8:
                return Intrinsic(
                    op=AVMOp.extract,
                    immediates=[8 - num_bytes, num_bytes],
                    args=[val_as_bytes],
                    source_location=source_location,
                )
            bytes_value: Value = val_as_bytes
        else:
            (len_,) = self.assign(
                temp_description="len_",
                source=Intrinsic(op=AVMOp.len_, args=[value], source_location=source_location),
                source_location=source_location,
            )
            (no_overflow,) = self.assign(
                temp_description="no_overflow",
                source=Intrinsic(
                    op=AVMOp.lte,
                    args=[
                        len_,
                        UInt64Constant(value=num_bytes, source_location=source_location),
                    ],
                    source_location=source_location,
                ),
                source_location=source_location,
            )

            self.block_builder.add(
                Intrinsic(
                    op=AVMOp.assert_,
                    args=[no_overflow],
                    source_location=source_location,
                    comment="overflow",
                )
            )
            bytes_value = value

        (b_zeros,) = self.assign(
            temp_description="b_zeros",
            source=Intrinsic(
                op=AVMOp.bzero,
                args=[UInt64Constant(value=num_bytes, source_location=source_location)],
                source_location=source_location,
            ),
            source_location=source_location,
        )
        return Intrinsic(
            op=AVMOp.bitwise_or_bytes,
            args=[bytes_value, b_zeros],
            source_location=source_location,
        )

    def visit_assignment_statement(self, stmt: awst_nodes.AssignmentStatement) -> TStatement:
        self._handle_assignment_expr(
            target=stmt.target, value=stmt.value, assignment_location=stmt.source_location
        )
        return None

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> TExpression:
        result = self._handle_assignment_expr(
            target=expr.target, value=expr.value, assignment_location=expr.source_location
        )
        if not result:
            # HOW DID YOU GET HERE
            raise CodeError("Assignment expression did not return a result", expr.source_location)
        if len(result) == 1:
            return result[0]
        else:
            return ValueTuple(expr.source_location, list(result))

    def _handle_assignment_expr(
        self,
        target: awst_nodes.Expression,
        value: awst_nodes.Expression,
        assignment_location: SourceLocation,
    ) -> Sequence[Value]:
        expr_values = self._visit_expr(value)
        return self._handle_assignment(
            target=target, value=expr_values, assignment_location=assignment_location
        )

    def _handle_assignment(
        self,
        target: awst_nodes.Expression,
        value: ValueProvider,
        assignment_location: SourceLocation,
    ) -> Sequence[Value]:
        match target:
            case awst_nodes.VarExpression(name=var_name, source_location=var_loc):
                return self.assign(
                    source=value,
                    names=[(var_name, var_loc)],
                    source_location=assignment_location,
                )
            case awst_nodes.TemporaryVariable(source_location=var_loc) as tmp:
                tmp_name = self._awst_tmp_name(tmp)
                return self.assign(
                    source=value,
                    names=[(tmp_name, var_loc)],
                    source_location=assignment_location,
                )
            case awst_nodes.TupleExpression(items=items):
                source = self._materialise_value_provider(value, description="tuple_assignment")
                if len(source) != len(items):
                    raise CodeError("unpacking vs result length mismatch", assignment_location)
                return [
                    val
                    for dst, src in zip(items, source, strict=True)
                    for val in self._handle_assignment(
                        target=dst,
                        value=src,
                        assignment_location=assignment_location,
                    )
                ]
            case awst_nodes.AppStateExpression(
                key=app_state_key, source_location=key_loc, key_encoding=key_encoding
            ):
                source = self._materialise_value_provider(value, description="new_state_value")
                if len(source) != 1:
                    raise CodeError("Tuple state is not supported", assignment_location)
                self.block_builder.add(
                    Intrinsic(
                        op=AVMOp.app_global_put,
                        args=[
                            BytesConstant(
                                value=app_state_key,
                                source_location=key_loc,
                                encoding=bytes_enc_to_avm_bytes_enc(key_encoding),
                            ),
                            source[0],
                        ],
                        source_location=assignment_location,
                    )
                )
                return source
            case awst_nodes.AppAccountStateExpression(
                key=app_acct_state_key,
                account=account_expr,
                source_location=key_loc,
                key_encoding=key_encoding,
            ):
                source = self._materialise_value_provider(value, description="new_state_value")
                account = self._visit_and_materialise_single(account_expr)
                if len(source) != 1:
                    raise CodeError("Tuple state is not supported", assignment_location)
                self.block_builder.add(
                    Intrinsic(
                        op=AVMOp.app_local_put,
                        args=[
                            account,
                            BytesConstant(
                                value=app_acct_state_key,
                                source_location=key_loc,
                                encoding=bytes_enc_to_avm_bytes_enc(key_encoding),
                            ),
                            source[0],
                        ],
                        source_location=assignment_location,
                    )
                )
                return source
            case _:
                raise TodoError(
                    assignment_location,
                    "TODO: explicitly handle or reject assignment target type:"
                    f" {type(target).__name__}",
                )

    def visit_uint64_binary_operation(self, expr: awst_nodes.UInt64BinaryOperation) -> TExpression:
        left = self._visit_and_materialise_single(expr.left)
        right = self._visit_and_materialise_single(expr.right)
        return create_uint64_binary_op(expr.op, left, right, expr.source_location)

    def visit_biguint_binary_operation(
        self, expr: awst_nodes.BigUIntBinaryOperation
    ) -> TExpression:
        left = self._visit_and_materialise_single(expr.left)
        right = self._visit_and_materialise_single(expr.right)
        return create_biguint_binary_op(expr.op, left, right, expr.source_location)

    def visit_uint64_unary_operation(self, expr: awst_nodes.UInt64UnaryOperation) -> TExpression:
        return Intrinsic(
            op=AVMOp(expr.op),
            args=[self._visit_and_materialise_single(expr.expr)],
            source_location=expr.source_location,
        )

    def visit_bytes_unary_operation(self, expr: awst_nodes.BytesUnaryOperation) -> TExpression:
        return Intrinsic(
            op=AVMOp(f"b{expr.op}"),
            args=[self._visit_and_materialise_single(expr.expr)],
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
        left = self._visit_and_materialise_single(expr.lhs)
        right = self._visit_and_materialise_single(expr.rhs)
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
        value_tmp = self._mktemp(
            atype=value_atype,
            source_location=expr.source_location,
            description="maybe_value",
        )
        did_exist_tmp = self._mktemp(
            atype=AVMType.uint64,
            source_location=expr.source_location,
            description="maybe_value_did_exist",
        )
        maybe_value = self._visit_expr(expr.expr)
        self._assign_targets(
            source=maybe_value,
            targets=[value_tmp, did_exist_tmp],
            assignment_location=expr.source_location,
        )
        self.block_builder.add(
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
                    self.ssa.read_variable(
                        variable=format_tuple_index(expr.name, idx),
                        atype=wtype_to_avm_type(wt, expr.source_location),
                        block=self.block_builder.active_block,
                    )
                    for idx, wt in enumerate(expr.wtype.types)
                ],
            )
        atype = wtype_to_avm_type(expr)
        variable = self.ssa.read_variable(expr.name, atype, self.block_builder.active_block)
        return variable

    def visit_intrinsic_call(self, call: awst_nodes.IntrinsicCall) -> TExpression:
        match call.op_code:
            case "err":
                self.block_builder.terminate(
                    Fail(source_location=call.source_location, comment=None)
                )
                return None
            case "return":
                assert not call.immediates, f"return intrinsic had immediates: {call.immediates}"
                (arg_expr,) = call.stack_args
                exit_value = self._visit_and_materialise_single(arg_expr)
                self.block_builder.terminate(
                    ProgramExit(source_location=call.source_location, result=exit_value)
                )
                return None
            case _:
                args = [self._visit_and_materialise_single(arg) for arg in call.stack_args]
                return Intrinsic(
                    op=AVMOp(call.op_code),
                    source_location=call.source_location,
                    args=args,
                    immediates=list(call.immediates),
                )

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
            items.append(self._visit_and_materialise_single(item))
        return ValueTuple(
            source_location=expr.source_location,
            values=items,
        )

    def visit_tuple_item_expression(self, expr: awst_nodes.TupleItemExpression) -> TExpression:
        tup = self._visit_and_materialise(expr.base)
        return tup[expr.index]

    def visit_field_expression(self, expr: awst_nodes.FieldExpression) -> TExpression:
        raise TodoError(expr.source_location, "TODO: IR building: visit_field_expression")

    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> TExpression:
        """Slices an enumerable type."""
        if isinstance(expr.wtype, wtypes.WTuple):
            values = list(self._visit_and_materialise(expr.base))
            start_i = extract_const_int(expr.begin_index)
            end_i = extract_const_int(expr.end_index)
            return ValueTuple(source_location=expr.source_location, values=values[start_i:end_i])
        elif expr.base.wtype == wtypes.bytes_wtype:
            base = self._visit_and_materialise_single(expr.base)
            if expr.begin_index is None and expr.end_index is None:
                return base

            if expr.begin_index is not None:
                start_value = self._visit_and_materialise_single(expr.begin_index)
            else:
                start_value = UInt64Constant(value=0, source_location=expr.source_location)

            if expr.end_index is not None:
                stop_value = self._visit_and_materialise_single(expr.end_index)
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
                (base_length,) = self.assign(
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
        index = self._visit_and_materialise_single(expr.index)
        base = self._visit_and_materialise_single(expr.base)
        match expr.index.wtype, expr.base.wtype:
            case wtypes.uint64_wtype, wtypes.bytes_wtype:
                # note: the below works because Bytes is immutable, so this index expression
                # can never appear as an assignment target
                if isinstance(index, UInt64Constant):
                    return Intrinsic(
                        op=AVMOp.extract,
                        args=[base],
                        immediates=[index.value, 1],
                        source_location=expr.source_location,
                    )
                (index_plus_1,) = self.assign(
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
            case wtypes.uint64_wtype, wtypes.ARC4StaticArray(
                array_size=array_size, element_type=element_type
            ):
                self._assert_index_in_bounds(
                    index=index,
                    length=UInt64Constant(value=array_size, source_location=expr.source_location),
                    source_location=expr.source_location,
                )
                return self._read_nth_item_of_arc4_homogeneous_container(
                    source_location=expr.source_location,
                    array_bytes_sans_length_header=base,
                    index=index,
                    item_wtype=element_type,
                )
            case wtypes.uint64_wtype, wtypes.ARC4DynamicArray(element_type=element_type):
                self._assert_index_in_bounds(
                    index=index,
                    length=Intrinsic(
                        op=AVMOp.extract_uint16,
                        args=[
                            base,
                            UInt64Constant(value=0, source_location=expr.source_location),
                        ],
                        source_location=expr.source_location,
                    ),
                    source_location=expr.source_location,
                )
                (array_data_sans_header,) = self.assign(
                    source_location=expr.source_location,
                    temp_description="array_data_sans_header",
                    source=Intrinsic(
                        op=AVMOp.extract,
                        args=[base],
                        immediates=[2, 0],
                        source_location=expr.source_location,
                    ),
                )
                return self._read_nth_item_of_arc4_homogeneous_container(
                    source_location=expr.source_location,
                    array_bytes_sans_length_header=array_data_sans_header,
                    index=index,
                    item_wtype=element_type,
                )
            case wtypes.uint64_wtype, (wtypes.ARC4Tuple() | wtypes.ARC4Struct()) as tuple_type:
                if not isinstance(index, UInt64Constant):
                    raise InternalError("Tuples must be index with a constant value")
                return self._read_nth_item_of_arc4_heterogeneous_container(
                    source_location=expr.source_location,
                    array_bytes_sans_length_header=base,
                    index=index,
                    tuple_type=tuple_type,
                )

        raise TodoError(expr.source_location, "TODO: IR building: visit_index_expression")

    def _assert_index_in_bounds(
        self, index: Value, length: ValueProvider, source_location: SourceLocation
    ) -> None:
        if isinstance(index, UInt64Constant) and isinstance(length, UInt64Constant):
            if 0 <= index.value < length.value:
                return
            raise CodeError("Index access is out of bounds", source_location)

        (array_length,) = self.assign(
            source_location=source_location,
            temp_description="array_length",
            source=length,
        )

        (index_is_in_bounds,) = self.assign(
            source_location=source_location,
            temp_description="index_is_in_bounds",
            source=Intrinsic(
                op=AVMOp.lt,
                args=[index, array_length],
                source_location=source_location,
            ),
        )
        self.block_builder.add(
            Intrinsic(
                op=AVMOp.assert_,
                source_location=source_location,
                args=[index_is_in_bounds],
                comment="Index access is out of bounds",
            )
        )

    def visit_conditional_expression(self, expr: awst_nodes.ConditionalExpression) -> TExpression:
        # TODO: if expr.true_value and exr.false_value are var expressions,
        #       we can optimize with the `select` op

        true_block, false_block, merge_block = mkblocks(
            expr.source_location, "ternary_true", "ternary_false", "ternary_merge"
        )
        self._process_conditional(
            expr.condition,
            true=true_block,
            false=false_block,
            loc=expr.source_location,
        )
        self._seal(true_block)
        self._seal(false_block)

        tmp_var_name = self._next_tmp_name("ternary_result")

        self.block_builder.activate_block(true_block)
        true_vp = self._visit_expr(expr.true_expr)
        self.assign(
            source=true_vp,
            names=[(tmp_var_name, expr.true_expr.source_location)],
            source_location=expr.source_location,
        )
        self.block_builder.goto(merge_block)

        self.block_builder.activate_block(false_block)
        false_vp = self._visit_expr(expr.false_expr)
        self.assign(
            source=false_vp,
            names=[(tmp_var_name, expr.false_expr.source_location)],
            source_location=expr.source_location,
        )
        self.block_builder.goto_and_activate(merge_block)
        self._seal(merge_block)
        result = self.ssa.read_variable(
            variable=tmp_var_name, atype=wtype_to_avm_type(expr), block=merge_block
        )
        return result

    def visit_temporary_variable(self, expr: awst_nodes.TemporaryVariable) -> TExpression:
        tmp_name = self._awst_tmp_name(expr)
        if not isinstance(expr.wtype, wtypes.WTuple):
            atype = wtype_to_avm_type(expr)
            return self.ssa.read_variable(tmp_name, atype, self.block_builder.active_block)
        else:
            registers: list[Value] = [
                self.ssa.read_variable(
                    format_tuple_index(tmp_name, idx),
                    wtype_to_avm_type(t),
                    self.block_builder.active_block,
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
        value_tmp = self._mktemp(
            atype=value_atype,
            source_location=expr.source_location,
            description="app_global_get_ex_value",
        )
        did_exist_tmp = self._mktemp(
            atype=AVMType.uint64,
            source_location=expr.source_location,
            description="app_global_get_ex_did_exist",
        )
        self._assign_targets(
            source=Intrinsic(
                op=AVMOp.app_global_get_ex,
                args=[current_app_offset, key],
                source_location=expr.source_location,
            ),
            targets=[value_tmp, did_exist_tmp],
            assignment_location=expr.source_location,
        )
        self.block_builder.add(
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
        account = self._visit_and_materialise_single(expr.account)

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
        value_tmp = self._mktemp(
            atype=wtype_to_avm_type(expr.wtype),
            source_location=expr.source_location,
            description="app_local_get_ex_value",
        )
        did_exist_tmp = self._mktemp(
            atype=AVMType.uint64,
            source_location=expr.source_location,
            description="app_local_get_ex_did_exist",
        )
        self._assign_targets(
            source=Intrinsic(
                op=AVMOp.app_local_get_ex,
                args=[account, current_app_offset, key],
                source_location=expr.source_location,
            ),
            targets=[value_tmp, did_exist_tmp],
            assignment_location=expr.source_location,
        )
        self.block_builder.add(
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

    def _value_as_uint16(
        self, value: Value, source_location: SourceLocation | None = None
    ) -> Value:
        source_location = source_location or value.source_location
        (value_as_bytes,) = self.assign(
            source_location=source_location,
            source=Intrinsic(op=AVMOp.itob, args=[value], source_location=source_location),
            temp_description="value_as_bytes",
        )
        (value_as_uint16,) = self.assign(
            source_location=source_location,
            source=Intrinsic(
                op=AVMOp.extract,
                args=[value_as_bytes],
                immediates=[6, 2],
                source_location=source_location,
            ),
            temp_description="value_as_uint16",
        )
        return value_as_uint16

    def _visit_arc4_tuple_encode(
        self, expr: awst_nodes.ARC4Encode, tuple_items: Sequence[wtypes.WType]
    ) -> TExpression:
        elements = self._visit_and_materialise(expr.value)
        header_size = determine_arc4_tuple_head_size(tuple_items, round_end_result=True)
        expr_loc = expr.source_location

        (current_tail_offset,) = self.assign(
            temp_description="current_tail_offset",
            source=UInt64Constant(value=header_size // 8, source_location=expr_loc),
            source_location=expr_loc,
        )

        (encoded_tuple_buffer,) = self.assign(
            temp_description="encoded_tuple_buffer",
            source_location=expr_loc,
            source=BytesConstant(
                value=b"", encoding=AVMBytesEncoding.base16, source_location=expr_loc
            ),
        )

        def assign_buffer(source: ValueProvider) -> None:
            nonlocal encoded_tuple_buffer
            encoded_tuple_buffer = self._reassign(encoded_tuple_buffer, source, expr_loc)

        def append_to_buffer(item: Value) -> None:
            assign_buffer(
                Intrinsic(
                    op=AVMOp.concat, args=[encoded_tuple_buffer, item], source_location=expr_loc
                )
            )

        for index, (element, el_wtype) in enumerate(zip(elements, tuple_items)):
            if el_wtype == wtypes.arc4_bool_wtype:
                # Pack boolean
                before_header = determine_arc4_tuple_head_size(
                    tuple_items[0:index], round_end_result=False
                )
                if before_header % 8 == 0:
                    append_to_buffer(element)
                else:
                    (is_true,) = self.assign(
                        temp_description="is_true",
                        source=Intrinsic(
                            op=AVMOp.getbit,
                            args=[element, UInt64Constant(value=0, source_location=None)],
                            source_location=expr_loc,
                        ),
                        source_location=expr_loc,
                    )

                    assign_buffer(
                        Intrinsic(
                            op=AVMOp.setbit,
                            args=[
                                encoded_tuple_buffer,
                                UInt64Constant(value=before_header, source_location=expr_loc),
                                is_true,
                            ],
                            source_location=expr_loc,
                        )
                    )
            elif not is_arc4_dynamic_size(el_wtype):
                # Append value
                append_to_buffer(element)
            else:
                # Append pointer
                offset_as_uint16b = self._value_as_uint16(current_tail_offset)
                append_to_buffer(offset_as_uint16b)
                # Update Pointer
                (data_length,) = self.assign(
                    temp_description="data_length",
                    source=Intrinsic(op=AVMOp.len_, args=[element], source_location=expr_loc),
                    source_location=expr_loc,
                )
                next_tail_offset = Intrinsic(
                    op=AVMOp.add,
                    args=[current_tail_offset, data_length],
                    source_location=expr_loc,
                )
                current_tail_offset = self._reassign(
                    current_tail_offset, next_tail_offset, expr_loc
                )

        for element, el_wtype in zip(elements, tuple_items):
            if is_arc4_dynamic_size(el_wtype):
                append_to_buffer(element)
        return encoded_tuple_buffer

    def visit_arc4_array_encode(self, expr: awst_nodes.ARC4ArrayEncode) -> TExpression:
        len_prefix = (
            len(expr.values).to_bytes(2, "big")
            if isinstance(expr.wtype, wtypes.ARC4DynamicArray)
            else b""
        )

        expr_loc = expr.source_location
        if not expr.values:
            return BytesConstant(
                value=len_prefix, encoding=AVMBytesEncoding.base16, source_location=expr_loc
            )

        elements = [self._visit_and_materialise_single(value) for value in expr.values]
        element_type = expr.wtype.element_type

        (array_data,) = self.assign(
            temp_description="array_data",
            source=BytesConstant(
                value=len_prefix, encoding=AVMBytesEncoding.base16, source_location=expr_loc
            ),
            source_location=expr_loc,
        )
        if element_type == wtypes.arc4_bool_wtype:
            for index, el in enumerate(elements):
                if index % 8 == 0:
                    new_array_data_value = Intrinsic(
                        op=AVMOp.concat, args=[array_data, el], source_location=expr_loc
                    )
                else:
                    (is_true,) = self.assign(
                        temp_description="is_true",
                        source=Intrinsic(
                            op=AVMOp.getbit,
                            args=[el, UInt64Constant(value=0, source_location=None)],
                            source_location=expr_loc,
                        ),
                        source_location=expr_loc,
                    )
                    new_array_data_value = Intrinsic(
                        op=AVMOp.setbit,
                        args=[
                            array_data,
                            UInt64Constant(
                                value=index + (len(len_prefix) * 8),
                                source_location=expr_loc,
                            ),
                            is_true,
                        ],
                        source_location=expr_loc,
                    )
                array_data = self._reassign(array_data, new_array_data_value, expr_loc)

            return array_data

        if is_arc4_dynamic_size(element_type):
            (next_offset,) = self.assign(
                temp_description="next_offset",
                source=UInt64Constant(value=(2 * len(elements)), source_location=expr_loc),
                source_location=expr_loc,
            )
            for element in elements:
                updated_array_data = Intrinsic(
                    op=AVMOp.concat,
                    args=[array_data, self._value_as_uint16(next_offset)],
                    source_location=expr_loc,
                )
                array_data = self._reassign(array_data, updated_array_data, expr_loc)

                (element_length,) = self.assign(
                    temp_description="element_length",
                    source=Intrinsic(op=AVMOp.len_, args=[element], source_location=expr_loc),
                    source_location=expr_loc,
                )
                next_offset_value = Intrinsic(
                    op=AVMOp.add, args=[next_offset, element_length], source_location=expr_loc
                )
                next_offset = self._reassign(next_offset, next_offset_value, expr_loc)

        for element in elements:
            array_data_value = Intrinsic(
                op=AVMOp.concat, args=[array_data, element], source_location=expr_loc
            )
            array_data = self._reassign(array_data, array_data_value, expr_loc)
        return array_data

    def visit_bytes_comparison_expression(
        self, expr: awst_nodes.BytesComparisonExpression
    ) -> TExpression:
        left = self._visit_and_materialise_single(expr.lhs)
        right = self._visit_and_materialise_single(expr.rhs)
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
        sref = self.context.resolve_function_reference(expr)
        target = self.context.subroutines[sref]
        # TODO: what if args are multi-valued?
        args_expanded = list[tuple[str | None, Value]]()
        for expr_arg in expr.args:
            if not isinstance(expr_arg.value.wtype, wtypes.WTuple):
                arg = self._visit_and_materialise_single(expr_arg.value)
                args_expanded.append((expr_arg.name, arg))
            else:
                tup_args = self._visit_and_materialise(expr_arg.value)
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
        left = self._visit_and_materialise_single(expr.left)
        right = self._visit_and_materialise_single(expr.right)
        return create_bytes_binary_op(expr.op, left, right, expr.source_location)

    def visit_boolean_binary_operation(
        self, expr: awst_nodes.BooleanBinaryOperation
    ) -> TExpression:
        if not isinstance(expr.right, awst_nodes.VarExpression | awst_nodes.BoolConstant):
            true_block, false_block, merge_block = mkblocks(
                expr.source_location, "bool_true", "bool_false", "bool_merge"
            )

            self._process_conditional(
                expr, true=true_block, false=false_block, loc=expr.source_location
            )
            self._seal(true_block)
            self._seal(false_block)

            tmp_name = self._next_tmp_name(f"{expr.op}_result")
            self.block_builder.activate_block(true_block)
            self.assign(
                UInt64Constant(value=1, source_location=None),
                names=[(tmp_name, None)],
                source_location=None,
            )
            self.block_builder.goto(merge_block)

            self.block_builder.activate_block(false_block)
            self.assign(
                UInt64Constant(value=0, source_location=None),
                names=[(tmp_name, None)],
                source_location=None,
            )
            self.block_builder.goto_and_activate(merge_block)
            self._seal(merge_block)
            return self.ssa.read_variable(
                variable=tmp_name, atype=AVMType.uint64, block=merge_block
            )

        left = self._visit_and_materialise_single(expr.left)
        right = self._visit_and_materialise_single(expr.right)
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
        negated = self._visit_and_materialise_single(expr.expr)
        return Intrinsic(
            op=AVMOp("!"),
            args=[negated],
            source_location=expr.source_location,
        )

    def visit_contains_expression(self, expr: awst_nodes.Contains) -> TExpression:
        item_register = self._visit_and_materialise_single(expr.item)

        if not isinstance(expr.sequence.wtype, wtypes.WTuple):
            raise TodoError(
                expr.source_location,
                "TODO: IR building: visit_contains_expression handle non tuple contains",
            )
        items_sequence = [
            item
            for item, item_wtype in zip(
                self._visit_and_materialise(expr.sequence), expr.sequence.wtype.types
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
            (left_var,) = self.assign(
                source=condition, temp_description="contains", source_location=expr.source_location
            )
            (right_var,) = self.assign(
                source=equal_i, temp_description="is_equal", source_location=expr.source_location
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
        # else_body might be unused, if so won't be added, so all good
        if_body, else_body, next_block = mkblocks(
            stmt.source_location,
            stmt.if_branch.description or "if_body",
            (stmt.else_branch and stmt.else_branch.description) or "else_body",
            "after_if_else",
        )

        self._process_conditional(
            stmt.condition,
            true=if_body,
            false=else_body if stmt.else_branch else next_block,
            loc=stmt.source_location,
        )
        self._seal(if_body)
        self._seal(else_body)
        self._branch(
            ir_block=if_body,
            ast_block=stmt.if_branch,
            next_ir_block=next_block,
        )
        if stmt.else_branch:
            self._branch(
                ir_block=else_body,
                ast_block=stmt.else_branch,
                next_ir_block=next_block,
            )
        if next_block.predecessors:
            # Activate the "next" block if it is reachable.
            # This might not be the case if all paths within the "if" and "else" branches
            # return early.
            self.block_builder.activate_block(next_block)
        elif next_block.phis or next_block.ops or next_block.terminated:
            # here as a sanity - there shouldn't've been any modifications of "next" block contents
            raise InternalError("next block has no predecessors but does have op(s)")
        self._seal(next_block)

    def visit_switch(self, statement: awst_nodes.Switch) -> TStatement:
        case_blocks = dict[Value, BasicBlock]()
        ir_blocks = dict[awst_nodes.Block, BasicBlock]()
        for value, block in statement.cases.items():
            ir_value = self._visit_and_materialise_single(value)
            case_blocks[ir_value] = lazy_setdefault(
                ir_blocks,
                block,
                lambda b: BasicBlock(
                    source_location=b.source_location,
                    comment=b.description or f"switch_case_{len(ir_blocks)}",
                ),
            )
        default_block, next_block = mkblocks(
            statement.source_location,
            (statement.default_case and statement.default_case.description)
            or "switch_case_default",
            "switch_case_next",
        )

        self.block_builder.terminate(
            Switch(
                value=self._visit_and_materialise_single(statement.value),
                cases=case_blocks,
                default=default_block,
                source_location=statement.source_location,
            )
        )
        for ir_block in (default_block, *ir_blocks.values()):
            self._seal(ir_block)
        for block, ir_block in ir_blocks.items():
            self._branch(ir_block, block, next_block)
        if statement.default_case:
            self._branch(default_block, statement.default_case, next_block)
        else:
            self.block_builder.activate_block(default_block)
            self.block_builder.goto(next_block)
        if next_block.predecessors:
            # Activate the "next" block if it is reachable.
            # This might not be the case if all paths within the "if" and "else" branches
            # return early.
            self.block_builder.activate_block(next_block)
        elif next_block.phis or next_block.ops or next_block.terminated:
            # here as a sanity - there shouldn't've been any modifications of "next" block contents
            raise InternalError("next block has no predecessors but does have op(s)")
        self._seal(next_block)

    def _branch(
        self, ir_block: BasicBlock, ast_block: awst_nodes.Block, next_ir_block: BasicBlock
    ) -> None:
        self.block_builder.activate_block(ir_block)
        ast_block.accept(self)
        self.block_builder.goto(next_ir_block)

    def _process_conditional(
        self,
        expr: awst_nodes.Expression,
        *,
        true: BasicBlock,
        false: BasicBlock,
        loc: SourceLocation,
    ) -> None:
        if expr.wtype != wtypes.bool_wtype:
            raise InternalError(
                "_process_conditional should only be used for boolean conditionals", loc
            )
        match expr:
            case awst_nodes.BooleanBinaryOperation(
                op=bool_op, left=lhs, right=rhs, source_location=loc
            ):
                # Short circuit boolean binary operators in a conditional context.
                contd = BasicBlock(source_location=loc, comment=f"{bool_op}_contd")
                if bool_op == "and":
                    self._process_conditional(lhs, true=contd, false=false, loc=loc)
                elif bool_op == "or":
                    self._process_conditional(lhs, true=true, false=contd, loc=loc)
                else:
                    raise InternalError(
                        f"Unhandled boolean operator for short circuiting: {bool_op}", loc
                    )
                self._seal(contd)
                self.block_builder.activate_block(contd)
                self._process_conditional(rhs, true=true, false=false, loc=loc)
            case awst_nodes.Not(expr=expr, source_location=loc):
                self._process_conditional(expr, true=false, false=true, loc=loc)
            case _:
                condition_value = self._visit_and_materialise_single(expr)
                self.block_builder.terminate(
                    ConditionalBranch(
                        condition=condition_value,
                        non_zero=true,
                        zero=false,
                        source_location=loc,
                    )
                )

    def visit_while_loop(self, statement: awst_nodes.WhileLoop) -> TStatement:
        top, body, next_block = mkblocks(
            statement.source_location,
            "while_top",
            statement.loop_body.description or "while_body",
            "after_while",
        )

        with self.block_builder.enter_loop(on_continue=top, on_break=next_block):
            self.block_builder.goto_and_activate(top)
            self._process_conditional(
                statement.condition,
                true=body,
                false=next_block,
                loc=statement.source_location,
            )
            self._seal(body)

            self.block_builder.activate_block(body)
            statement.loop_body.accept(self)
            self.block_builder.goto(top)
        self._seal(top)
        self._seal(next_block)
        self.block_builder.activate_block(next_block)

    def visit_break_statement(self, statement: awst_nodes.BreakStatement) -> TStatement:
        self.block_builder.loop_break(statement.source_location)

    def visit_return_statement(self, statement: awst_nodes.ReturnStatement) -> TStatement:
        if statement.value is not None:
            result = list(self._visit_and_materialise(statement.value))
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
        self.block_builder.terminate(
            SubroutineReturn(
                source_location=statement.source_location,
                result=result,
            )
        )

    def visit_continue_statement(self, statement: awst_nodes.ContinueStatement) -> TStatement:
        self.block_builder.loop_continue(statement.source_location)

    def visit_expression_statement(self, statement: awst_nodes.ExpressionStatement) -> TStatement:
        # NOTE: popping of ignored return values should happen at code gen time
        result = statement.expr.accept(self)
        if result is None:
            if statement.expr.wtype != wtypes.void_wtype:
                raise InternalError(
                    f"Expression statement with type {statement.expr.wtype} generated no result",
                    statement.source_location,
                )
        elif isinstance(result, Op):
            self.block_builder.add(result)
        # If we get a Value (e.g. a Register or some such) it's something that's being
        # discarded effectively.
        # The frontend should have already warned about this

    def visit_assert_statement(self, statement: awst_nodes.AssertStatement) -> TStatement:
        condition_value = self._visit_and_materialise_single(statement.condition)
        if isinstance(condition_value, UInt64Constant):
            if condition_value.value:
                self.context.errors.warning(
                    "assertion is always true, ignoring", statement.source_location
                )
            else:
                self.block_builder.terminate(
                    Fail(source_location=statement.source_location, comment=statement.comment)
                )
            return
        self.block_builder.add(
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
        target_value = self._visit_and_materialise_single(statement.target)
        rhs = self._visit_and_materialise_single(statement.value)
        expr = create_uint64_binary_op(statement.op, target_value, rhs, statement.source_location)

        self._handle_assignment(
            target=statement.target,
            value=expr,
            assignment_location=statement.source_location,
        )

    def visit_biguint_augmented_assignment(
        self, statement: puya.awst.nodes.BigUIntAugmentedAssignment
    ) -> TStatement:
        target_value = self._visit_and_materialise_single(statement.target)
        rhs = self._visit_and_materialise_single(statement.value)
        expr = create_biguint_binary_op(statement.op, target_value, rhs, statement.source_location)

        self._handle_assignment(
            target=statement.target,
            value=expr,
            assignment_location=statement.source_location,
        )

    def visit_bytes_augmented_assignment(
        self, statement: awst_nodes.BytesAugmentedAssignment
    ) -> TStatement:
        target_value = self._visit_and_materialise_single(statement.target)
        rhs = self._visit_and_materialise_single(statement.value)
        expr = create_bytes_binary_op(statement.op, target_value, rhs, statement.source_location)

        self._handle_assignment(
            target=statement.target,
            value=expr,
            assignment_location=statement.source_location,
        )

    def visit_enumeration(self, expr: awst_nodes.Enumeration) -> TStatement:
        raise CodeError("Nested enumeration is not currently supported", expr.source_location)

    def visit_for_in_loop(self, statement: awst_nodes.ForInLoop) -> TStatement:
        if isinstance(statement.sequence, awst_nodes.Enumeration):
            if not (
                isinstance(statement.items, awst_nodes.TupleExpression)
                and len(statement.items.items) == 2
            ):
                # TODO: fix this
                raise CodeError(
                    "when using uenumerate(), loop variables must be an unpacked two item tuple",
                    statement.sequence.source_location,
                )
            index_var, item_var = statement.items.items
            sequence = statement.sequence.expr
        else:
            index_var = None
            item_var = statement.items
            sequence = statement.sequence

        match sequence:
            case awst_nodes.Range(
                start=range_start, stop=range_stop, step=range_step, source_location=range_loc
            ):
                self._iterate_urange(
                    loop_body=statement.loop_body,
                    item_var=item_var,
                    index_var=index_var,
                    statement_loc=statement.source_location,
                    range_start=range_start,
                    range_stop=range_stop,
                    range_step=range_step,
                    range_loc=range_loc,
                )
            case awst_nodes.Expression(wtype=wtypes.WTuple()) as tuple_expression:
                tuple_items = self._visit_and_materialise(tuple_expression)
                if not tuple_items:
                    logger.debug("Skipping ForInStatement which iterates an empty sequence.")
                else:
                    self._iterate_tuple(
                        loop_body=statement.loop_body,
                        item_var=item_var,
                        index_var=index_var,
                        tuple_items=tuple_items,
                        statement_loc=statement.source_location,
                    )
            case awst_nodes.Expression(wtype=wtypes.bytes_wtype) as bytes_expression:
                bytes_value = self._visit_and_materialise_single(bytes_expression)
                (byte_length,) = self.assign(
                    temp_description="bytes_length",
                    source=Intrinsic(
                        op=AVMOp.len_,
                        args=[bytes_value],
                        source_location=statement.source_location,
                    ),
                    source_location=statement.source_location,
                )

                def get_byte_at_index(index_register: Register) -> ValueProvider:
                    return Intrinsic(
                        op=AVMOp.extract3,
                        args=[
                            bytes_value,
                            index_register,
                            UInt64Constant(value=1, source_location=None),
                        ],
                        source_location=item_var.source_location,
                    )

                self._iterate_indexable(
                    loop_body=statement.loop_body,
                    indexable_size=byte_length,
                    get_value_at_index=get_byte_at_index,
                    item_var=item_var,
                    index_var=index_var,
                    statement_loc=statement.source_location,
                )
            case awst_nodes.Expression(
                wtype=wtypes.ARC4DynamicArray() as dynamic_array_wtype
            ) as arc4_dynamic_array_expression:
                array_value_with_length = self._visit_and_materialise_single(
                    arc4_dynamic_array_expression
                )
                (dynamic_array_length,) = self.assign(
                    temp_description="array_length",
                    source=Intrinsic(
                        op=AVMOp.extract_uint16,
                        args=[
                            array_value_with_length,
                            UInt64Constant(value=0, source_location=statement.source_location),
                        ],
                        source_location=statement.source_location,
                    ),
                    source_location=statement.source_location,
                )
                (dynamic_array_value,) = self.assign(
                    temp_description="array_value",
                    source=Intrinsic(
                        op=AVMOp.extract,
                        args=[array_value_with_length],
                        immediates=[2, 0],
                        source_location=statement.source_location,
                    ),
                    source_location=statement.source_location,
                )

                def get_dynamic_array_item_at_index(index_register: Register) -> ValueProvider:
                    return self._read_nth_item_of_arc4_homogeneous_container(
                        array_bytes_sans_length_header=dynamic_array_value,
                        item_wtype=dynamic_array_wtype.element_type,
                        index=index_register,
                        source_location=statement.source_location,
                    )

                self._iterate_indexable(
                    loop_body=statement.loop_body,
                    indexable_size=dynamic_array_length,
                    get_value_at_index=get_dynamic_array_item_at_index,
                    item_var=item_var,
                    index_var=index_var,
                    statement_loc=statement.source_location,
                )
            case awst_nodes.Expression(
                wtype=wtypes.ARC4StaticArray(array_size=array_size) as static_array_wtype
            ) as arc4_static_array_expression:
                static_array_value = self._visit_and_materialise_single(
                    arc4_static_array_expression
                )

                static_array_length = UInt64Constant(
                    value=array_size, source_location=statement.source_location
                )

                def get_static_array_item_at_index(index_register: Register) -> ValueProvider:
                    return self._read_nth_item_of_arc4_homogeneous_container(
                        array_bytes_sans_length_header=static_array_value,
                        item_wtype=static_array_wtype.element_type,
                        index=index_register,
                        source_location=statement.source_location,
                    )

                self._iterate_indexable(
                    loop_body=statement.loop_body,
                    indexable_size=static_array_length,
                    get_value_at_index=get_static_array_item_at_index,
                    item_var=item_var,
                    index_var=index_var,
                    statement_loc=statement.source_location,
                )
            case _:
                raise TodoError(statement.source_location, "TODO: IR build support")

    def _read_nth_item_of_arc4_heterogeneous_container(
        self,
        *,
        array_bytes_sans_length_header: Value,
        tuple_type: wtypes.ARC4Tuple | wtypes.ARC4Struct,
        index: UInt64Constant,
        source_location: SourceLocation,
    ) -> ValueProvider:
        tuple_item_types = tuple_type.types

        item_wtype = tuple_item_types[index.value]
        item_bit_size = get_arc4_fixed_bit_size(item_wtype)
        head_up_to_item = determine_arc4_tuple_head_size(
            tuple_item_types[0 : index.value], round_end_result=False
        )
        if item_bit_size is not None:
            item_index: Value = UInt64Constant(
                value=(
                    head_up_to_item
                    if item_wtype == wtypes.arc4_bool_wtype
                    else bits_to_bytes(head_up_to_item)
                ),
                source_location=source_location,
            )
        else:
            item_index_value = Intrinsic(
                op=AVMOp.extract_uint16,
                args=[
                    array_bytes_sans_length_header,
                    UInt64Constant(
                        value=bits_to_bytes(head_up_to_item), source_location=source_location
                    ),
                ],
                source_location=source_location,
            )
            (item_index,) = self.assign(
                temp_description="item_index",
                source=item_index_value,
                source_location=source_location,
            )
        return self._read_nth_item_of_arc4_container(
            data=array_bytes_sans_length_header,
            index=item_index,
            item_wtype=item_wtype,
            item_bit_size=item_bit_size,
            source_location=source_location,
        )

    def _read_nth_item_of_arc4_homogeneous_container(
        self,
        *,
        array_bytes_sans_length_header: Value,
        item_wtype: wtypes.WType,
        index: Value,
        source_location: SourceLocation,
    ) -> ValueProvider:
        item_bit_size = get_arc4_fixed_bit_size(item_wtype)
        if item_bit_size is not None:
            item_index_value = Intrinsic(
                op=AVMOp.mul,
                args=[
                    index,
                    UInt64Constant(
                        value=item_bit_size
                        if item_wtype == wtypes.arc4_bool_wtype
                        else (item_bit_size // 8),
                        source_location=source_location,
                    ),
                ],
                source_location=source_location,
            )
        else:
            (item_index_index,) = self.assign(
                source_location=source_location,
                temp_description="item_index_index",
                source=Intrinsic(
                    source_location=source_location,
                    op=AVMOp.mul,
                    args=[index, UInt64Constant(value=2, source_location=source_location)],
                ),
            )
            item_index_value = Intrinsic(
                source_location=source_location,
                op=AVMOp.extract_uint16,
                args=[array_bytes_sans_length_header, item_index_index],
            )

        (item_index,) = self.assign(
            temp_description="item_index", source=item_index_value, source_location=source_location
        )

        return self._read_nth_item_of_arc4_container(
            data=array_bytes_sans_length_header,
            index=item_index,
            item_wtype=item_wtype,
            item_bit_size=item_bit_size,
            source_location=source_location,
        )

    def _read_nth_item_of_arc4_container(
        self,
        *,
        data: Value,
        index: Value,
        item_wtype: wtypes.WType,
        item_bit_size: int | None,
        source_location: SourceLocation,
    ) -> ValueProvider:
        """
        Reads the nth item of an arc4 array, tuple, or struct
        """
        if item_wtype == wtypes.arc4_bool_wtype:
            # item_index is the bit position
            (is_true,) = self.assign(
                temp_description="is_true",
                source=Intrinsic(
                    op=AVMOp.getbit, args=[data, index], source_location=source_location
                ),
                source_location=source_location,
            )
            return encode_arc4_bool(is_true, source_location)
        if item_bit_size is not None:
            # item_index is the byte position of our fixed length item
            end: Value = UInt64Constant(value=item_bit_size // 8, source_location=source_location)
        else:
            # item_index is the position of the 'length' bytes of our variable length item
            (item_length,) = self.assign(
                temp_description="item_length",
                source=Intrinsic(
                    op=AVMOp.extract_uint16,
                    args=[data, index],
                    source_location=source_location,
                ),
                source_location=source_location,
            )
            (end,) = self.assign(
                temp_description="item_length_plus_2",
                source=Intrinsic(
                    op=AVMOp.add,
                    args=[
                        item_length,
                        UInt64Constant(value=2, source_location=source_location),
                    ],
                    source_location=source_location,
                ),
                source_location=source_location,
            )
        return Intrinsic(
            op=AVMOp.extract3, args=[data, index, end], source_location=source_location
        )

    def _iterate_urange(
        self,
        *,
        loop_body: awst_nodes.Block,
        item_var: Expression,
        index_var: Expression | None,
        statement_loc: SourceLocation,
        range_start: Expression,
        range_stop: Expression,
        range_step: Expression,
        range_loc: SourceLocation,
    ) -> None:
        header, body, footer, next_block = mkblocks(
            statement_loc,
            "for_header",
            "for_body",
            "for_footer",
            "after_for",
        )

        step = self._visit_and_materialise_single(range_step)
        stop = self._visit_and_materialise_single(range_stop)
        start = self._visit_and_materialise_single(range_start)
        (range_item,) = self.assign(
            source=start,
            temp_description="range_item",
            source_location=item_var.source_location,
        )

        index_var_src_loc = index_var.source_location if index_var else None
        range_index = None
        if index_var:
            (range_index,) = self.assign(
                source=UInt64Constant(value=0, source_location=None),
                temp_description="range_index",
                source_location=index_var_src_loc,
            )

        self.block_builder.goto_and_activate(header)
        (continue_looping,) = self.assign(
            source=(
                Intrinsic(
                    op=AVMOp("<"),
                    args=[self._refresh_mutated_variable(range_item), stop],
                    source_location=range_loc,
                )
            ),
            temp_description="continue_looping",
            source_location=range_loc,
        )

        self.block_builder.terminate(
            ConditionalBranch(
                condition=continue_looping,
                non_zero=body,
                zero=next_block,
                source_location=statement_loc,
            )
        )
        self._seal(body)

        self.block_builder.activate_block(body)

        self._handle_assignment(
            target=item_var,
            value=self._refresh_mutated_variable(range_item),
            assignment_location=item_var.source_location,
        )
        if index_var and range_index:
            self._handle_assignment(
                target=index_var,
                value=self._refresh_mutated_variable(range_index),
                assignment_location=index_var.source_location,
            )

        with self.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(self)
        self.block_builder.goto_and_activate(footer)
        self._seal(footer)
        self._seal(next_block)
        new_range_item_value = Intrinsic(
            op=AVMOp("+"),
            args=[self._refresh_mutated_variable(range_item), step],
            source_location=range_loc,
        )
        self._reassign(range_item, new_range_item_value, statement_loc)
        if range_index:
            new_rang_index_value = Intrinsic(
                op=AVMOp("+"),
                args=[
                    self._refresh_mutated_variable(range_index),
                    UInt64Constant(value=1, source_location=None),
                ],
                source_location=None,
            )
            self._reassign(range_index, new_rang_index_value, index_var_src_loc)

        self.block_builder.goto(header)
        self._seal(header)

        self.block_builder.activate_block(next_block)

    def _iterate_indexable(
        self,
        *,
        loop_body: awst_nodes.Block,
        item_var: Expression,
        index_var: Expression | None,
        statement_loc: SourceLocation,
        indexable_size: Value,
        get_value_at_index: typing.Callable[[Register], ValueProvider],
    ) -> None:
        header, body, footer, next_block = mkblocks(
            statement_loc,
            "for_header",
            "for_body",
            "for_footer",
            "after_for",
        )

        (index_internal,) = self.assign(
            source=UInt64Constant(value=0, source_location=None),
            temp_description="item_index_internal",
            source_location=None,
        )

        self.block_builder.goto_and_activate(header)
        (continue_looping,) = self.assign(
            source=(
                Intrinsic(
                    op=AVMOp.lt,
                    args=[self._refresh_mutated_variable(index_internal), indexable_size],
                    source_location=statement_loc,
                )
            ),
            temp_description="continue_looping",
            source_location=statement_loc,
        )

        self.block_builder.terminate(
            ConditionalBranch(
                condition=continue_looping,
                non_zero=body,
                zero=next_block,
                source_location=statement_loc,
            )
        )
        self._seal(body)

        self.block_builder.activate_block(body)

        current_index_internal = self._refresh_mutated_variable(index_internal)
        item_value = get_value_at_index(current_index_internal)
        self._handle_assignment(
            target=item_var,
            value=item_value,
            assignment_location=item_var.source_location,
        )

        if index_var:
            self._handle_assignment(
                target=index_var,
                value=current_index_internal,
                assignment_location=index_var.source_location,
            )

        with self.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(self)
        self.block_builder.goto_and_activate(footer)
        self._seal(footer)
        self._seal(next_block)
        new_index_internal_value = Intrinsic(
            op=AVMOp("+"),
            args=[
                self._refresh_mutated_variable(index_internal),
                UInt64Constant(value=1, source_location=None),
            ],
            source_location=None,
        )
        self._reassign(index_internal, new_index_internal_value, source_location=None)

        self.block_builder.goto(header)
        self._seal(header)

        self.block_builder.activate_block(next_block)

    def _iterate_tuple(
        self,
        loop_body: awst_nodes.Block,
        item_var: awst_nodes.Expression,
        index_var: awst_nodes.Expression | None,
        tuple_items: Sequence[Value],
        statement_loc: SourceLocation,
    ) -> None:
        headers = [
            BasicBlock(comment=f"for_header_{index}", source_location=statement_loc)
            for index, _ in enumerate(tuple_items)
        ]

        body, footer, next_block = mkblocks(
            statement_loc,
            "for_body",
            "for_footer",
            "after_for",
        )

        tuple_index = self._next_tmp_name("tuple_index")
        for index, (item, header) in enumerate(zip(tuple_items, headers)):
            if index == 0:
                self.block_builder.goto_and_activate(header)
                self._seal(header)
                self.assign(
                    source=UInt64Constant(value=0, source_location=None),
                    names=[(tuple_index, None)],
                    source_location=None,
                )
            else:
                self.block_builder.activate_block(header, ignore_predecessor_check=True)
            self._handle_assignment(
                target=item_var,
                value=item,
                assignment_location=item_var.source_location,
            )
            self.block_builder.goto(body)

        self._seal(body)
        self.block_builder.activate_block(body)
        if index_var:
            self._handle_assignment(
                target=index_var,
                value=self.ssa.read_variable(tuple_index, AVMType.uint64, body),
                assignment_location=index_var.source_location,
            )
        with self.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(self)

        self.block_builder.goto_and_activate(footer)
        self._seal(footer)
        curr_index_internal = self.ssa.read_variable(tuple_index, AVMType.uint64, footer)
        (_updated_r,) = self.assign(
            source=Intrinsic(
                op=AVMOp("+"),
                args=[curr_index_internal, UInt64Constant(value=1, source_location=None)],
                source_location=None,
            ),
            names=[(tuple_index, None)],
            source_location=None,
        )
        self.block_builder.terminate(
            GotoNth(
                source_location=statement_loc,
                value=curr_index_internal,
                blocks=headers[1:],
                default=next_block,
            )
        )
        for header in headers[1:]:
            self._seal(header)

        self._seal(next_block)
        self.block_builder.activate_block(next_block)

    def visit_array_append(self, expr: awst_nodes.ArrayAppend) -> TExpression:
        raise TodoError(expr.source_location, "TODO: visit_new_struct")

    def visit_new_struct(self, expr: awst_nodes.NewStruct) -> TExpression:
        raise TodoError(expr.source_location, "TODO: visit_new_struct")


def mkblocks(loc: SourceLocation, *comments: str | None) -> Iterator[BasicBlock]:
    for c in comments:
        yield BasicBlock(comment=c, source_location=loc)


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


def format_tuple_index(var_name: str, index: int | str) -> str:
    return f"{var_name}.{index}"


def encode_arc4_bool(value: Value, source_location: SourceLocation) -> ValueProvider:
    return Intrinsic(
        op=AVMOp.setbit,
        args=[
            BytesConstant(
                value=0x00.to_bytes(1, "big"),
                source_location=source_location,
                encoding=AVMBytesEncoding.base16,
            ),
            UInt64Constant(value=0, source_location=None),
            value,
        ],
        source_location=source_location,
    )


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
