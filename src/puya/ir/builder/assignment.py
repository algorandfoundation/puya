from collections.abc import Iterator, Sequence

import attrs

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import sequence, storage
from puya.ir.builder._tuple_util import build_tuple_registers
from puya.ir.builder._utils import assign, assign_targets, get_implicit_return_is_original
from puya.ir.context import IRFunctionBuildContext
from puya.ir.types_ import PrimitiveIRType, SlotType, get_wtype_arity
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def handle_assignment_expr(
    context: IRFunctionBuildContext,
    target: awst_nodes.Lvalue,
    value: awst_nodes.Expression,
    assignment_location: SourceLocation,
) -> Sequence[ir.Value]:
    # as per AWST node Value is evaluated before the target
    expr_values = context.visitor.visit_and_materialise_as_value_or_tuple(value)
    return handle_assignment(
        context,
        target=target,
        value=expr_values,
        is_nested_update=False,
        assignment_location=assignment_location,
    )


def handle_assignment(
    context: IRFunctionBuildContext,
    target: awst_nodes.Expression,
    value: ir.MultiValue,
    assignment_location: SourceLocation,
    *,
    is_nested_update: bool,
) -> Sequence[ir.Value]:
    source = list(value.values) if isinstance(value, ir.ValueTuple) else [value]
    match target:
        case awst_nodes.TupleExpression() as tup_expr:
            assert not is_nested_update, "tuple literal item assignment is not supported"
            results = list[ir.Value]()
            for item in tup_expr.items:
                arity = get_wtype_arity(item.wtype)
                values = source[:arity]
                del source[:arity]
                if len(values) != arity:
                    raise CodeError("not enough values to unpack", assignment_location)
                if arity == 1:
                    nested_value: ir.MultiValue = values[0]
                else:
                    nested_value = ir.ValueTuple(
                        values=values, source_location=value.source_location
                    )
                results.extend(
                    handle_assignment(
                        context,
                        target=item,
                        value=nested_value,
                        is_nested_update=is_nested_update,
                        assignment_location=assignment_location,
                    )
                )
            if source:
                raise CodeError("too many values to unpack", assignment_location)
            return results
        case awst_nodes.VarExpression(name=base_name, source_location=var_loc, wtype=var_type):
            return _handle_maybe_implicit_return_assignment(
                context,
                base_name=base_name,
                wtype=var_type,
                value=value,
                var_loc=var_loc,
                assignment_loc=assignment_location,
                is_nested_update=is_nested_update,
            )
        case awst_nodes.AppStateExpression(
            key=awst_key, wtype=wtype, source_location=field_location
        ):
            key_value = context.visitor.visit_and_materialise_single(awst_key)
            codec = storage.get_storage_codec(
                wtype, awst_nodes.AppStorageKind.app_global, field_location
            )
            encode_result = codec.encode(context, source, field_location)
            context.block_builder.add(
                ir.Intrinsic(
                    op=AVMOp.app_global_put,
                    args=[key_value, encode_result],
                    source_location=assignment_location,
                )
            )
            return source
        case awst_nodes.AppAccountStateExpression(
            key=awst_key, account=account_expr, wtype=wtype, source_location=field_location
        ):
            key_value = context.visitor.visit_and_materialise_single(awst_key)
            account = context.visitor.visit_and_materialise_single(account_expr)
            codec = storage.get_storage_codec(
                wtype, awst_nodes.AppStorageKind.account_local, field_location
            )
            encode_result = codec.encode(context, source, field_location)
            context.block_builder.add(
                ir.Intrinsic(
                    op=AVMOp.app_local_put,
                    args=[account, key_value, encode_result],
                    source_location=assignment_location,
                )
            )
            return source
        case awst_nodes.BoxValueExpression(
            key=awst_key, wtype=wtype, source_location=field_location
        ):
            key_value = context.visitor.visit_and_materialise_single(awst_key)
            codec = storage.get_storage_codec(wtype, awst_nodes.AppStorageKind.box, field_location)
            # del box first if size is dynamic
            if codec.encoded_ir_type.num_bytes is None:
                context.block_builder.add(
                    ir.Intrinsic(
                        op=AVMOp.box_del, args=[key_value], source_location=assignment_location
                    )
                )
            encode_result = codec.encode(context, source, field_location)
            context.block_builder.add(
                ir.BoxWrite(
                    key=key_value,
                    value=encode_result,
                    source_location=assignment_location,
                )
            )
            return source
        case maybe_index_op if isinstance(maybe_index_op, _IndexOp):
            base_target, index_src_ops = _extract_write_path(target)
            base_eval = context.visitor.visit_and_materialise_as_value_or_tuple(
                base_target, "update_assignment_current_base_value"
            )

            if not index_src_ops:
                new_value = value
            else:
                indexes = _get_indexes(context, index_src_ops)
                base_wtype = base_target.wtype
                assert isinstance(
                    base_wtype,
                    wtypes.WTuple
                    | wtypes.ARC4Array
                    | wtypes.ARC4Tuple
                    | wtypes.ARC4Struct
                    | wtypes.ReferenceArray,
                )
                new_value = sequence.encode_and_write_aggregate_index(
                    context,
                    base_wtype,
                    base_eval,
                    indexes,
                    source,
                    assignment_location,
                )
            if isinstance(base_target, awst_nodes.VarExpression | awst_nodes.StorageExpression):
                handle_assignment(
                    context, base_target, new_value, assignment_location, is_nested_update=True
                )
            elif isinstance(base_eval, ir.Value) and isinstance(base_eval.ir_type, SlotType):
                logger.debug("base assignment target is in a slot", location=assignment_location)
            else:
                logger.error("unsupported assignment target", location=assignment_location)
            return source
        case _:
            raise CodeError(
                "expression is not valid as an assignment target", target.source_location
            )


