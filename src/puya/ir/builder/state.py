import typing

from puya.awst import nodes as awst_nodes
from puya.ir import intrinsic_factory
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import box
from puya.ir.builder._utils import assert_value, assign_targets, mktemp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Intrinsic, UInt64Constant, Value, ValueProvider
from puya.ir.types_ import IRType, wtype_to_ir_type
from puya.parse import SourceLocation


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ValueProvider:
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    return _checked_state_access(context, expr, assert_comment=f"check {expr.field_name} exists")


def visit_app_account_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppAccountStateExpression
) -> ValueProvider:
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    return _checked_state_access(
        context, expr, assert_comment=f"check {expr.field_name} exists for account"
    )


def visit_state_get_ex(
    context: IRFunctionBuildContext, expr: awst_nodes.StateGetEx
) -> ValueProvider:
    match expr.field:
        case awst_nodes.BoxValueExpression():
            return box.visit_box_state_get_ex(context, expr)
    return _build_state_get_ex(context, expr.field, expr.source_location)


def visit_state_delete(context: IRFunctionBuildContext, statement: awst_nodes.StateDelete) -> None:
    match statement.field:
        case awst_nodes.BoxValueExpression():
            return box.visit_box_state_delete(context, statement)
        case awst_nodes.AppStateExpression(key=awst_key):
            op = AVMOp.app_global_del
            awst_account = None
        case awst_nodes.AppAccountStateExpression(key=awst_key, account=awst_account):
            op = AVMOp.app_local_del
        case _:
            typing.assert_never(statement.field)

    args = []
    if awst_account is not None:
        account_value = context.visitor.visit_and_materialise_single(awst_account)
        args.append(account_value)
    key_value = context.visitor.visit_and_materialise_single(awst_key)
    args.append(key_value)

    context.block_builder.add(
        Intrinsic(op=op, args=args, source_location=statement.source_location)
    )


def visit_state_get(context: IRFunctionBuildContext, expr: awst_nodes.StateGet) -> ValueProvider:
    if isinstance(expr.field, awst_nodes.BoxValueExpression):
        return box.visit_box_state_get(context, expr)
    default = context.visitor.visit_and_materialise_single(expr.default)
    get_ex = _build_state_get_ex(context, expr.field, expr.source_location)
    maybe_value, exists = context.visitor.materialise_value_provider(
        get_ex, description=f"{expr.field.field_name}_get_ex"
    )
    return intrinsic_factory.select(
        condition=exists,
        true=maybe_value,
        false=default,
        type_=wtype_to_ir_type(expr.wtype),
        source_location=expr.source_location,
    )


def visit_state_exists(
    context: IRFunctionBuildContext, expr: awst_nodes.StateExists
) -> ValueProvider:
    match expr.field:
        case awst_nodes.BoxValueExpression():
            return box.visit_box_state_exists(context, expr)
    get_ex = _build_state_get_ex(context, expr.field, expr.source_location)
    _, exists = context.visitor.materialise_value_provider(
        get_ex, description=f"{expr.field.field_name}_exists"
    )
    return exists


def _checked_state_access(
    context: IRFunctionBuildContext,
    expr: awst_nodes.AppAccountStateExpression | awst_nodes.AppStateExpression,
    assert_comment: str,
) -> ValueProvider:
    get = _build_state_get_ex(context, expr, expr.source_location)
    # note: we manually construct temporary targets here since ir_type is any,
    #       but we "know" the type from the expression
    value_ir_type = wtype_to_ir_type(expr.wtype)
    value_tmp = mktemp(
        context,
        ir_type=value_ir_type,
        description=f"{expr.field_name}_value",
        source_location=expr.source_location,
    )
    did_exist_tmp = mktemp(
        context,
        ir_type=IRType.bool,
        description=f"{expr.field_name}_exists",
        source_location=expr.source_location,
    )
    assign_targets(
        context,
        source=get,
        targets=[value_tmp, did_exist_tmp],
        assignment_location=expr.source_location,
    )
    assert_value(
        context,
        value=did_exist_tmp,
        comment=assert_comment,
        source_location=expr.source_location,
    )
    return value_tmp


def _build_state_get_ex(
    context: IRFunctionBuildContext,
    expr: awst_nodes.AppAccountStateExpression | awst_nodes.AppStateExpression,
    source_location: SourceLocation,
) -> Intrinsic:
    current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
    key = context.visitor.visit_and_materialise_single(expr.key)
    args: list[Value] = [current_app_offset, key]
    if isinstance(expr, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_get_ex
    else:
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(expr.account)
        args.insert(0, account)
    return Intrinsic(
        op=op,
        args=args,
        source_location=source_location,
        types=[wtype_to_ir_type(expr.wtype), IRType.bool],
    )
