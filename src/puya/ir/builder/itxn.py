import typing
from collections.abc import Mapping, Sequence

import attrs

from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder.blocks import BlocksBuilder
from puya.ir.builder.utils import assign, assign_intrinsic_op
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    BasicBlock,
    ConditionalBranch,
    Intrinsic,
    Register,
    UInt64Constant,
    ValueProvider,
    ValueTuple,
)
from puya.ir.ssa import BraunSSA
from puya.ir.types_ import wtype_to_avm_type
from puya.parse import SourceLocation


@attrs.frozen(kw_only=True)
class SubmitInnerTransactionData:
    group_index: int
    is_last_in_group: bool
    submit_id: int
    var_name: str


@attrs.frozen(kw_only=True)
class CreateInnerTransactionFieldData:
    var_name: str
    field: awst_nodes.TxnField
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
    fields: dict[awst_nodes.TxnField, CreateInnerTransactionFieldData] = attrs.field(
        factory=dict, init=False
    )

    def get_or_add_field_data(self, field: awst_nodes.TxnField) -> CreateInnerTransactionFieldData:
        try:
            field_data = self.fields[field]
        except KeyError:
            field_data = self.fields[field] = CreateInnerTransactionFieldData(
                var_name=self.var_name,
                field=field,
                field_count_register_name=f"{self.var_name}%%{field.immediate}_length",
            )
        return field_data


INNER_TRANSACTION_SUBMIT_ID_NAME = "%%inner_txn_submit_id"


