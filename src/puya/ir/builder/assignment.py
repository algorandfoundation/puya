import typing
from collections.abc import Callable, Sequence

import attrs

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import sequence, storage, tup
from puya.ir.builder._tuple_util import build_tuple_registers
from puya.ir.builder._utils import assign, assign_targets, get_implicit_return_is_original
from puya.ir.context import IRFunctionBuildContext
from puya.ir.types_ import PrimitiveIRType, get_wtype_arity
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


@attrs.frozen
class _ConstantIndexOperand:
    index: int
    source_location: SourceLocation
    field_name: str | None = None


_IndexOp = awst_nodes.IndexExpression | awst_nodes.FieldExpression | awst_nodes.TupleItemExpression


def _extract_write_path(target: _IndexOp) -> tuple[awst_nodes.Expression, list[_IndexOp]]:
    indexes = list[_IndexOp]()
    base: awst_nodes.Expression = target
    while isinstance(base, _IndexOp):
        indexes.append(base)
        base = base.base
    indexes.reverse()
    return base, indexes


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
        case awst_nodes.TupleExpression():
            results = list[ir.Value]()
            for item in target.items:
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
                        assignment_location=assignment_location,
                        is_nested_update=is_nested_update,
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
                ir.Intrinsic(
                    op=AVMOp.box_put,
                    args=[key_value, encode_result],
                    source_location=assignment_location,
                )
            )
            return source
        case maybe_index_op if isinstance(maybe_index_op, _IndexOp):
            base_target, index_src_ops = _extract_write_path(target)
            base_eval = context.visitor.visit_and_materialise_as_value_or_tuple(
                base_target, "update_assignment_current_base_value"
            )
            path_values = [base_eval]
            # index_evals = list[ir.Value | _ConstantIndexOperand]()
            update_funcs = list[Callable[[ir.MultiValue, ir.MultiValue], ir.MultiValue]]()
            for index_src_op in index_src_ops:
                match index_src_op:
                    case awst_nodes.IndexExpression():
                        seq_builder = sequence.get_builder(
                            context, index_src_op.base.wtype, index_src_op.base.source_location
                        )
                        index_value = context.visitor.visit_and_materialise_single(
                            index_src_op.index, "index"
                        )
                        assert isinstance(path_values[-1], ir.Value)
                        next_value = seq_builder.read_at_index(path_values[-1], index_value)
                        # index_evals.append(index_value)
                        # fmt: off
                        updater = lambda arr, new_val, seq_builder=seq_builder, index_value=index_value: seq_builder.write_at_index(arr, index_value, new_val)
                        # fmt: on
                        update_funcs.append(updater)
                    case awst_nodes.TupleItemExpression(index=index_int):
                        tup_builder = tup.get_builder(
                            context, index_src_op.base.wtype, index_src_op.base.source_location
                        )
                        next_value = tup_builder.read_at_index(path_values[-1], index_int)
                        # index_evals.append(
                        #     _ConstantIndexOperand(
                        #         index=index_int, source_location=index_src_op.source_location
                        #     )
                        # )
                        # fmt: off
                        updater = lambda tup, new_val, tup_builder=tup_builder, index_int=index_int: tup_builder.write_at_index(tup, index_int, new_val)
                        # fmt: on
                        update_funcs.append(updater)
                    case awst_nodes.FieldExpression():
                        match index_src_op.base.wtype:
                            case wtypes.ARC4Struct(names=names):
                                pass
                            case wtypes.WTuple(names=[*names]):
                                pass
                            case unimplemented:
                                raise InternalError(
                                    f"unimplemented field expression to index conversion for wtype: {unimplemented}",
                                    target.source_location,
                                )
                        index_int = names.index(index_src_op.name)
                        tup_builder = tup.get_builder(
                            context, index_src_op.base.wtype, index_src_op.base.source_location
                        )
                        next_value = tup_builder.read_at_index(path_values[-1], index_int)
                        # fmt: off
                        updater = lambda tup, new_val, tup_builder=tup_builder, index_int=index_int: tup_builder.write_at_index(tup, index_int, new_val)
                        # fmt: on
                        update_funcs.append(updater)
                        # index_evals.append(
                        #     _ConstantIndexOperand(
                        #         index=index_int, source_location=index_src_op.source_location
                        #     )
                        # )
                    case unexpected:
                        typing.assert_never(unexpected)
                path_values.append(next_value)

            path_values.pop()  # the last one is the value we're replacing...
            new_value = value
            for path_val, updater2 in reversed(list(zip(path_values, update_funcs, strict=True))):
                new_value = updater2(path_val, new_value)
            handle_assignment(
                context, base_target, new_value, assignment_location, is_nested_update=True
            )
            return source

            # a.b.c.d = x
            # tmp_a = a
            # tmp_b = tmp_a.b
            # tmp_c = tmp_b.c
            # new_c = replace(tmp_c, "d", x)
            # new_b = replace(tmp_b, "c", new_c)
            # new_a = replace(tmp_a, "b", new_b)
            # a = new_a

        case _:
            raise CodeError(
                "expression is not valid as an assignment target", target.source_location
            )
    #
    # match target:
    #     case awst_nodes.TupleItemExpression(
    #         base=awst_nodes.Expression(wtype=wtypes.ARC4Tuple() as tuple_wtype) as base_expr,
    #         index=index_int,
    #     ):
    #         base = context.visitor.visit_and_materialise_single(base_expr, "base")
    #
    #         tup_builder = tup.get_builder(context, tuple_wtype, assignment_location)
    #         item4 = tup_builder.write_at_index(base, index_int, value)
    #
    #         handle_assignment(
    #             context,
    #             target=base_expr,
    #             value=item4,
    #             assignment_location=assignment_location,
    #             is_nested_update=True,
    #         )
    #         return source
    #     case awst_nodes.IndexExpression(
    #         base=awst_nodes.Expression(wtype=sequence_wtype) as base_expr, index=index_value
    #     ):
    #         array_or_slot = context.visitor.visit_and_materialise_single(base_expr)
    #         index = context.visitor.visit_and_materialise_single(index_value)
    #         builder = sequence.get_builder(context, sequence_wtype, assignment_location)
    #         if isinstance(sequence_wtype, wtypes.ReferenceArray):
    #             array = mem.read_slot(context, array_or_slot, assignment_location)
    #             array_contents = builder.write_at_index(array, index, value)
    #             (array_contents,) = context.visitor.materialise_value_provider(
    #                 array_contents, "array_contents"
    #             )
    #             mem.write_slot(context, array_or_slot, array_contents, assignment_location)
    #             return source
    #         elif isinstance(sequence_wtype, wtypes.ARC4Array):
    #             array_contents = builder.write_at_index(array_or_slot, index, value)
    #             handle_assignment(
    #                 context,
    #                 target=base_expr,
    #                 value=array_contents,
    #                 assignment_location=assignment_location,
    #                 is_nested_update=True,
    #             )
    #             return source
    #         else:
    #             raise InternalError(
    #                 f"Indexed assignment operation IR lowering"
    #                 f" not implemented for base type {base_expr.wtype.name}",
    #                 assignment_location,
    #             )
    #     case awst_nodes.FieldExpression(
    #         base=awst_nodes.Expression(wtype=wtypes.ARC4Struct() as struct_wtype) as base_expr,
    #         name=field_name,
    #     ):
    #         base = context.visitor.visit_and_materialise_single(base_expr, "base")
    #         index_int = struct_wtype.names.index(field_name)
    #
    #         tup_builder = tup.get_builder(context, struct_wtype, assignment_location)
    #         item3 = tup_builder.write_at_index(base, index_int, value)
    #
    #         handle_assignment(
    #             context,
    #             target=base_expr,
    #             value=item3,
    #             assignment_location=assignment_location,
    #             is_nested_update=True,
    #         )
    #         return source
    #     # special case: a nested update can cause a tuple item to be re-assigned
    #     # TODO: refactor this so that this special case is handled where it originates
    #     case (
    #         awst_nodes.TupleItemExpression(wtype=var_type, source_location=var_loc)
    #         | awst_nodes.FieldExpression(wtype=var_type, source_location=var_loc)
    #     ) if (
    #         # including assumptions in condition, so assignment will error if they are not true
    #         not var_type.immutable  # mutable arc4 type
    #         and is_nested_update  # is a reassignment due to a nested update
    #         and var_type.scalar_type is not None  # only updating a scalar value
    #     ):
    #         base_name = _get_tuple_var_name(target, assignment_location)
    #         return _handle_maybe_implicit_return_assignment(
    #             context,
    #             base_name=base_name,
    #             wtype=var_type,
    #             value=value,
    #             var_loc=var_loc,
    #             assignment_loc=assignment_location,
    #             is_nested_update=is_nested_update,
    #         )
    #     case awst_nodes.FieldExpression() as field_expr:
    #         raise InternalError(
    #             f"Field assignment operation IR lowering"
    #             f" not implemented for base type {field_expr.base.wtype.name}",
    #             assignment_location,
    #         )
    #
    #     # case awst_nodes.TupleExpression() as tup_expr:
    #     #     results = list[ir.Value]()
    #     #     for item in tup_expr.items:
    #     #         arity = get_wtype_arity(item.wtype)
    #     #         values = source[:arity]
    #     #         del source[:arity]
    #     #         if len(values) != arity:
    #     #             raise CodeError("not enough values to unpack", assignment_location)
    #     #         if arity == 1:
    #     #             nested_value: ir.MultiValue = values[0]
    #     #         else:
    #     #             nested_value = ir.ValueTuple(
    #     #                 values=values, source_location=value.source_location
    #     #             )
    #     #         results.extend(
    #     #             handle_assignment(
    #     #                 context,
    #     #                 target=item,
    #     #                 value=nested_value,
    #     #                 is_nested_update=False,
    #     #                 assignment_location=assignment_location,
    #     #             )
    #     #         )
    #     #     if source:
    #     #         raise CodeError("too many values to unpack", assignment_location)
    #     #     return results
    #
    #     case _:
    #         raise CodeError(
    #             "expression is not valid as an assignment target", target.source_location
    #         )


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


def _get_tuple_var_name(
    expr: awst_nodes.TupleItemExpression | awst_nodes.FieldExpression, ass_loc: SourceLocation
) -> str:
    if isinstance(expr.base.wtype, wtypes.WTuple):
        if isinstance(expr, awst_nodes.TupleItemExpression):
            name_or_index: str | int = expr.index
        else:
            typing.assert_type(expr, awst_nodes.FieldExpression)
            name_or_index = expr.name
        if isinstance(expr.base, awst_nodes.FieldExpression):
            return format_tuple_index(
                expr.base.wtype, _get_tuple_var_name(expr.base, ass_loc), name_or_index
            )
        if isinstance(expr.base, awst_nodes.TupleItemExpression):
            return format_tuple_index(
                expr.base.wtype, _get_tuple_var_name(expr.base, ass_loc), name_or_index
            )
        if isinstance(expr.base, awst_nodes.VarExpression):
            return format_tuple_index(expr.base.wtype, expr.base.name, name_or_index)
        if isinstance(expr.base, awst_nodes.StorageExpression):
            raise CodeError(
                "updating mutable elements within a tuple in storage is not supported", ass_loc
            )
    raise CodeError("invalid assignment target", expr.base.source_location)
