import base64
import itertools
import typing
from collections.abc import Iterator, Sequence

import structlog

import wyvern.awst.visitors
from wyvern.awst import (
    nodes as awst_nodes,
    wtypes,
)
from wyvern.awst.nodes import (
    BigUIntBinaryOperator,
    BytesEncoding,
    Expression,
    UInt64BinaryOperator,
)
from wyvern.errors import CodeError, InternalError, TodoError
from wyvern.ir.avm_ops import AVMOp
from wyvern.ir.blocks_builder import BlocksBuilder
from wyvern.ir.context import IRBuildContext, IRFunctionBuildContext
from wyvern.ir.models import (
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
    Op,
    ProgramExit,
    Register,
    Subroutine,
    SubroutineReturn,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from wyvern.ir.ssa import BraunSSA
from wyvern.ir.types_ import (
    AVMBytesEncoding,
    AVMType,
    bytes_enc_to_avm_bytes_enc,
    wtype_to_avm_type,
)
from wyvern.parse import SourceLocation

TExpression: typing.TypeAlias = ValueProvider | None
TStatement: typing.TypeAlias = None

logger = structlog.get_logger(__name__)

TMP_VAR_INDICATOR = "%"


class FunctionIRBuilder(
    wyvern.awst.visitors.ExpressionVisitor[TExpression],
    wyvern.awst.visitors.StatementVisitor[TStatement],
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
        on_create_block, entrypoint_block = self._mkblocks(
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

    def _mkblocks(self, loc: SourceLocation, *comments: str | None) -> Iterator[BasicBlock]:
        for c in comments:
            yield BasicBlock(comment=c, source_location=loc)

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

    def visit_is_substring(self, expr: awst_nodes.IsSubstring) -> TExpression:
        """
        Search for a shorter string in a larger one.

        search_start = 0
        found = 0
        while (search_start + len(item) <= len_sequence):
            found = item == substr(sequence, search_start, search_start + len(item))
            if found:
                break
            search_start += 1
        return found
        """
        src_loc = expr.source_location

        header, body, footer, next_block = self._mkblocks(
            src_loc,
            "substr_header",
            "substr_body",
            "substr_footer",
            "substr_after",
        )
        item = self._visit_and_materialise_single(expr.item)
        sequence = self._visit_and_materialise_single(expr.sequence)
        (found,) = self.assign(
            temp_description="found",
            source=UInt64Constant(value=0, source_location=src_loc),
            source_location=src_loc,
        )
        (len_sequence,) = self.assign(
            temp_description="len_sequence",
            source=Intrinsic(op=AVMOp.len_, args=[sequence], source_location=src_loc),
            source_location=src_loc,
        )
        (len_item,) = self.assign(
            temp_description="len_item",
            source=Intrinsic(
                op=AVMOp.len_,
                args=[item],
                source_location=src_loc,
            ),
            source_location=src_loc,
        )
        (search_start,) = self.assign(
            temp_description="search_start",
            source=UInt64Constant(value=0, source_location=src_loc),
            source_location=src_loc,
        )
        self.block_builder.goto_and_activate(header)

        (search_end,) = self.assign(
            temp_description="search_end",
            source_location=src_loc,
            source=Intrinsic(
                op=AVMOp.add,
                args=[
                    self.ssa.read_register(search_start, header),
                    self.ssa.read_register(len_item, header),
                ],
                source_location=src_loc,
            ),
        )

        (cant_find,) = self.assign(
            temp_description="cant_find",
            source=Intrinsic(
                op=AVMOp.gt,
                args=[self.ssa.read_register(search_end, header), len_sequence],
                source_location=src_loc,
            ),
            source_location=src_loc,
        )

        self.block_builder.terminate(
            ConditionalBranch(
                condition=cant_find,
                non_zero=next_block,
                zero=body,
                source_location=src_loc,
            )
        )
        self.block_builder.activate_block(body)
        self._seal(body)

        (substr,) = self.assign(
            temp_description="substr",
            source=Intrinsic(
                op=AVMOp.substring3,
                args=[
                    sequence,
                    self.ssa.read_register(search_start, body),
                    self.ssa.read_register(search_end, body),
                ],
                source_location=src_loc,
            ),
            source_location=src_loc,
        )
        self.assign(
            names=[(found.name, src_loc)],
            source=Intrinsic(
                op=AVMOp.eq,
                args=[
                    self.ssa.read_register(substr, body),
                    item,
                ],
                source_location=src_loc,
            ),
            source_location=src_loc,
        )

        self.block_builder.terminate(
            ConditionalBranch(
                condition=self.ssa.read_register(found, body),
                zero=footer,
                non_zero=next_block,
                source_location=src_loc,
            )
        )
        self.block_builder.activate_block(footer)

        self.assign(
            names=[(search_start.name, src_loc)],
            source=Intrinsic(
                op=AVMOp.add,
                args=[
                    self.ssa.read_register(search_start, footer),
                    UInt64Constant(
                        value=1,
                        source_location=src_loc,
                    ),
                ],
                source_location=src_loc,
            ),
            source_location=src_loc,
        )

        self.block_builder.goto(header)

        self._seal(footer)
        self._seal(header)
        self.block_builder.activate_block(next_block)
        self._seal(next_block)

        return self.ssa.read_register(found, next_block)

    def visit_abi_decode(self, expr: awst_nodes.AbiDecode) -> TExpression:
        value = self._visit_and_materialise_single(expr.value)
        match expr.value.wtype:
            case wtypes.AbiUIntN(n=scale):
                match scale:
                    case 8:
                        op = AVMOp.getbyte
                    case 16:
                        op = AVMOp.extract_uint16
                    case 32:
                        op = AVMOp.extract_uint32
                    case 64:
                        op = AVMOp.extract_uint64
                    case _:
                        (integer_bytes,) = self.assign(
                            source=Intrinsic(
                                op=AVMOp.extract3,
                                args=[
                                    value,
                                    UInt64Constant(value=0, source_location=expr.source_location),
                                    UInt64Constant(
                                        value=scale // 8,
                                        source_location=expr.source_location,
                                    ),
                                ],
                                source_location=expr.source_location,
                            ),
                            temp_description="integer_bytes",
                            source_location=expr.source_location,
                        )
                        return Intrinsic(
                            op=AVMOp.btoi,
                            args=[
                                self.ssa.read_register(
                                    integer_bytes, self.block_builder.active_block
                                ),
                            ],
                            source_location=expr.source_location,
                        )

                return Intrinsic(
                    op=op,
                    args=[value, UInt64Constant(value=0, source_location=expr.source_location)],
                    source_location=expr.source_location,
                )
            case wtypes.abi_string_wtype:
                return Intrinsic(
                    op=AVMOp.extract,
                    immediates=[2, 0],
                    args=[value],
                    source_location=expr.source_location,
                )
            case _:
                raise TodoError(expr.source_location, "TODO: visit_abi_decode")

    def visit_abi_constant(self, expr: awst_nodes.AbiConstant) -> TExpression:
        return BytesConstant(
            source_location=expr.source_location,
            encoding=bytes_enc_to_avm_bytes_enc(expr.bytes_encoding),
            value=expr.value,
        )

    def visit_abi_encode(self, expr: awst_nodes.AbiEncode) -> TExpression:
        value = self._visit_and_materialise_single(expr.value)

        match expr.wtype:
            case wtypes.abi_string_wtype:
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
                    args=[
                        self._value_as_uint16(length, expr.source_location),
                        value,
                    ],
                    source_location=expr.source_location,
                )
            case wtypes.AbiUIntN(n=scale) if scale <= 64:
                (val_as_bytes,) = self.assign(
                    temp_description="val_as_bytes",
                    source_location=expr.source_location,
                    source=Intrinsic(
                        op=AVMOp.itob, args=[value], source_location=expr.source_location
                    ),
                )
                scale_bytes = scale // 8

                return Intrinsic(
                    op=AVMOp.substring3,
                    args=[
                        val_as_bytes,
                        UInt64Constant(
                            value=8 - scale_bytes, source_location=expr.source_location
                        ),
                        UInt64Constant(value=8, source_location=expr.source_location),
                    ],
                    source_location=expr.source_location,
                )
        raise TodoError(expr.source_location, "TODO: Handle wtype")

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

    @staticmethod
    def _create_uint64_binary_op(
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

    @staticmethod
    def _create_biguint_binary_op(
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

    def visit_uint64_binary_operation(self, expr: awst_nodes.UInt64BinaryOperation) -> TExpression:
        left = self._visit_and_materialise_single(expr.left)
        right = self._visit_and_materialise_single(expr.right)
        return self._create_uint64_binary_op(expr.op, left, right, expr.source_location)

    def visit_biguint_binary_operation(
        self, expr: awst_nodes.BigUIntBinaryOperation
    ) -> TExpression:
        left = self._visit_and_materialise_single(expr.left)
        right = self._visit_and_materialise_single(expr.right)
        return self._create_biguint_binary_op(expr.op, left, right, expr.source_location)

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

    def visit_uint64_constant(self, expr: awst_nodes.UInt64Constant) -> TExpression:
        return UInt64Constant(
            value=expr.value, source_location=expr.source_location, teal_alias=expr.teal_alias
        )

    def visit_biguint_constant(self, expr: awst_nodes.BigUIntConstant) -> TExpression:
        return BigUIntConstant(value=expr.value, source_location=expr.source_location)

    def visit_bool_constant(self, expr: awst_nodes.BoolConstant) -> TExpression:
        return UInt64Constant(value=int(expr.value), source_location=expr.source_location)

    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> TExpression:
        return BytesConstant(
            value=expr.value,
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
        left = self._visit_and_materialise_single(expr.lhs)
        right = self._visit_and_materialise_single(expr.rhs)
        if left.atype != right.atype:
            raise InternalError(
                "Numeric comparison between different numeric types", expr.source_location
            )
        if left.atype == AVMType.any:
            raise InternalError("Numeric comparison mapped to any type", expr.source_location)
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

    def visit_bytes_decode(self, expr: awst_nodes.BytesDecode) -> TExpression:
        match expr.encoding:
            case BytesEncoding.base16:
                value = base64.b16decode(expr.value)
                encoding = AVMBytesEncoding.base16
            case BytesEncoding.base32:
                value = base64.b32decode(expr.value)
                encoding = AVMBytesEncoding.base32
            case BytesEncoding.base64:
                value = base64.b64decode(expr.value)
                encoding = AVMBytesEncoding.base64
            case BytesEncoding.method:
                raise TodoError(expr.source_location, f"TODO: support encoding {expr.encoding}")
            case _:
                raise InternalError("Unsupported bytes encoding")
        return BytesConstant(value=value, encoding=encoding, source_location=expr.source_location)

    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> TExpression:
        items = []
        for item in expr.items:
            try:
                wtype_to_avm_type(item)
            except InternalError:  # TODO: UNYUCK THIS FUCK
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

    def visit_slice_expression(self, expr: wyvern.awst.nodes.SliceExpression) -> TExpression:
        """
        Slices an enumerable type.


        """
        if expr.base.wtype == wtypes.bytes_wtype:
            base = self._visit_and_materialise_single(expr.base)

            # For certain constant values we can use the immediate version of extract/substring
            match (base, expr.begin_index, expr.end_index):
                case (
                    _,
                    wyvern.awst.nodes.UInt64Constant() as start,
                    wyvern.awst.nodes.UInt64Constant() as stop,
                ):
                    return self._extract_with_constants(
                        AVMOp.substring, base, start.value, stop.value, expr.source_location
                    )
                case (_, wyvern.awst.nodes.UInt64Constant() as start, None):
                    return self._extract_with_constants(
                        AVMOp.extract, base, start.value, 0, expr.source_location
                    )
                case (_, None, wyvern.awst.nodes.UInt64Constant() as stop):
                    return self._extract_with_constants(
                        AVMOp.extract, base, 0, stop.value, expr.source_location
                    )

            (base_length,) = self.assign(
                source_location=expr.source_location,
                source=Intrinsic(op=AVMOp.len_, args=[base], source_location=expr.source_location),
                temp_description="base_length",
            )
            start_value: Value
            match expr.begin_index:
                case None:
                    start_value = UInt64Constant(value=0, source_location=expr.source_location)
                case Expression() as begin_expr:
                    start_value = self._visit_and_materialise_single(begin_expr)
                case _:
                    raise InternalError("Shouldn't get here")

            stop_value: Value
            if expr.end_index:
                match expr.end_index:
                    case Expression() as begin_expr:
                        stop_value = self._visit_and_materialise_single(begin_expr)
                    case _:
                        raise InternalError("Shouldn't get here")

                return Intrinsic(
                    op=AVMOp.substring3,
                    args=[base, start_value, stop_value],
                    source_location=expr.source_location,
                )
            else:
                return Intrinsic(
                    op=AVMOp.substring3,
                    args=[
                        base,
                        start_value,
                        self.ssa.read_register(base_length, self.block_builder.active_block),
                    ],
                    source_location=expr.source_location,
                )

        else:
            raise TodoError(expr.source_location, f"TODO: IR Slice {expr.wtype}")

    @staticmethod
    def _extract_with_constants(
        op: typing.Literal[AVMOp.substring, AVMOp.extract],
        expr: Value,
        start: int,
        stop_or_length: int,
        source_location: SourceLocation,
    ) -> Intrinsic:
        return Intrinsic(
            op=op,
            args=[expr],
            immediates=[start, stop_or_length],
            source_location=source_location,
        )

    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> TExpression:
        if expr.base.wtype == wtypes.bytes_wtype and expr.index.wtype == wtypes.uint64_wtype:
            # note: the below works because Bytes is immutable, so this index expression
            # can never appear as an assignment target
            base = self._visit_and_materialise_single(expr.base)
            index = self._visit_and_materialise_single(expr.index)
            if isinstance(index, UInt64Constant):
                return self._extract_with_constants(
                    AVMOp.extract, base, index.value, 1, expr.source_location
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
        raise TodoError(expr.source_location, "TODO: IR building: visit_index_expression")

    def visit_conditional_expression(self, expr: awst_nodes.ConditionalExpression) -> TExpression:
        # TODO: if expr.true_value and exr.false_value are var expressions,
        #       we can optimize with the `select` op

        true_block, false_block, merge_block = self._mkblocks(
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

    def _value_as_uint16(self, value: Value, source_location: SourceLocation) -> Value:
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

    def visit_new_abi_array(self, expr: awst_nodes.NewAbiArray) -> TExpression:
        elements = [self._visit_and_materialise_single(el) for el in expr.elements]

        array_data: Register | None = None

        if isinstance(expr.wtype, wtypes.AbiDynamicArray):
            (array_data,) = self.assign(
                source_location=expr.source_location,
                source=BytesConstant(
                    source_location=expr.source_location,
                    encoding=AVMBytesEncoding.base16,
                    value=len(elements).to_bytes(2, "big"),
                ),
                temp_description="array_data",
            )
        if expr.wtype.element_type == wtypes.abi_string_wtype:
            (next_offset,) = self.assign(
                source_location=expr.source_location,
                source=UInt64Constant(
                    value=(2 * len(elements)),
                    source_location=expr.source_location,
                ),
                temp_description="next_offset",
            )
            for element in elements:
                if array_data is None:
                    (array_data,) = self.assign(
                        source_location=expr.source_location,
                        source=self._value_as_uint16(
                            self.ssa.read_register(next_offset, self.block_builder.active_block),
                            source_location=expr.source_location,
                        ),
                        temp_description="array_data",
                    )
                else:
                    (array_data,) = self.assign(
                        source_location=expr.source_location,
                        source=Intrinsic(
                            op=AVMOp.concat,
                            args=[
                                self.ssa.read_register(
                                    array_data, self.block_builder.active_block
                                ),
                                self._value_as_uint16(
                                    self.ssa.read_register(
                                        next_offset, self.block_builder.active_block
                                    ),
                                    source_location=expr.source_location,
                                ),
                            ],
                            source_location=expr.source_location,
                        ),
                        names=[(array_data.name, expr.source_location)],
                    )

                (element_length,) = self.assign(
                    source_location=expr.source_location,
                    source=Intrinsic(
                        op=AVMOp.len_, args=[element], source_location=expr.source_location
                    ),
                    temp_description="element_length",
                )
                self.assign(
                    source_location=expr.source_location,
                    names=[(next_offset.name, expr.source_location)],
                    source=Intrinsic(
                        op=AVMOp.add,
                        args=[
                            self.ssa.read_register(next_offset, self.block_builder.active_block),
                            element_length,
                        ],
                        source_location=expr.source_location,
                    ),
                )

        for element in elements:
            if array_data is None:
                (array_data,) = self.assign(
                    source_location=expr.source_location,
                    source=element,
                    temp_description="array_data",
                )
            else:
                (array_data,) = self.assign(
                    source_location=expr.source_location,
                    source=Intrinsic(
                        op=AVMOp.concat,
                        args=[
                            self.ssa.read_register(array_data, self.block_builder.active_block),
                            element,
                        ],
                        source_location=expr.source_location,
                    ),
                    names=[(array_data.name, expr.source_location)],
                )

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

    @staticmethod
    def _create_bytes_binary_op(
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

    def visit_bytes_binary_operation(self, expr: awst_nodes.BytesBinaryOperation) -> TExpression:
        left = self._visit_and_materialise_single(expr.left)
        right = self._visit_and_materialise_single(expr.right)
        return self._create_bytes_binary_op(expr.op, left, right, expr.source_location)

    def visit_boolean_binary_operation(
        self, expr: awst_nodes.BooleanBinaryOperation
    ) -> TExpression:
        if not isinstance(expr.right, awst_nodes.VarExpression | awst_nodes.BoolConstant):
            true_block, false_block, merge_block = self._mkblocks(
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

    def _get_comparison_op_for_wtype(
        self, numeric_comparison_equivalent: awst_nodes.NumericComparison, wtype: wtypes.WType
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
                op=self._get_comparison_op_for_wtype(
                    awst_nodes.NumericComparison.eq, expr.item.wtype
                ),
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
        if_body, else_body, next_block = self._mkblocks(
            stmt.source_location, "if_body", "else_body", "after_if_else"
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
        top, body, next_block = self._mkblocks(
            statement.source_location, "while_top", "while_body", "after_while"
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
        else:
            raise InternalError(
                "Unexpected IR type for expression statement:"
                f" {type(result).__name__}, value is {result}",
                statement.source_location,
            )

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
        self, statement: wyvern.awst.nodes.UInt64AugmentedAssignment
    ) -> TStatement:
        target_value = self._visit_and_materialise_single(statement.target)
        rhs = self._visit_and_materialise_single(statement.value)
        expr = self._create_uint64_binary_op(
            statement.op, target_value, rhs, statement.source_location
        )

        self._handle_assignment(
            target=statement.target,
            value=expr,
            assignment_location=statement.source_location,
        )

    def visit_biguint_augmented_assignment(
        self, statement: wyvern.awst.nodes.BigUIntAugmentedAssignment
    ) -> TStatement:
        target_value = self._visit_and_materialise_single(statement.target)
        rhs = self._visit_and_materialise_single(statement.value)
        expr = self._create_biguint_binary_op(
            statement.op, target_value, rhs, statement.source_location
        )

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
        expr = self._create_bytes_binary_op(
            statement.op, target_value, rhs, statement.source_location
        )

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
                    "when using enumerate(), loop variables must be an unpacked two item tuple",
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

                def assign_item_var_from_index(index_register: Register) -> None:
                    block = self.block_builder.active_block
                    self._handle_assignment(
                        target=item_var,
                        value=Intrinsic(
                            op=AVMOp.extract3,
                            args=[
                                bytes_value,
                                self.ssa.read_register(index_register, block),
                                UInt64Constant(value=1, source_location=None),
                            ],
                            source_location=item_var.source_location,
                        ),
                        assignment_location=item_var.source_location,
                    )

                self._iterate_indexable(
                    loop_body=statement.loop_body,
                    indexable_size=byte_length,
                    assign_item_var_from_index=assign_item_var_from_index,
                    index_var=index_var,
                    statement_loc=statement.source_location,
                )

            case _:
                raise TodoError(statement.source_location, "TODO: IR build support")

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
        header, body, footer, next_block = self._mkblocks(
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
                    args=[self.ssa.read_register(range_item, header), stop],
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
            value=self.ssa.read_register(range_item, body),
            assignment_location=item_var.source_location,
        )
        if index_var and range_index:
            self._handle_assignment(
                target=index_var,
                value=self.ssa.read_register(range_index, body),
                assignment_location=index_var.source_location,
            )

        with self.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(self)
        self.block_builder.goto_and_activate(footer)
        self._seal(footer)
        self._seal(next_block)
        self.assign(
            source=Intrinsic(
                op=AVMOp("+"),
                args=[self.ssa.read_register(range_item, footer), step],
                source_location=range_loc,
            ),
            names=[(range_item.name, item_var.source_location)],
            source_location=statement_loc,
        )
        if range_index:
            self.assign(
                source=Intrinsic(
                    op=AVMOp("+"),
                    args=[
                        self.ssa.read_register(range_index, footer),
                        UInt64Constant(value=1, source_location=None),
                    ],
                    source_location=None,
                ),
                names=[(range_index.name, index_var_src_loc)],
                source_location=index_var_src_loc,
            )

        self.block_builder.goto(header)
        self._seal(header)

        self.block_builder.activate_block(next_block)

    def _iterate_indexable(
        self,
        *,
        loop_body: awst_nodes.Block,
        index_var: Expression | None,
        statement_loc: SourceLocation,
        indexable_size: Register,
        assign_item_var_from_index: typing.Callable[[Register], None],
    ) -> None:
        header, body, footer, next_block = self._mkblocks(
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
                    op=AVMOp("<"),
                    args=[
                        self.ssa.read_register(index_internal, header),
                        self.ssa.read_register(indexable_size, header),
                    ],
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

        assign_item_var_from_index(index_internal)

        if index_var:
            self._handle_assignment(
                target=index_var,
                value=self.ssa.read_register(index_internal, body),
                assignment_location=index_var.source_location,
            )

        with self.block_builder.enter_loop(on_continue=footer, on_break=next_block):
            loop_body.accept(self)
        self.block_builder.goto_and_activate(footer)
        self._seal(footer)
        self._seal(next_block)
        self.assign(
            source=Intrinsic(
                op=AVMOp("+"),
                args=[
                    self.ssa.read_register(index_internal, footer),
                    UInt64Constant(value=1, source_location=None),
                ],
                source_location=None,
            ),
            names=[(index_internal.name, None)],
            source_location=None,
        )

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

        body, footer, next_block = self._mkblocks(
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


def format_tuple_index(var_name: str, index: int | str) -> str:
    return f"{var_name}.{index}"