_IndexOp = awst_nodes.IndexExpression | awst_nodes.FieldExpression | awst_nodes.TupleItemExpression


def _extract_write_path(target: _IndexOp) -> tuple[awst_nodes.Expression, list[_IndexOp]]:
    indexes = list[_IndexOp]()
    base: awst_nodes.Expression = target
    while isinstance(base, _IndexOp):
        indexes.append(base)
        base = base.base
    # special case: we currently explode native tuples during IR construction
    if isinstance(base, awst_nodes.VarExpression):
        while indexes and isinstance(base.wtype, wtypes.WTuple):
            tuple_index_op = indexes.pop()
            match tuple_index_op:
                case awst_nodes.TupleItemExpression(index=index_or_name):
                    pass
                case awst_nodes.FieldExpression(name=index_or_name):
                    pass
                case _:
                    raise InternalError(
                        "unexpected tuple indexing expression", tuple_index_op.source_location
                    )
            new_name = format_tuple_index(base.wtype, base.name, index_or_name)
            new_wtype = tuple_index_op.wtype
            new_loc = base.source_location.try_merge(tuple_index_op.source_location)
            base = awst_nodes.VarExpression(
                name=new_name, wtype=new_wtype, source_location=new_loc
            )
    indexes.reverse()
    return base, indexes


@attrs.frozen(kw_only=True)
class _ArrayIndex:
    base_wtype: wtypes.ARC4Array | wtypes.ReferenceArray
    source_location: SourceLocation
    index: ir.Value

    def read(self, context: IRFunctionBuildContext, array: ir.MultiValue) -> ir.MultiValue:
        arr = _multi_value_to_values(array)
        next_value = sequence.read_aggregate_index_and_decode(
            context, self.base_wtype, arr, [self.index], self.source_location
        )
        return next_value

    def write(
        self, context: IRFunctionBuildContext, array: ir.MultiValue, new_value: ir.MultiValue
    ) -> ir.Value:
        (array_or_slot,) = _multi_value_to_values(array)
        updated_array = sequence.encode_and_write_aggregate_index(
            context,
            self.base_wtype,
            array_or_slot,
            [self.index],
            values=_multi_value_to_values(new_value),
            loc=self.source_location,
        )
        assert isinstance(updated_array, ir.Value)
        return updated_array


@attrs.frozen(kw_only=True)
class _TupleOrStructIndex:
    base_wtype: wtypes.ARC4Tuple | wtypes.ARC4Struct | wtypes.WTuple
    source_location: SourceLocation
    index: int
    field_name: str | None = None

    def read(self, context: IRFunctionBuildContext, tup: ir.MultiValue) -> ir.MultiValue:
        tuple_values = _multi_value_to_values(tup)
        next_value = sequence.read_aggregate_index_and_decode(
            context,
            self.base_wtype,
            tuple_values,
            [self.index],
            self.source_location,
        )
        return next_value

    def write(
        self, context: IRFunctionBuildContext, tup: ir.MultiValue, new_value: ir.MultiValue
    ) -> ir.MultiValue:
        return sequence.encode_and_write_aggregate_index(
            context,
            self.base_wtype,
            tup,
            [self.index],
            values=_multi_value_to_values(new_value),
            loc=self.source_location,
        )


