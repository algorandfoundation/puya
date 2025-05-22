import typing
from collections.abc import Mapping, Sequence

import attrs

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    txn_fields,
    wtypes,
)
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.awst.visitors import ExpressionVisitor
from puya.awst.wtypes import WInnerTransactionFields
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._tuple_util import build_tuple_item_names
from puya.ir.builder._utils import assign, assign_intrinsic_op
from puya.ir.builder.blocks import BlocksBuilder
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    BasicBlock,
    ConditionalBranch,
    InnerTransactionField,
    Intrinsic,
    ITxnConstant,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.ssa import BraunSSA
from puya.ir.types_ import (
    PrimitiveIRType,
    get_wtype_arity,
    sum_wtypes_arity,
    wtype_to_ir_type,
    wtype_to_ir_types,
)
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation
from puya.utils import StableSet, positive_index

logger = log.get_logger(__name__)

_INNER_TRANSACTION_NON_ARRAY_FIELDS = [f for f in txn_fields.TxnField if not f.is_array]
_FIELD_IR_TYPES = {
    # fake source location is okay here, because this is executed as part of module initialization,
    # any types without a valid mapping (which there really shouldn't be) will cause errors
    # immediately on compiler startup rather than during compilation.
    f: wtype_to_ir_type(f.wtype, SourceLocation(file=None, line=1))
    for f in txn_fields.TxnField
}


@attrs.frozen(kw_only=True)
class CreateInnerTransactionFieldData:
    var_name: str
    field: txn_fields.TxnField
    field_counts: set[int] = attrs.field(factory=set)
    """The observed number of values for this field
    For non-array fields this will be either 0 or 1
    For array fields this will be 0 -> N
    Capturing these ranges allows generating much simpler IR
    """
    field_count_register_name: str

    @property
    def value_registers(self) -> dict[int, str]:
        return {idx: self.get_value_register_name(idx) for idx in range(max(self.field_counts))}

    def get_value_register_name(self, index: int) -> str:
        return f"{self.var_name}%%param_{self.field.immediate}_idx_{index}"


@attrs.frozen(kw_only=True)
class CreateInnerTransactionData:
    var_name: str
    fields: dict[txn_fields.TxnField, CreateInnerTransactionFieldData] = attrs.field(
        factory=dict, init=False
    )

    def get_or_add_field_data(self, field: txn_fields.TxnField) -> CreateInnerTransactionFieldData:
        try:
            field_data = self.fields[field]
        except KeyError:
            field_data = self.fields[field] = CreateInnerTransactionFieldData(
                var_name=self.var_name,
                field=field,
                field_count_register_name=f"{self.var_name}%%{field.immediate}_length",
            )
        return field_data