class InnerTransactionBuilder:
    def __init__(self, context: IRFunctionBuildContext):
        self.context = context
        self._inner_txn_params_data = dict[str, CreateInnerTransactionData]()
        self._inner_txn_submit_data = dict[str, SubmitInnerTransactionData]()
        self._last_submit_id = 0

    @property
    def ssa(self) -> BraunSSA:
        return self.context.block_builder.ssa

    @property
    def block_builder(self) -> BlocksBuilder:
        return self.context.block_builder

    def handle_inner_transaction_assignments(self, stmt: awst_nodes.AssignmentStatement) -> bool:
        """Performs special handling for inner transaction related assignments

        Returns True if assignment was handled, False otherwise"""
        if isinstance(stmt.value, awst_nodes.SubmitInnerTransaction):
            num_inner_txns = len(stmt.value.itxns)
            match stmt.target:
                case awst_nodes.VarExpression(name=var_name) if num_inner_txns == 1:
                    names = [var_name]
                case awst_nodes.TupleExpression(items=items) if num_inner_txns == len(
                    items
                ) and all(isinstance(i, awst_nodes.VarExpression) for i in items):
                    items = typing.cast(Sequence[awst_nodes.VarExpression], items)
                    names = [expr.name for expr in items]
                case _:
                    raise CodeError(
                        "Inner Transactions can only be assigned to local variables",
                        stmt.source_location,
                    )
            self.handle_submit_inner_transaction(stmt.value, names)
        elif isinstance(stmt.value.wtype, wtypes.WInnerTransactionFields):
            match stmt.target:
                case awst_nodes.VarExpression(name=var_name, source_location=var_loc):
                    pass
                case awst_nodes.TemporaryVariable(source_location=var_loc) as tmp:
                    var_name = self.context.get_awst_tmp_name(tmp)
                case _:
                    raise CodeError(
                        "Inner Transaction params can only be assigned to (non-tuple) variables",
                        stmt.source_location,
                    )
            match stmt.value:
                case awst_nodes.CreateInnerTransaction(fields=fields):
                    self._set_inner_transaction_fields(var_name, fields, var_loc)
                case awst_nodes.Copy(value=value):
                    src_var_name = self._resolve_inner_txn_params_var_name(value)
                    self._copy_inner_transaction_fields(var_name, src_var_name, var_loc)
                case _:
                    raise CodeError(
                        "Inner Transaction params can only be reassigned using copy()",
                        stmt.source_location,
                    )

        elif isinstance(
            stmt.value.wtype, (wtypes.WInnerTransaction, wtypes.WInnerTransactionFields)
        ):
            raise CodeError(
                "Inner Transactions cannot be reassigned",
                stmt.source_location,
            )
        else:
            return False
        return True

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
        submit_data = self._resolve_itxn_group_index(itxn_field.itxn)
        var_name = submit_data.var_name
        group_txn_index = submit_data.group_index

        if field.is_array:
            if itxn_field.array_index is None:
                raise InternalError("expected array_index expression", itxn_field.source_location)
            self._assert_submit_id_is_correct(var_name, submit_data.submit_id, src_loc)
            array_index = self.context.visitor.visit_and_materialise_single(itxn_field.array_index)
            return (
                Intrinsic(
                    op=AVMOp.itxnas,
                    immediates=[field.immediate],
                    args=[array_index],
                    source_location=src_loc,
                )
                if submit_data.is_last_in_group
                else Intrinsic(
                    op=AVMOp.gitxnas,
                    immediates=[group_txn_index, field.immediate],
                    args=[array_index],
                    source_location=src_loc,
                )
            )
        field_var_name = get_inner_txn_field_name(var_name, field.immediate)
        return self.ssa.read_variable(
            field_var_name, wtype_to_avm_type(field.wtype), self.block_builder.active_block
        )

    def handle_submit_inner_transaction(
        self,
        submit: awst_nodes.SubmitInnerTransaction,
        submit_var_names: Sequence[str] | None = None,
    ) -> tuple[SubmitInnerTransactionData, ...]:
        src_loc = submit.source_location
        self.block_builder.add(
            Intrinsic(
                op=AVMOp.itxn_begin,
                source_location=src_loc,
            )
        )
        self._last_submit_id += 1
        result = list[SubmitInnerTransactionData]()
        num_inner_txns = len(submit.itxns)
        last_group_index = num_inner_txns - 1
        if submit_var_names is None:
            submit_var_names = [
                self.context.next_tmp_name(f"submit_result_{i}") for i in range(num_inner_txns)
            ]
        for group_index, (submit_var_name, param) in enumerate(
            zip(submit_var_names, submit.itxns, strict=True)
        ):
            if group_index > 0:
                self.block_builder.add(
                    Intrinsic(
                        op=AVMOp.itxn_next,
                        source_location=src_loc,
                    )
                )
            param_var_name = self._resolve_inner_txn_params_var_name(param)
            next_txn = BasicBlock(comment="next_txn", source_location=submit.source_location)
            param_data = self._inner_txn_params_data[param_var_name]

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
                next_field = BasicBlock(comment="next_field", source_location=src_loc)
                self._set_field_values(field_data, 0, min_num_values)

                if remaining_values:
                    last_num_values = min_num_values
                    for next_num_values in remaining_values:
                        set_fields_blk = BasicBlock(
                            comment=f"set_{field.immediate}_{last_num_values}_to_{next_num_values-1}",
                            source_location=src_loc,
                        )
                        self.block_builder.terminate(
                            ConditionalBranch(
                                condition=self._get_is_field_count_gte(
                                    field_data, next_num_values
                                ),
                                non_zero=set_fields_blk,
                                zero=next_field,
                                source_location=None,
                            )
                        )
                        self.ssa.seal_block(set_fields_blk)

                        self.block_builder.activate_block(set_fields_blk)
                        self._set_field_values(field_data, last_num_values, next_num_values)
                        last_num_values = next_num_values

                    self.block_builder.goto_and_activate(next_field)
                    self.ssa.seal_block(next_field)
            submit_data = SubmitInnerTransactionData(
                group_index=group_index,
                is_last_in_group=group_index == last_group_index,
                submit_id=self._last_submit_id,
                var_name=submit_var_name,
            )
            self._inner_txn_submit_data[submit_var_name] = submit_data
            result.append(submit_data)

            self.block_builder.goto_and_activate(next_txn)
            self.ssa.seal_block(next_txn)

        self.block_builder.add(
            Intrinsic(
                op=AVMOp.itxn_submit,
                source_location=src_loc,
            )
        )

        assign(
            context=self.context,
            source=UInt64Constant(
                value=self._last_submit_id, source_location=submit.source_location
            ),
            names=[(INNER_TRANSACTION_SUBMIT_ID_NAME, submit.source_location)],
            source_location=submit.source_location,
        )
        for data in result:
            self._assign_inner_txn_fields(data, submit.source_location)

        return tuple(result)

    def _set_field_values(
        self,
        field_data: CreateInnerTransactionFieldData,
        idx_from: int,
        idx_to: int,
    ) -> None:
        field = field_data.field
        field_atype = wtype_to_avm_type(field.wtype)
        for idx in range(idx_from, idx_to):
            field_value = self.ssa.read_variable(
                field_data.get_value_register_name(idx),
                field_atype,
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
            AVMType.uint64,
            self.block_builder.active_block,
        )

        (is_field_count_gte,) = assign_intrinsic_op(
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
        inner_txn_fields: Mapping[awst_nodes.TxnField, awst_nodes.Expression],
        var_loc: SourceLocation,
        *,
        update: bool = False,
    ) -> None:
        param_data = self._inner_txn_params_data.setdefault(
            var_name, CreateInnerTransactionData(var_name=var_name)
        )
        fields = (
            inner_txn_fields.keys()
            if update
            else awst_nodes.TxnFields.inner_transaction_param_fields()
        )
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
                    names=[(field_data.get_value_register_name(idx), var_loc)],
                    source_location=value.source_location,
                )
            assign(
                context=self.context,
                source=UInt64Constant(
                    value=len(values),
                    source_location=count_loc,
                ),
                names=[(field_data.field_count_register_name, var_loc)],
                source_location=count_loc,
            )

    def _copy_inner_transaction_fields(
        self, dest_var_name: str, src_var_name: str, var_loc: SourceLocation
    ) -> None:
        src_params_data = self._inner_txn_params_data[src_var_name]
        dest_params_data = self._inner_txn_params_data.setdefault(
            dest_var_name, CreateInnerTransactionData(var_name=dest_var_name)
        )
        for field in awst_nodes.TxnFields.inner_transaction_param_fields():
            src_field_data = src_params_data.get_or_add_field_data(field)

            dest_field_data = dest_params_data.get_or_add_field_data(field)
            dest_field_data.field_counts.update(src_field_data.field_counts)
            for idx, src_field_register in src_field_data.value_registers.items():
                dest_field_register = dest_field_data.get_value_register_name(idx)
                assign(
                    context=self.context,
                    source=self.ssa.read_variable(
                        src_field_register,
                        wtype_to_avm_type(field.wtype),
                        self.block_builder.active_block,
                    ),
                    names=[(dest_field_register, var_loc)],
                    source_location=var_loc,
                )
            assign(
                context=self.context,
                source=self.ssa.read_variable(
                    src_field_data.field_count_register_name,
                    AVMType.uint64,
                    self.block_builder.active_block,
                ),
                names=[(dest_field_data.field_count_register_name, var_loc)],
                source_location=var_loc,
            )

    def _assert_submit_id_is_correct(
        self, var_name: str, submit_id: int, loc: SourceLocation
    ) -> None:
        current_submit_id = self.ssa.read_variable(
            INNER_TRANSACTION_SUBMIT_ID_NAME, AVMType.uint64, self.block_builder.active_block
        )
        (submit_id_eq,) = assign_intrinsic_op(
            context=self.context,
            target=f"submit_id_is_{submit_id}",
            op=AVMOp.eq,
            args=[current_submit_id, submit_id],
            source_location=loc,
        )
        self.block_builder.add(
            Intrinsic(
                op=AVMOp.assert_,
                args=[submit_id_eq],
                comment=f"'{var_name}' can still be accessed",
                source_location=loc,
            )
        )

    def _resolve_itxn_group_index(self, expr: awst_nodes.Expression) -> SubmitInnerTransactionData:
        match expr:
            case awst_nodes.VarExpression(name=var_name):
                try:
                    return self._inner_txn_submit_data[var_name]
                except KeyError:
                    pass
            case awst_nodes.SubmitInnerTransaction() as submit:
                submit_data = self.handle_submit_inner_transaction(submit)
                try:
                    (first_submit,) = submit_data
                except ValueError as ex:
                    raise InternalError(
                        f"Expected 1 inner transaction when submitting "
                        f"got: {len(submit_data)}",
                        expr.source_location,
                    ) from ex
                return first_submit
        raise CodeError(
            f"Could not resolve inner transaction group index for {expr}",
            expr.source_location,
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
            case awst_nodes.Copy(value=value):
                return self._resolve_inner_txn_params_var_name(value)
            case _:
                raise InternalError(
                    "Could not resolve var_name for inner transaction params",
                    params.source_location,
                )
        return var_name

    def _assign_inner_txn_fields(
        self, submit_data: SubmitInnerTransactionData, source_location: SourceLocation
    ) -> None:
        for field in awst_nodes.TxnFields.inner_transaction_non_array_fields():
            register_name = get_inner_txn_field_name(submit_data.var_name, field.immediate)
            value = (
                Intrinsic(
                    op=AVMOp.itxn,
                    immediates=[field.immediate],
                    source_location=source_location,
                )
                if submit_data.is_last_in_group
                else Intrinsic(
                    op=AVMOp.gitxn,
                    immediates=[submit_data.group_index, field.immediate],
                    source_location=source_location,
                )
            )
            assign(
                context=self.context,
                source=value,
                names=[(register_name, source_location)],
                source_location=source_location,
            )


def get_inner_txn_field_name(var_name: str, field: str) -> str:
    return f"{var_name}%%{field}"
