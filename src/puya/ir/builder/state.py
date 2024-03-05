from puya.avm_type import AVMType
from puya.awst import nodes as awst_nodes
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import assign_targets, mktemp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import BytesConstant, Intrinsic, UInt64Constant, Value, ValueProvider
from puya.ir.types_ import bytes_enc_to_avm_bytes_enc, wtype_to_avm_type


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ValueProvider:
    state_def = context.resolve_state(expr.field_name, expr.source_location)
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
    key = BytesConstant(
        value=state_def.key,
        source_location=expr.source_location,
        encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
    )

    # note: we manually construct temporary targets here since atype is any,
    #       but we "know" the type from the expression
    value_atype = wtype_to_avm_type(expr.wtype)
    value_tmp = mktemp(
        context,
        atype=value_atype,
        source_location=expr.source_location,
        description="app_global_get_ex_value",
    )
    did_exist_tmp = mktemp(
        context,
        atype=AVMType.uint64,
        source_location=expr.source_location,
        description="app_global_get_ex_did_exist",
    )
    assign_targets(
        context,
        source=Intrinsic(
            op=AVMOp.app_global_get_ex,
            args=[current_app_offset, key],
            source_location=expr.source_location,
        ),
        targets=[value_tmp, did_exist_tmp],
        assignment_location=expr.source_location,
    )
    context.block_builder.add(
        Intrinsic(
            op=AVMOp.assert_,
            args=[did_exist_tmp],
            comment=f"check {expr.field_name} exists",
            source_location=expr.source_location,
        )
    )

    return value_tmp


def visit_app_account_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppAccountStateExpression
) -> ValueProvider:
    state_def = context.resolve_state(expr.field_name, expr.source_location)
    account = context.visitor.visit_and_materialise_single(expr.account)

    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
    key = BytesConstant(
        value=state_def.key,
        source_location=expr.source_location,
        encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
    )

    # note: we manually construct temporary targets here since atype is any,
    #       but we "know" the type from the expression
    value_tmp = mktemp(
        context,
        atype=wtype_to_avm_type(expr.wtype),
        source_location=expr.source_location,
        description="app_local_get_ex_value",
    )
    did_exist_tmp = mktemp(
        context,
        atype=AVMType.uint64,
        source_location=expr.source_location,
        description="app_local_get_ex_did_exist",
    )
    assign_targets(
        context,
        source=Intrinsic(
            op=AVMOp.app_local_get_ex,
            args=[account, current_app_offset, key],
            source_location=expr.source_location,
        ),
        targets=[value_tmp, did_exist_tmp],
        assignment_location=expr.source_location,
    )
    context.block_builder.add(
        Intrinsic(
            op=AVMOp.assert_,
            args=[did_exist_tmp],
            comment=f"check {expr.field_name} exists for account",
            source_location=expr.source_location,
        )
    )
    return value_tmp


def visit_state_get_ex(
    context: IRFunctionBuildContext, expr: awst_nodes.StateGetEx
) -> ValueProvider:
    subject = expr.field
    state_def = context.resolve_state(subject.field_name, subject.source_location)
    current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
    key = BytesConstant(
        value=state_def.key,
        source_location=subject.source_location,
        encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
    )
    args: list[Value] = [current_app_offset, key]
    if isinstance(subject, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_get_ex
    else:
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(subject.account)
        args.insert(0, account)
    return Intrinsic(
        op=op,
        args=args,
        source_location=expr.source_location,
    )


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
    subject = expr.field
    state_def = context.resolve_state(subject.field_name, subject.source_location)
    current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)

    key = BytesConstant(
        value=state_def.key,
        source_location=subject.source_location,
        encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
    )
    default = context.visitor.visit_and_materialise_single(expr.default)

    args: list[Value] = [current_app_offset, key]
    if isinstance(subject, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_get_ex
    else:
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(subject.account)
        args.insert(0, account)
    maybe_value, exists = context.visitor.materialise_value_provider(
        Intrinsic(
            op=op,
            args=args,
            source_location=expr.source_location,
        ),
        description=f"{subject.field_name}_get_ex",
    )
    return Intrinsic(
        op=AVMOp.select,
        args=[default, maybe_value, exists],
        source_location=expr.source_location,
    )


def visit_state_exists(
    context: IRFunctionBuildContext, expr: awst_nodes.StateExists
) -> ValueProvider:
    subject = expr.field
    state_def = context.resolve_state(subject.field_name, subject.source_location)
    current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
    key = BytesConstant(
        value=state_def.key,
        source_location=subject.source_location,
        encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
    )
    args: list[Value] = [current_app_offset, key]
    if isinstance(subject, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_get_ex
    else:
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(subject.account)
        args.insert(0, account)
    _, exists = context.visitor.materialise_value_provider(
        Intrinsic(
            op=op,
            args=args,
            source_location=expr.source_location,
        ),
        description=f"{subject.field_name}_exists",
    )
    return exists