class InnerTransactionBuilder:
    def __init__(self, context: IRFunctionBuildContext):
        self.context = context
        self._inner_txn_fields_data = dict[str, CreateInnerTransactionData]()
        self._create_itxn_counter = iter(range(2**64 - 1))

    @property
    def ssa(self) -> BraunSSA:
        return self.context.block_builder.ssa

    @property
    def block_builder(self) -> BlocksBuilder:
        return self.context.block_builder

    def handle_inner_transaction_field_assignments(
        self, stmt: awst_nodes.AssignmentStatement
    ) -> bool:
        # awst_nodes.CreateInnerTransaction is used to create a set of fields used in an inner txn
        # When lowering this to IR field values and sizes are stored to local registers using
        # the top level variable name as a prefix.
        # For unused fields the size is 0
        # For array fields the size goes up to the length of the array
        # Other fields will have a size of 1
        #
        # Then itxn field sets are referenced the values are read using normal SSA functions
        # this allows for complex use cases such as branches and loops to still function

        value = stmt.value
        source_location = stmt.source_location
        target = stmt.target
        match value:
            case awst_nodes.CreateInnerTransaction(fields=fields):
                ((var_name, var_loc),) = _get_assignment_target_local_names(target, 1)
                self._set_inner_transaction_fields(var_name, fields, var_loc)
                return True
            case awst_nodes.Copy(
                value=awst_nodes.Expression(wtype=wtypes.WInnerTransactionFields()) as copy_source
            ):
                ((var_name, var_loc),) = _get_assignment_target_local_names(target, 1)
                src_var_name = self._resolve_inner_txn_params_var_name(copy_source)
                self._copy_inner_transaction_fields(var_name, src_var_name, var_loc)
                return True
            case awst_nodes.TupleExpression(items=tuple_items) as tuple_source if any(
                isinstance(t, WInnerTransactionFields) for t in tuple_source.wtype.types
            ):
                names = _get_assignment_target_local_names(target, len(tuple_items))
                for (item_name, item_loc), item_value in zip(names, tuple_items, strict=True):
                    match item_value:
                        case awst_nodes.CreateInnerTransaction(fields=fields):
                            self._set_inner_transaction_fields(item_name, fields, item_loc)
                        case awst_nodes.Copy(
                            value=awst_nodes.Expression(
                                wtype=wtypes.WInnerTransactionFields()
                            ) as copy_source
                        ):
                            src_var_name = self._resolve_inner_txn_params_var_name(copy_source)
                            self._copy_inner_transaction_fields(item_name, src_var_name, item_loc)
                        case awst_nodes.Expression(wtype=wtypes.WInnerTransactionFields()):
                            raise CodeError(
                                "Unexpected Inner Transaction encountered in tuple", item_loc
                            )
                        case _:
                            value_provider = self.context.visitor.visit_expr(item_value)
                            assign(
                                self.context,
                                value_provider,
                                name=item_name,
                                register_location=item_loc,
                                assignment_location=source_location,
                            )
                return True
            case awst_nodes.Expression(wtype=wtypes.WInnerTransactionFields()):
                raise CodeError(
                    "Inner Transaction params can only be reassigned using copy()",
                    source_location,
                )
            case _:
                return False

    def _visit_submit_expr(self, expr: awst_nodes.Expression) -> Sequence[Value]:
        value_provider = self.context.visitor.visit_expr(expr)
        match value_provider:
            case ValueTuple(values=values):
                return values
            case Value() as value:
                return (value,)
        raise InternalError(
            "Unexpected result for SubmitInnerTransaction expr", expr.source_location
        )

    def add_inner_transaction_submit_result_assignments(
        self,
        targets: Sequence[Value],
        source_expr: awst_nodes.Expression,
        ass_loc: SourceLocation | None,
    ) -> None:
        """Performs special handling for inner transaction related assignments"""
        # awst_nodes.SubmitInnerTransaction is used to submit itxn field sets as an inner
        # transaction group
        # Then all non aray fields are assigned to local registers and cached
        # This allows these fields to be read later even if additional itxn submissions have been
        # performed.
        # Array fields can not be cached in the same way currently, due to the lack of an
        # efficient array type.

        # targets are the assignment results, which will all be registers here,
        # the only case they aren't registers is when assigning to storage, which will
        # never be supported for itxn's because they're ephemeral
        source_actions = _ITxnSourceValueActionExtractor.visit(source_expr)
        for target, source_action in zip(targets, source_actions, strict=True):
            match target, source_action:
                case Register(ir_type=PrimitiveIRType.itxn_group_idx), _CopySource(
                    var_name=src_var_name
                ):
                    self._copy_submit_inner_transaction_fields(target.name, src_var_name)
                case Register(ir_type=PrimitiveIRType.itxn_group_idx), _AssignSubmit(
                    is_last=is_last
                ):
                    self._assign_submit_inner_transaction_fields(target, is_last=is_last)
                case tt, None if tt.ir_type != PrimitiveIRType.itxn_group_idx:
                    pass
                case _:
                    raise CodeError(
                        f"unsupported inner transaction assignment: {target!r} <- {source_action}",
                        ass_loc,
                    )

    def handle_update_inner_transaction(self, call: awst_nodes.UpdateInnerTransaction) -> None:
        var_name = self._resolve_inner_txn_params_var_name(call.itxn)
        self._set_inner_transaction_fields(
            var_name, call.fields, call.source_location, update=True
        )

    def handle_inner_transaction_field(
        self, itxn_field: awst_nodes.InnerTransactionField
    ) -> ValueProvider:
        src_loc = itxn_field.source_location
        field = itxn_field.field
        if field.is_array != bool(itxn_field.array_index):
            raise InternalError(
                "inconsistent array_index for inner transaction field",
                src_loc,
            )

        itxn = self.context.visitor.visit_expr(itxn_field.itxn)
        if not isinstance(itxn, Register | ITxnConstant):
            itxn_field_desc = {itxn_field.itxn.accept(ToCodeVisitor())}
            raise CodeError(
                f"Could not resolve inner transaction group index for {itxn_field_desc}",
                src_loc,
            )

        # use cached field if available
        if isinstance(itxn, Register):
            field_var_name = _get_txn_field_var_name(itxn.name, field.immediate)
            if self.ssa.has_version(field_var_name):
                return self.ssa.read_variable(
                    field_var_name,
                    wtype_to_ir_type(field.wtype, itxn_field.source_location),
                    self.block_builder.active_block,
                )

        match itxn:
            # use is_last register if it is defined
            case Register(name=itxn_name) if self.ssa.has_version(_get_txn_is_last(itxn_name)):
                is_last_in_group: Value = self.ssa.read_variable(
                    _get_txn_is_last(itxn_name),
                    PrimitiveIRType.bool,
                    self.block_builder.active_block,
                )
            # otherwise infer based on itxn expr
            case _:
                is_last_in_group = UInt64Constant(
                    value=int(_is_last_itxn(itxn_field.itxn)),
                    ir_type=PrimitiveIRType.bool,
                    source_location=src_loc,
                )

        return InnerTransactionField(
            group_index=itxn,
            is_last_in_group=is_last_in_group,
            array_index=(
                self.context.visitor.visit_and_materialise_single(itxn_field.array_index)
                if itxn_field.array_index
                else None
            ),
            field=field.immediate,
            type=wtype_to_ir_type(field.wtype, itxn_field.source_location),
            source_location=src_loc,
        )

    def _emit_itxn_fields(
        self, fields: awst_nodes.Expression, emit_loc: SourceLocation
    ) -> BasicBlock:
        param_var_name = self._resolve_inner_txn_params_var_name(fields)
        next_txn = self.block_builder.mkblock(emit_loc, "next_txn")
        param_data = self._inner_txn_fields_data[param_var_name]

        # with the current implementation, reversing the order itxn_field is called
        # results in less stack manipulations as most values are naturally in the
        # required order when stack allocation occurs
        for field, field_data in reversed(param_data.fields.items()):
            field_value_counts = sorted(field_data.field_counts)
            if not field_value_counts or field_value_counts == [0]:
                # nothing to do
                continue

            min_num_values, *remaining_values = field_value_counts
            # values 0 -> min_num_values do not need to test
            # values min_num_values -> max_num_values need to check if they are set
            next_field = self.block_builder.mkblock(emit_loc, "next_field")
            self._set_field_values(field_data, 0, min_num_values)

            if remaining_values:
                last_num_values = min_num_values
                for next_num_values in remaining_values:
                    set_fields_blk = self.block_builder.mkblock(
                        emit_loc,
                        f"set_{field.immediate}_{last_num_values}_to_{next_num_values - 1}",
                    )
                    self.block_builder.terminate(
                        ConditionalBranch(
                            condition=self._get_is_field_count_gte(field_data, next_num_values),
                            non_zero=set_fields_blk,
                            zero=next_field,
                            source_location=emit_loc,
                        )
                    )
                    self.block_builder.activate_block(set_fields_blk)
                    self._set_field_values(field_data, last_num_values, next_num_values)
                    last_num_values = next_num_values

                self.block_builder.goto(next_field)
                self.block_builder.activate_block(next_field)
        return next_txn

    def handle_set_inner_transaction_fields(
        self, node: awst_nodes.SetInnerTransactionFields
    ) -> None:
        for idx, itxn in enumerate(node.itxns):
            if node.start_with_begin and idx == 0:
                self.block_builder.add(
                    Intrinsic(
                        op=AVMOp.itxn_begin,
                        source_location=node.source_location,
                    )
                )
            else:
                self.block_builder.add(
                    Intrinsic(
                        op=AVMOp.itxn_next,
                        source_location=node.source_location,
                    )
                )
            self._emit_itxn_fields(itxn, node.source_location)

    def handle_submit_inner_transaction(
        self, submit: awst_nodes.SubmitInnerTransaction
    ) -> Sequence[ITxnConstant]:
        src_loc = submit.source_location

        self.block_builder.add(
            Intrinsic(
                op=AVMOp.itxn_begin,
                source_location=src_loc,
            )
        )

        group_indexes = []
        for group_index, param in enumerate(submit.itxns):
            submit_var_loc = param.source_location
            if group_index > 0:
                self.block_builder.add(
                    Intrinsic(
                        op=AVMOp.itxn_next,
                        source_location=submit_var_loc,
                    )
                )
            next_txn = self._emit_itxn_fields(param, submit_var_loc)

            group_indexes.append(
                ITxnConstant(
                    value=group_index,
                    source_location=submit_var_loc,
                    ir_type=PrimitiveIRType.itxn_group_idx,
                )
            )

            self.block_builder.goto(next_txn)
            self.block_builder.activate_block(next_txn)

        self.block_builder.add(
            Intrinsic(
                op=AVMOp.itxn_submit,
                source_location=src_loc,
            )
        )

        return group_indexes

    def _assign_submit_inner_transaction_fields(
        self,
        target: Register,
        *,
        is_last: bool,
    ) -> None:
        var_name = target.name
        is_last_in_group = assign(
            self.context,
            source=UInt64Constant(
                value=int(is_last),
                ir_type=PrimitiveIRType.bool,
                source_location=None,
            ),
            name=_get_txn_is_last(var_name),
            register_location=None,
            assignment_location=None,
        )
        for field in _INNER_TRANSACTION_NON_ARRAY_FIELDS:
            field_reg = _get_txn_field_var_name(var_name, field.immediate)
            assign(
                context=self.context,
                source=InnerTransactionField(
                    field=field.immediate,
                    group_index=target,
                    is_last_in_group=is_last_in_group,
                    type=_FIELD_IR_TYPES[field],
                    array_index=None,
                    source_location=None,
                ),
                name=field_reg,
                register_location=None,
                assignment_location=None,
            )

    def _copy_submit_inner_transaction_fields(self, dest_var_name: str, src_var_name: str) -> None:
        active_block = self.context.block_builder.active_block
        for field in _INNER_TRANSACTION_NON_ARRAY_FIELDS:
            src_field = _get_txn_field_var_name(src_var_name, field.immediate)
            dest_field = _get_txn_field_var_name(dest_var_name, field.immediate)
            assign(
                context=self.context,
                source=self.context.ssa.read_variable(
                    src_field, _FIELD_IR_TYPES[field], active_block
                ),
                name=dest_field,
                register_location=None,
                assignment_location=None,
            )

    def _set_field_values(
        self,
        field_data: CreateInnerTransactionFieldData,
        idx_from: int,
        idx_to: int,
    ) -> None:
        field = field_data.field
        field_ir_type = _FIELD_IR_TYPES[field]
        for idx in range(idx_from, idx_to):
            field_value = self.ssa.read_variable(
                field_data.get_value_register_name(idx),
                field_ir_type,
                self.block_builder.active_block,
            )
            self.block_builder.add(
                Intrinsic(
                    op=AVMOp.itxn_field,
                    source_location=None,
                    immediates=[field.immediate],
                    args=[field_value],
                )
            )

    def _get_is_field_count_gte(
        self, field_data: CreateInnerTransactionFieldData, count: int
    ) -> Register:
        field = field_data.field
        len_register = self.ssa.read_variable(
            field_data.field_count_register_name,
            PrimitiveIRType.uint64,
            self.block_builder.active_block,
        )

        is_field_count_gte = assign_intrinsic_op(
            self.context,
            target=f"is_{field.immediate}_count_gte_{count}",
            op=AVMOp.gte,
            args=[len_register, count],
            source_location=None,
        )
        return is_field_count_gte

    def _set_inner_transaction_fields(
        self,
        var_name: str,
        inner_txn_fields: Mapping[txn_fields.TxnField, awst_nodes.Expression],
        var_loc: SourceLocation,
        *,
        update: bool = False,
    ) -> None:
        param_data = self._inner_txn_fields_data.setdefault(
            var_name, CreateInnerTransactionData(var_name=var_name)
        )
        # assign a unique constant to var_name, not used for anything directly, but prevents
        # an undefined variable warning
        assign(
            context=self.context,
            source=ITxnConstant(
                value=next(self._create_itxn_counter),
                source_location=var_loc,
                ir_type=PrimitiveIRType.itxn_field_set,
            ),
            name=var_name,
            assignment_location=var_loc,
        )
        fields = StableSet.from_iter(inner_txn_fields)
        if not update:
            # add missing fields to end
            for field in txn_fields.TxnField:
                if field.is_inner_param and field not in fields:
                    fields.add(field)
        for field in fields:
            field_data = param_data.get_or_add_field_data(field)
            arg_expr = inner_txn_fields.get(field)
            values: Sequence[ValueProvider] = []
            count_loc = arg_expr.source_location if arg_expr else var_loc
            if arg_expr:
                match self.context.visitor.visit_expr(arg_expr):
                    case ValueTuple(values=values):
                        pass
                    case ValueProvider() as vp:
                        values = [vp]

            field_data.field_counts.add(len(values))
            for idx, value in enumerate(values):
                assign(
                    context=self.context,
                    source=value,
                    name=field_data.get_value_register_name(idx),
                    register_location=var_loc,
                    assignment_location=value.source_location,
                )
            assign(
                context=self.context,
                source=UInt64Constant(
                    value=len(values),
                    source_location=count_loc,
                ),
                name=field_data.field_count_register_name,
                register_location=var_loc,
                assignment_location=count_loc,
            )

    def _copy_inner_transaction_fields(
        self, dest_var_name: str, src_var_name: str, var_loc: SourceLocation
    ) -> None:
        src_params_data = self._inner_txn_fields_data[src_var_name]
        dest_params_data = self._inner_txn_fields_data.setdefault(
            dest_var_name, CreateInnerTransactionData(var_name=dest_var_name)
        )
        for field in txn_fields.TxnField:
            if not field.is_inner_param:
                continue
            src_field_data = src_params_data.get_or_add_field_data(field)

            dest_field_data = dest_params_data.get_or_add_field_data(field)
            dest_field_data.field_counts.update(src_field_data.field_counts)
            for idx, src_field_register in src_field_data.value_registers.items():
                dest_field_register = dest_field_data.get_value_register_name(idx)
                assign(
                    context=self.context,
                    source=self.ssa.read_variable(
                        src_field_register,
                        _FIELD_IR_TYPES[field],
                        self.block_builder.active_block,
                    ),
                    name=dest_field_register,
                    assignment_location=var_loc,
                )
            assign(
                context=self.context,
                source=self.ssa.read_variable(
                    src_field_data.field_count_register_name,
                    PrimitiveIRType.uint64,
                    self.block_builder.active_block,
                ),
                name=dest_field_data.field_count_register_name,
                assignment_location=var_loc,
            )

    def _resolve_inner_txn_params_var_name(self, params: awst_nodes.Expression) -> str:
        match params:
            case awst_nodes.CreateInnerTransaction() as itxn:
                var_name = self.context.next_tmp_name(description="inner_txn_params")
                self._set_inner_transaction_fields(
                    var_name=var_name, inner_txn_fields=itxn.fields, var_loc=itxn.source_location
                )
            case awst_nodes.VarExpression(name=var_name):
                pass
            case awst_nodes.TupleItemExpression(
                base=awst_nodes.VarExpression(name=name, wtype=wtypes.WTuple() as base_wtype),
                index=index,
            ):
                return format_tuple_index(base_wtype, name, index)
            case awst_nodes.Copy(value=value):
                return self._resolve_inner_txn_params_var_name(value)
            case _:
                raise InternalError(
                    "Could not resolve var_name for inner transaction params",
                    params.source_location,
                )
        return var_name


