import typing
from collections.abc import Sequence

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4, mem, storage
from puya.ir.builder._tuple_util import build_tuple_registers
from puya.ir.builder._utils import (
    assign,
    assign_targets,
    assign_temp,
    get_implicit_return_is_original,
)
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
    expr_values = context.visitor.visit_expr(value)
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
    value: ir.ValueProvider,
    assignment_location: SourceLocation,
    *,
    is_nested_update: bool,
) -> Sequence[ir.Value]:
    match target:
        # special case: a nested update can cause a tuple item to be re-assigned
        # TODO: refactor this so that this special case is handled where it originates
        case (
            awst_nodes.TupleItemExpression(wtype=var_type, source_location=var_loc)
            | awst_nodes.FieldExpression(wtype=var_type, source_location=var_loc)
        ) if (
            # including assumptions in condition, so assignment will error if they are not true
            not var_type.immutable  # mutable arc4 type
            and is_nested_update  # is a reassignment due to a nested update
            and var_type.scalar_type is not None  # only updating a scalar value
        ):
            base_name = _get_tuple_var_name(target, assignment_location)
            return _handle_maybe_implicit_return_assignment(
                context,
                base_name=base_name,
                wtype=var_type,
                value=value,
                var_loc=var_loc,
                assignment_loc=assignment_location,
                is_nested_update=is_nested_update,
            )
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
        case awst_nodes.TupleExpression() as tup_expr:
            source = context.visitor.materialise_value_provider(
                value, description="tuple_assignment"
            )
            results = list[ir.Value]()
            for item in tup_expr.items:
                arity = get_wtype_arity(item.wtype)
                values = source[:arity]
                del source[:arity]
                if len(values) != arity:
                    raise CodeError("not enough values to unpack", assignment_location)
                if arity == 1:
                    nested_value: ir.ValueProvider = values[0]
                else:
                    nested_value = ir.ValueTuple(
                        values=values, source_location=value.source_location
                    )
                results.extend(
                    handle_assignment(
                        context,
                        target=item,
                        value=nested_value,
                        is_nested_update=False,
                        assignment_location=assignment_location,
                    )
                )
            if source:
                raise CodeError("too many values to unpack", assignment_location)
            return results
        case awst_nodes.AppStateExpression(
            key=awst_key, wtype=wtype, source_location=field_location
        ):
            source = context.visitor.materialise_value_provider(value, "materialized_values")
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
            source = context.visitor.materialise_value_provider(value, "materialized_values")
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
            source = context.visitor.materialise_value_provider(value, "materialized_values")
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
        case awst_nodes.IndexExpression() as ix_expr:
            if isinstance(ix_expr.base.wtype, wtypes.ReferenceArray):
                values = context.visitor.materialise_value_provider(
                    value, description="materialized_values"
                )
                array_slot = context.visitor.visit_and_materialise_single(
                    ix_expr.base, "array_slot"
                )
                index = context.visitor.visit_and_materialise_single(ix_expr.index, "index")
                array = mem.read_slot(context, array_slot, ix_expr.source_location)
                element: ir.ValueTuple | ir.Value
                try:
                    (element,) = values
                except ValueError:
                    element = ir.ValueTuple(values=values, source_location=value.source_location)
                updated_array_vp = ir.ArrayWriteIndex(
                    array=array,
                    index=index,
                    value=element,
                    source_location=ix_expr.source_location,
                )
                updated_array = assign_temp(
                    context,
                    updated_array_vp,
                    temp_description="updated_array",
                    source_location=value.source_location,
                )
                mem.write_slot(context, array_slot, updated_array, ix_expr.source_location)
                return values
            elif isinstance(ix_expr.base.wtype, wtypes.ARC4Type):
                return (
                    arc4.handle_arc4_assign(
                        context,
                        target=ix_expr,
                        value=value,
                        is_nested_update=is_nested_update,
                        source_location=assignment_location,
                    ),
                )
            else:
                raise InternalError(
                    f"Indexed assignment operation IR lowering"
                    f" not implemented for base type {ix_expr.base.wtype.name}",
                    assignment_location,
                )
        case awst_nodes.FieldExpression() as field_expr:
            if isinstance(field_expr.base.wtype, wtypes.WStructType):
                raise NotImplementedError
            elif isinstance(field_expr.base.wtype, wtypes.ARC4Struct):  # noqa: RET506
                return (
                    arc4.handle_arc4_assign(
                        context,
                        target=field_expr,
                        value=value,
                        is_nested_update=is_nested_update,
                        source_location=assignment_location,
                    ),
                )
            else:
                raise InternalError(
                    f"Field assignment operation IR lowering"
                    f" not implemented for base type {field_expr.base.wtype.name}",
                    assignment_location,
                )
        case _:
            raise CodeError(
                "expression is not valid as an assignment target", target.source_location
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
