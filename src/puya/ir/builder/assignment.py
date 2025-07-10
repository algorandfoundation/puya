from collections.abc import Sequence

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir import (
    models as ir,
    types_ as types,
)
from puya.ir._utils import multi_value_to_values
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import sequence, storage
from puya.ir.builder._utils import assign, assign_tuple, get_implicit_return_is_original
from puya.ir.context import IRFunctionBuildContext
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
    source = multi_value_to_values(value)
    match target:
        case awst_nodes.TupleExpression(items=items, wtype=wtype, source_location=loc):
            assert not is_nested_update, "tuple literal item assignment is not supported"
            tuple_ir_type = types.wtype_to_ir_type(wtype, loc, allow_tuple=True)
            assert len(items) == len(tuple_ir_type.elements), "tuple type length mismatch"
            results = list[ir.Value]()
            for item, ir_type in zip(items, tuple_ir_type.elements, strict=True):
                if not isinstance(ir_type, types.TupleIRType):
                    nested_value: ir.MultiValue = source.pop(0)
                else:
                    arity = ir_type.arity
                    values = source[:arity]
                    if len(values) != arity:
                        raise CodeError("not enough values to unpack", assignment_location)
                    del source[:arity]
                    nested_value = ir.ValueTuple(
                        values=values, ir_type=ir_type, source_location=value.source_location
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
            ir_type = types.wtype_to_ir_type(var_type, var_loc, allow_tuple=True)
            if isinstance(ir_type, types.TupleIRType):
                exploded_names = ir_type.build_item_names(base_name)
            else:
                exploded_names = [base_name]
            for exploded_name in exploded_names:
                is_implicit_return = exploded_name in (
                    p.name for p in context.subroutine.parameters if p.implicit_return
                )
                # if an implicitly returned value is explicitly reassigned, then set a register
                # which will prevent the original from being updated any further
                if is_implicit_return and not is_nested_update:
                    assign(
                        context,
                        ir.UInt64Constant(value=0, ir_type=types.bool_, source_location=None),
                        name=get_implicit_return_is_original(exploded_name),
                        assignment_location=None,
                    )
            return assign_tuple(
                context,
                source=value,
                names=exploded_names,
                ir_types=types.ir_type_to_ir_types(ir_type),
                assignment_location=assignment_location,
                register_location=var_loc,
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
            encode_result = codec.encode(context, source, field_location)
            context.block_builder.add(
                ir.BoxWrite(
                    key=key_value,
                    value=encode_result,
                    delete_first=codec.encoded_ir_type.num_bytes is None,
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
                indexes = _materialise_indexes(context, index_src_ops)
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
            elif isinstance(base_eval, ir.Value) and isinstance(base_eval.ir_type, types.SlotType):
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
    # turn the syntax tree inside out, get to the base of any repeated indexing operations,
    # and turn the tree of indexes into a linear list.
    indexes = list[_IndexOp]()
    base: awst_nodes.Expression = target
    while isinstance(base, _IndexOp):
        indexes.append(base)
        base = base.base
    # special case: we currently explode native tuples during IR construction,
    # so if the base is a var expression of WTuple type, we need to "index" it
    # by altering the base target until we reach a tuple item that is not itself of tuple type.
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
    # now that the base target is not a tuple-type, we reverse the indexes, since they were
    # collected whilst descending the tree, this puts them in order of application,
    # i.e. the op at indexes[0] should be applied to base first, and then indexes[1] should be
    # applied to that result, and so on
    indexes.reverse()
    return base, indexes


def _materialise_indexes(
    context: IRFunctionBuildContext, index_src_ops: Sequence[_IndexOp]
) -> list[int | ir.Value]:
    """Given a list of indexing operations order of application, materialize any variable-indexing
    in the semantically correct order, and also convert any field expressions to indexes."""
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