def _get_assignment_target_local_names(
    target: awst_nodes.Expression, expected_number: int
) -> Sequence[tuple[str, SourceLocation]]:
    match target:
        case awst_nodes.VarExpression(name=var_name) if expected_number == 1:
            return [(var_name, target.source_location)]
        case awst_nodes.VarExpression(name=var_name, wtype=wtypes.WTuple() as var_wtype):
            return [
                (format_tuple_index(var_wtype, var_name, idx), target.source_location)
                for idx in range(expected_number)
            ]
        case awst_nodes.TupleExpression(items=items) if expected_number == len(items) and all(
            isinstance(i, awst_nodes.VarExpression) for i in items
        ):
            items = typing.cast(Sequence[awst_nodes.VarExpression], items)
            return [(expr.name, expr.source_location) for expr in items]
        case awst_nodes.TupleItemExpression(
            base=awst_nodes.TupleExpression(wtype=tuple_wtype) as base, index=index
        ):
            tuple_names = _get_assignment_target_local_names(base, len(tuple_wtype.types))
            return [tuple_names[index]]
        case awst_nodes.FieldExpression(
            base=awst_nodes.TupleExpression(wtype=tuple_wtype) as base,
            name=name,
            source_location=name_loc,
        ):
            tuple_names = _get_assignment_target_local_names(base, len(tuple_wtype.types))
            index = tuple_wtype.name_to_index(name, name_loc)
            return [tuple_names[index]]
    raise CodeError(
        "Inner Transactions can only be assigned to local variables",
        target.source_location,
    )


