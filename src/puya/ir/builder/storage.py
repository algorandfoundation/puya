import typing

from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.ir import intrinsic_factory
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import assert_value, assign_targets, mktemp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Intrinsic, UInt64Constant, Value, ValueProvider, ValueTuple
from puya.ir.types_ import IRType, wtype_to_ir_type
from puya.parse import SourceLocation


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ValueProvider:
    maybe_value, exists = _build_state_get_ex(context, expr, expr.source_location)
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    assert_value(
        context,
        value=exists,
        comment=expr.exists_assertion_message or "state exists",
        source_location=expr.source_location,
    )
    return maybe_value


def visit_app_account_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppAccountStateExpression
) -> ValueProvider:
    maybe_value, exists = _build_state_get_ex(context, expr, expr.source_location)
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    assert_value(
        context,
        value=exists,
        comment=expr.exists_assertion_message or "state exists for account",
        source_location=expr.source_location,
    )
    return maybe_value


def visit_box_value(
    context: IRFunctionBuildContext, expr: awst_nodes.BoxValueExpression
) -> ValueProvider:
    maybe_value, exists = _build_state_get_ex(context, expr, expr.source_location)
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    assert_value(
        context,
        value=exists,
        comment=expr.exists_assertion_message or "box exists",
        source_location=expr.source_location,
    )
    return maybe_value


def visit_state_exists(
    context: IRFunctionBuildContext, expr: awst_nodes.StateExists
) -> ValueProvider:
    _, exists = _build_state_get_ex(
        context, expr.field, expr.source_location, for_existence_check=True
    )
    return exists


def visit_state_get(context: IRFunctionBuildContext, expr: awst_nodes.StateGet) -> ValueProvider:
    default = context.visitor.visit_and_materialise_single(expr.default)
    maybe_value, exists = _build_state_get_ex(context, expr.field, expr.source_location)
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
    return ValueTuple(
        values=list(_build_state_get_ex(context, expr.field, expr.source_location)),
        source_location=expr.source_location,
    )


def visit_state_delete(
    context: IRFunctionBuildContext, statement: awst_nodes.StateDelete
) -> ValueProvider | None:
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
    return None


def _build_state_get_ex(
    context: IRFunctionBuildContext,
    expr: (
        awst_nodes.AppAccountStateExpression
        | awst_nodes.AppStateExpression
        | awst_nodes.BoxValueExpression
    ),
    source_location: SourceLocation,
    *,
    for_existence_check: bool = False,
) -> tuple[Value, Value]:
    key = context.visitor.visit_and_materialise_single(expr.key)
    args: list[Value]
    true_value_ir_type = get_ex_value_ir_type = wtype_to_ir_type(expr.wtype)
    convert_op: AVMOp | None = None
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
        args = [key]
        if for_existence_check:
            get_ex_value_ir_type = IRType.uint64
            op = AVMOp.box_len
        else:
            op = AVMOp.box_get
            match wtypes.persistable_stack_type(expr.wtype, source_location):
                case AVMType.uint64:
                    get_ex_value_ir_type = IRType.bytes
                    convert_op = AVMOp.btoi
                case AVMType.bytes:
                    pass
                case invalid:
                    typing.assert_never(invalid)
    get_ex = Intrinsic(
        op=op,
        args=args,
        types=[get_ex_value_ir_type, IRType.bool],
        source_location=source_location,
    )
    value_tmp, did_exist_tmp = context.visitor.materialise_value_provider(
        get_ex, ("maybe_value", "maybe_exists")
    )
    if convert_op is None:
        return value_tmp, did_exist_tmp
    convert = Intrinsic(op=convert_op, args=[value_tmp], source_location=source_location)
    value_tmp_converted = mktemp(
        context,
        ir_type=true_value_ir_type,
        description="maybe_value_converted",
        source_location=expr.source_location,
    )

    assign_targets(
        context, source=convert, targets=[value_tmp_converted], assignment_location=source_location
    )
    return value_tmp_converted, did_exist_tmp
