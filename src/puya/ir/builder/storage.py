import typing

from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
)
from puya.ir import (
    intrinsic_factory,
    models as ops,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import (
    assert_value,
    assign,
    assign_intrinsic_op,
    assign_targets,
    mktemp,
)
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Intrinsic, UInt64Constant, Value, ValueProvider
from puya.ir.types_ import IRType, wtype_to_ir_type
from puya.parse import SourceLocation


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ValueProvider:
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    return _checked_state_access(context, expr, assert_comment=f"check {expr.member_name} exists")


def visit_app_account_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppAccountStateExpression
) -> ValueProvider:
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    return _checked_state_access(
        context, expr, assert_comment=f"check {expr.member_name} exists for account"
    )


def visit_state_exists(
    context: IRFunctionBuildContext, expr: awst_nodes.StateExists
) -> ValueProvider:
    match expr.field:
        case awst_nodes.BoxValueExpression() as box_expr:
            return _box_state_exists(context, box_expr, expr.source_location)
    get_ex = _build_state_get_ex(context, expr.field, expr.source_location)
    _, exists = context.visitor.materialise_value_provider(
        get_ex, description=f"{expr.field.member_name}_exists"
    )
    return exists


def visit_box_value(
    context: IRFunctionBuildContext, expr: awst_nodes.BoxValueExpression
) -> ops.ValueProvider:
    source_location = expr.source_location
    box_key = context.visitor.visit_and_materialise_single(expr.key)
    (box_value, box_exists) = assign(
        context=context,
        temp_description=["box_value", "box_exists"],
        source_location=source_location,
        source=ops.Intrinsic(
            op=AVMOp.box_get,
            args=[box_key],
            source_location=source_location,
        ),
    )
    if expr.wtype.scalar_type == AVMType.uint64:
        (box_value,) = assign_intrinsic_op(
            op=AVMOp.btoi,
            target="box_value_uint64",
            source_location=source_location,
            context=context,
            args=[box_value],
        )
    assert_value(
        context,
        box_exists,
        comment="Box must exist",
        source_location=expr.source_location,
    )
    return box_value


def visit_state_get(context: IRFunctionBuildContext, expr: awst_nodes.StateGet) -> ValueProvider:
    default = context.visitor.visit_and_materialise_single(expr.default)
    get_ex = _build_state_get_ex(context, expr.field, expr.source_location)
    maybe_value, exists = context.visitor.materialise_value_provider(
        get_ex, description=f"{expr.field.member_name}_get_ex"
    )
    return intrinsic_factory.select(
        condition=exists,
        true=maybe_value,
        false=default,
        type_=wtype_to_ir_type(expr.wtype),
        source_location=expr.source_location,
    )


def visit_state_get_ex(
    context: IRFunctionBuildContext, expr: awst_nodes.StateGetEx
) -> ValueProvider:
    return _build_state_get_ex(context, expr.field, expr.source_location)


def visit_state_delete(context: IRFunctionBuildContext, statement: awst_nodes.StateDelete) -> None:
    match statement.field:
        case awst_nodes.BoxValueExpression(key=awst_key):
            op = AVMOp.box_del
            awst_account = None
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


def _checked_state_access(
    context: IRFunctionBuildContext,
    expr: awst_nodes.AppAccountStateExpression | awst_nodes.AppStateExpression,
    assert_comment: str,
) -> ValueProvider:
    get = _build_state_get_ex(context, expr, expr.source_location)
    # note: we manually construct temporary targets here since AVMType can be any,
    #       but we "know" the type from the expression
    value_ir_type = wtype_to_ir_type(expr.wtype)
    value_tmp = mktemp(
        context,
        ir_type=value_ir_type,
        description=f"{expr.member_name}_value",
        source_location=expr.source_location,
    )
    did_exist_tmp = mktemp(
        context,
        ir_type=IRType.bool,
        description=f"{expr.member_name}_exists",
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
    expr: (
        awst_nodes.AppAccountStateExpression
        | awst_nodes.AppStateExpression
        | awst_nodes.BoxValueExpression
    ),
    source_location: SourceLocation,
) -> Intrinsic:
    key = context.visitor.visit_and_materialise_single(expr.key)
    args: list[Value]
    if isinstance(expr, awst_nodes.AppStateExpression):
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        args = [current_app_offset, key]
        op = AVMOp.app_global_get_ex
    elif isinstance(expr, awst_nodes.AppAccountStateExpression):
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(expr.account)
        args = [account, current_app_offset, key]
    else:
        op = AVMOp.box_get
        args = [key]
    value_ir_type = wtype_to_ir_type(expr.wtype)
    return Intrinsic(
        op=op, args=args, types=[value_ir_type, IRType.bool], source_location=source_location
    )


def _box_state_exists(
    context: IRFunctionBuildContext, field: awst_nodes.BoxValueExpression, location: SourceLocation
) -> ops.ValueProvider:
    box_key = context.visitor.visit_and_materialise_single(field.key)
    if field.is_map:
        pass
    (box_len, box_exists) = assign(
        context=context,
        temp_description=["box_len", "box_exists"],
        source=ops.Intrinsic(op=AVMOp.box_len, args=[box_key], source_location=location),
        source_location=location,
    )
    return box_exists