@attrs.frozen
class _CopySource:
    var_name: str


@attrs.frozen
class _AssignSubmit:
    index: int
    is_last: bool


_SourceAction = _CopySource | _AssignSubmit | None


class _ITxnSourceValueActionExtractor(ExpressionVisitor[list[_SourceAction]]):
    """
    Collects itxn group index values used in an assignment statement source
    So when these are assigned to their targets the itxn fields can be cached
    """

    @classmethod
    def visit(cls, expr: awst_nodes.Expression) -> list[_SourceAction]:
        visitor = cls()
        result = expr.accept(visitor)
        if len(visitor.seen_submit_exprs) > 1:
            logger.error(
                "multiple inner transactions cannot be individually"
                " submitted in the same statement. Try using a group",
                location=expr.source_location,
            )
        return result

    def __init__(self) -> None:
        # used to ensure multiple submits are not present
        self.seen_submit_exprs = set[awst_nodes.SubmitInnerTransaction]()

    @typing.override
    def visit_submit_inner_transaction(
        self, expr: awst_nodes.SubmitInnerTransaction
    ) -> list[_SourceAction]:
        self.seen_submit_exprs.add(expr)
        itxns = len(expr.itxns)
        return [_AssignSubmit(index=idx, is_last=idx == itxns - 1) for idx in range(itxns)]

    @typing.override
    def visit_var_expression(self, expr: awst_nodes.VarExpression) -> list[_SourceAction]:
        return [
            _CopySource(var_name=name) if ir_type == PrimitiveIRType.itxn_group_idx else None
            for name, ir_type in build_tuple_item_names(
                expr.name, expr.wtype, expr.source_location
            )
        ]

    @typing.override
    def visit_single_evaluation(self, expr: awst_nodes.SingleEvaluation) -> list[_SourceAction]:
        return expr.source.accept(self)

    @typing.override
    def visit_checked_maybe(self, expr: awst_nodes.CheckedMaybe) -> list[_SourceAction]:
        # return the expr without the maybe portion
        return expr.expr.accept(self)[:1]

    @typing.override
    def visit_tuple_item_expression(
        self, expr: awst_nodes.TupleItemExpression
    ) -> list[_SourceAction]:
        # only keep the relevant action
        if isinstance(expr.base.wtype, wtypes.ARC4Tuple):
            return self._empty_actions_from_wtype(expr)
        assert isinstance(expr.base.wtype, wtypes.WTuple)
        added = expr.base.accept(self)
        assert len(added) == get_wtype_arity(expr.base.wtype)
        return list(
            _get_tuple_items(
                tuple_values=added,
                tuple_wtype=expr.base.wtype,
                index=expr.index,
            )
        )

    @typing.override
    def visit_tuple_expression(self, expr: awst_nodes.TupleExpression) -> list[_SourceAction]:
        return [t for item in expr.items for t in item.accept(self)]

    @typing.override
    def visit_field_expression(self, expr: awst_nodes.FieldExpression) -> list[_SourceAction]:
        base_wtype = expr.base.wtype
        if not (isinstance(base_wtype, wtypes.WTuple) and base_wtype.names):
            return self._empty_actions_from_wtype(expr)
        added = expr.base.accept(self)
        index = base_wtype.name_to_index(expr.name, expr.source_location)
        return list(
            _get_tuple_items(
                tuple_values=added,
                tuple_wtype=base_wtype,
                index=index,
            )
        )

    @typing.override
    def visit_slice_expression(self, expr: awst_nodes.SliceExpression) -> list[_SourceAction]:
        if not isinstance(expr.base.wtype, wtypes.WTuple):
            return self._empty_actions_from_wtype(expr)
        added = expr.base.accept(self)
        assert len(added) == get_wtype_arity(expr.base.wtype)
        # determine constant indexes
        tuple_size = len(added)
        begin_index = 0 if expr.begin_index is None else _get_uint64_const(expr.begin_index)
        end_index = tuple_size if expr.end_index is None else _get_uint64_const(expr.end_index)
        if begin_index is None or end_index is None:
            raise InternalError("uh-oh spaghetti-do's", expr.source_location)
        begin_index = positive_index(begin_index, added)
        end_index = positive_index(end_index, added)
        added = expr.base.accept(self)
        return list(
            _get_tuple_items(
                tuple_values=added,
                tuple_wtype=expr.base.wtype,
                index=(begin_index, end_index),
            )
        )

    @typing.override
    def visit_assignment_expression(
        self, expr: awst_nodes.AssignmentExpression
    ) -> list[_SourceAction]:
        return expr.value.accept(self)

    @typing.override
    def visit_reinterpret_cast(self, expr: awst_nodes.ReinterpretCast) -> list[_SourceAction]:
        return expr.expr.accept(self)

    @typing.override
    def visit_comma_expression(self, expr: awst_nodes.CommaExpression) -> list[_SourceAction]:
        return expr.expressions[-1].accept(self)

    # region idc
    def _empty_actions_from_wtype(self, expr: awst_nodes.Expression) -> list[_SourceAction]:
        ir_types = wtype_to_ir_types(expr.wtype, source_location=expr.source_location)
        # itxn_group_idx values are only supported in specific types of expressions
        if PrimitiveIRType.itxn_group_idx in ir_types:
            logger.error("unsupported inner transaction expression", location=expr.source_location)
        return [None] * len(ir_types)

    @typing.override
    def visit_set_inner_transaction_fields(
        self, expr: awst_nodes.SetInnerTransactionFields
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_state_delete(self, expr: awst_nodes.StateDelete) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_uint64_binary_operation(
        self, expr: awst_nodes.UInt64BinaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_biguint_binary_operation(
        self, expr: awst_nodes.BigUIntBinaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_integer_constant(self, expr: awst_nodes.IntegerConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_decimal_constant(self, expr: awst_nodes.DecimalConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_bool_constant(self, expr: awst_nodes.BoolConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_bytes_constant(self, expr: awst_nodes.BytesConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_string_constant(self, expr: awst_nodes.StringConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_void_constant(self, expr: awst_nodes.VoidConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_address_constant(self, expr: awst_nodes.AddressConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_compiled_contract(self, expr: awst_nodes.CompiledContract) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_compiled_logicsig(self, expr: awst_nodes.CompiledLogicSig) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_size_of(self, expr: awst_nodes.SizeOf) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_numeric_comparison_expression(
        self, expr: awst_nodes.NumericComparisonExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_intrinsic_call(self, expr: awst_nodes.IntrinsicCall) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_puya_lib_call(self, expr: awst_nodes.PuyaLibCall) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_group_transaction_reference(
        self, expr: awst_nodes.GroupTransactionReference
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_create_inner_transaction(
        self, expr: awst_nodes.CreateInnerTransaction
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_update_inner_transaction(
        self, expr: awst_nodes.UpdateInnerTransaction
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_assert_expression(self, expr: awst_nodes.AssertExpression) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_arc4_decode(self, expr: awst_nodes.ARC4Decode) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_arc4_encode(self, expr: awst_nodes.ARC4Encode) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_array_concat(self, expr: awst_nodes.ArrayConcat) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_array_extend(self, expr: awst_nodes.ArrayExtend) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_index_expression(self, expr: awst_nodes.IndexExpression) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_conditional_expression(
        self, expr: awst_nodes.ConditionalExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_app_state_expression(
        self, expr: awst_nodes.AppStateExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_new_array(self, expr: awst_nodes.NewArray) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_array_length(self, expr: awst_nodes.ArrayLength) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_new_struct(self, expr: awst_nodes.NewStruct) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_bytes_comparison_expression(
        self, expr: awst_nodes.BytesComparisonExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_subroutine_call_expression(
        self, expr: awst_nodes.SubroutineCallExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_bytes_binary_operation(
        self, expr: awst_nodes.BytesBinaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_boolean_binary_operation(
        self, expr: awst_nodes.BooleanBinaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_uint64_unary_operation(
        self, expr: awst_nodes.UInt64UnaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_bytes_unary_operation(
        self, expr: awst_nodes.BytesUnaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_not_expression(self, expr: awst_nodes.Not) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_enumeration(self, expr: awst_nodes.Enumeration) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_method_constant(self, expr: awst_nodes.MethodConstant) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_array_pop(self, expr: awst_nodes.ArrayPop) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_array_replace(self, expr: awst_nodes.ArrayReplace) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_copy(self, expr: awst_nodes.Copy) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_reversed(self, expr: awst_nodes.Reversed) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_state_get(self, expr: awst_nodes.StateGet) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_state_get_ex(self, expr: awst_nodes.StateGetEx) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_state_exists(self, expr: awst_nodes.StateExists) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_template_var(self, expr: awst_nodes.TemplateVar) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_intersection_slice_expression(
        self, expr: awst_nodes.IntersectionSliceExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_box_prefixed_key_expression(
        self, expr: awst_nodes.BoxPrefixedKeyExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_box_value_expression(
        self, expr: awst_nodes.BoxValueExpression
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_uint64_postfix_unary_operation(
        self, expr: awst_nodes.UInt64PostfixUnaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_biguint_postfix_unary_operation(
        self, expr: awst_nodes.BigUIntPostfixUnaryOperation
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_arc4_router(self, expr: awst_nodes.ARC4Router) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_range(self, expr: awst_nodes.Range) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_emit(self, expr: awst_nodes.Emit) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    @typing.override
    def visit_inner_transaction_field(
        self, expr: awst_nodes.InnerTransactionField
    ) -> list[_SourceAction]:
        return self._empty_actions_from_wtype(expr)

    # endregion


def _get_uint64_const(expr: awst_nodes.Expression) -> int | None:
    if isinstance(expr, awst_nodes.IntegerConstant) and expr.wtype == wtypes.uint64_wtype:
        return expr.value
    return None


def _is_last_itxn(expr: awst_nodes.Expression) -> bool:
    # is last itxn if expr is a submit expr of size 1 OR
    if not isinstance(expr, awst_nodes.TupleItemExpression | awst_nodes.FieldExpression):
        return _is_submit_expr_of_size(expr, 1)

    # if expr is a tuple item expression with an index into the last item of a submit expr
    base = expr.base
    if not isinstance(base.wtype, wtypes.WTuple):
        return False

    index = (
        expr.index
        if isinstance(expr, awst_nodes.TupleItemExpression)
        else base.wtype.name_to_index(expr.name, expr.source_location)
    )
    tuple_size = len(base.wtype.types)
    if index == -1 or (index + 1) == tuple_size:
        return _is_submit_expr_of_size(base, tuple_size)
    else:
        return False


def _is_submit_expr_of_size(expr: awst_nodes.Expression, expected_group_size: int) -> bool:
    match expr:
        case awst_nodes.SubmitInnerTransaction(itxns=itxns) if len(itxns) == expected_group_size:
            return True
        case awst_nodes.SingleEvaluation(source=source):
            return _is_submit_expr_of_size(source, expected_group_size)
        case _:
            return False


def _get_txn_field_var_name(var_name: str, field: str) -> str:
    return f"{var_name}.{field}"


def _get_txn_is_last(var_name: str) -> str:
    return f"{var_name}._is_last"


def _get_tuple_items[T](
    *,
    tuple_values: Sequence[T],
    tuple_wtype: wtypes.WTuple,
    index: int | tuple[int, int | None],
) -> Sequence[T]:
    if isinstance(index, tuple):
        skip_values = sum_wtypes_arity(tuple_wtype.types[: index[0]])
        target_arity = sum_wtypes_arity(tuple_wtype.types[index[0] : index[1]])
    else:
        skip_values = sum_wtypes_arity(tuple_wtype.types[:index])
        target_arity = get_wtype_arity(tuple_wtype.types[index])

    return tuple_values[skip_values : skip_values + target_arity]
