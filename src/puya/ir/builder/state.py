from puya.avm_type import AVMType
from puya.awst import nodes as awst_nodes
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import assert_value, assign_targets, mktemp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import BytesConstant, Intrinsic, UInt64Constant, Value, ValueProvider
from puya.ir.types_ import bytes_enc_to_avm_bytes_enc, wtype_to_avm_type
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
    return _build_state_get_ex(context, expr.field, expr.source_location)


def visit_state_delete(context: IRFunctionBuildContext, statement: awst_nodes.StateDelete) -> None:
    subject = statement.field
    state_def = context.resolve_state(subject.field_name, subject.source_location)
    key = BytesConstant(
        value=state_def.key,
        source_location=subject.source_location,
        encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
    )
    args: list[Value] = [key]
    if isinstance(subject, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_del
    else:
        op = AVMOp.app_local_del
        account = context.visitor.visit_and_materialise_single(subject.account)
        args.insert(0, account)
    context.block_builder.add(
        Intrinsic(
            op=op,
            args=args,
            source_location=statement.source_location,
        )
    )


def visit_state_get(context: IRFunctionBuildContext, expr: awst_nodes.StateGet) -> ValueProvider:
    default = context.visitor.visit_and_materialise_single(expr.default)
    get_ex = _build_state_get_ex(context, expr.field, expr.source_location)
    maybe_value, exists = context.visitor.materialise_value_provider(
        get_ex, description=f"{expr.field.field_name}_get_ex"
    )
    return Intrinsic(
        op=AVMOp.select,
        args=[default, maybe_value, exists],
        source_location=expr.source_location,
    )


def visit_state_exists(
    context: IRFunctionBuildContext, expr: awst_nodes.StateExists
) -> ValueProvider:
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
    # note: we manually construct temporary targets here since atype is any,
    #       but we "know" the type from the expression
    value_atype = wtype_to_avm_type(expr.wtype)
    value_tmp = mktemp(
        context,
        atype=value_atype,
        description=f"{expr.field_name}_value",
        source_location=expr.source_location,
    )
    did_exist_tmp = mktemp(
        context,
        atype=AVMType.uint64,
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
    state_def = context.resolve_state(expr.field_name, expr.source_location)
    current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
    key = BytesConstant(
        value=state_def.key,
        source_location=expr.source_location,
        encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
    )
    args: list[Value] = [current_app_offset, key]
    if isinstance(expr, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_get_ex
    else:
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(expr.account)
        args.insert(0, account)
    return Intrinsic(op=op, args=args, source_location=source_location)