def _multi_value_to_values(value: ir.MultiValue) -> Sequence[ir.Value]:
    if isinstance(value, ir.Value):
        return [value]
    return value.values


def _get_indexes(
    context: IRFunctionBuildContext, index_src_ops: Sequence[_IndexOp]
) -> list[int | ir.Value]:
    indexes = list[int | ir.Value]()
    for index_src_op in index_src_ops:
        match index_src_op, index_src_op.base.wtype:
            case (
                awst_nodes.IndexExpression(),
                (wtypes.ARC4Array() | wtypes.ReferenceArray()),
            ):
                index_value = context.visitor.visit_and_materialise_single(
                    index_src_op.index, "index"
                )
                indexes.append(index_value)
            case (
                awst_nodes.TupleItemExpression(index=index_int),
                (wtypes.ARC4Tuple() | wtypes.WTuple()),
            ):
                indexes.append(index_int)
            case (
                awst_nodes.FieldExpression(),
                (wtypes.ARC4Struct(names=names) | wtypes.WTuple(names=[*names])),
            ):
                index_int = names.index(index_src_op.name)
                indexes.append(index_int)
            case unimplemented, for_type:
                raise InternalError(
                    f"unimplemented index write operation {type(unimplemented).__name__}"
                    f" for wtype: {for_type}",
                    index_src_op.source_location,
                )
    return indexes


def _materialize_index_ops(
    context: IRFunctionBuildContext, index_src_ops: Sequence[_IndexOp]
) -> Iterator[_ArrayIndex | _TupleOrStructIndex]:
    for index_src_op in index_src_ops:
        match index_src_op, index_src_op.base.wtype:
            case (
                awst_nodes.IndexExpression(),
                (wtypes.ARC4Array() | wtypes.ReferenceArray() as array_wtype),
            ):
                index_value = context.visitor.visit_and_materialise_single(
                    index_src_op.index, "index"
                )
                yield _ArrayIndex(
                    base_wtype=array_wtype,
                    source_location=index_src_op.source_location,
                    index=index_value,
                )
            case (
                awst_nodes.TupleItemExpression(index=index_int),
                (wtypes.ARC4Tuple() | wtypes.WTuple() as tuple_wtype),
            ):
                yield _TupleOrStructIndex(
                    base_wtype=tuple_wtype,
                    source_location=index_src_op.source_location,
                    index=index_int,
                    field_name=None,
                )
            case (
                awst_nodes.FieldExpression(),
                (wtypes.ARC4Struct(names=names) | wtypes.WTuple(names=[*names])) as structy_wtype,
            ):
                index_int = names.index(index_src_op.name)
                yield _TupleOrStructIndex(
                    base_wtype=structy_wtype,
                    source_location=index_src_op.source_location,
                    index=index_int,
                    field_name=index_src_op.name,
                )
            case unimplemented, for_type:
                raise InternalError(
                    f"unimplemented index write operation {type(unimplemented).__name__}"
                    f" for wtype: {for_type}",
                    index_src_op.source_location,
                )


def _handle_maybe_implicit_return_assignment(
    context: IRFunctionBuildContext,
    *,
    base_name: str,
    wtype: wtypes.WType,
    value: ir.ValueProvider,
    var_loc: SourceLocation,
    assignment_loc: SourceLocation,
    is_nested_update: bool,
) -> Sequence[ir.Value]:
    registers = build_tuple_registers(context, base_name, wtype, var_loc)
    for register in registers:
        is_implicit_return = register.name in (
            p.name for p in context.subroutine.parameters if p.implicit_return
        )
        # if an implicitly returned value is explicitly reassigned, then set a register which will
        # prevent the original from being updated any further
        if is_implicit_return and not is_nested_update:
            assign(
                context,
                ir.UInt64Constant(value=0, ir_type=PrimitiveIRType.bool, source_location=None),
                name=get_implicit_return_is_original(register.name),
                assignment_location=None,
            )

    assign_targets(
        context,
        source=value,
        targets=registers,
        assignment_location=assignment_loc,
    )
    return registers
