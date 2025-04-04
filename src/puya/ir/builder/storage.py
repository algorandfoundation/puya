import typing
from collections.abc import Callable

from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.ir.arc4_types import wtype_to_arc4_wtype
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._tuple_util import build_tuple_registers
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    assign_targets,
    mktemp,
    new_register_version,
)
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    ConditionalBranch,
    Intrinsic,
    UInt64Constant,
    Undefined,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.types_ import PrimitiveIRType, wtype_to_ir_type, wtype_to_ir_types
from puya.parse import SourceLocation


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ValueProvider:
    maybe_value, exists = _build_state_get_ex(context, expr, expr.source_location)
    # TODO: add specific (unsafe) optimisation flag to allow skipping this check
    assert_value(
        context,
        value=exists,
        error_message=expr.exists_assertion_message or "state exists",
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
        error_message=expr.exists_assertion_message or "state exists for account",
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
        error_message=expr.exists_assertion_message or "box exists",
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


def conditional_value_provider(
    context: IRFunctionBuildContext,
    *,
    condition: Value,
    wtype: wtypes.WType,
    true_factory: Callable[[], ValueProvider],
    false_factory: Callable[[], ValueProvider],
    loc: SourceLocation,
) -> ValueProvider:
    true_block, false_block, merge_block = context.block_builder.mkblocks(
        "ternary_true", "ternary_false", "ternary_merge", source_location=loc
    )
    context.block_builder.terminate(
        ConditionalBranch(
            condition=condition,
            non_zero=true_block,
            zero=false_block,
            source_location=loc,
        )
    )
    tmp_var_name = context.next_tmp_name("ternary_result")
    true_registers = build_tuple_registers(context, tmp_var_name, wtype, loc)
    context.block_builder.activate_block(true_block)
    true = true_factory()
    assign_targets(
        context,
        source=true,
        targets=true_registers,
        assignment_location=true.source_location,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(false_block)
    false = false_factory()
    assign_targets(
        context,
        source=false,
        targets=[new_register_version(context, reg) for reg in true_registers],
        assignment_location=false.source_location,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(merge_block)
    result = [
        context.ssa.read_variable(variable=r.name, ir_type=r.ir_type, block=merge_block)
        for r in true_registers
    ]
    return ValueTuple(values=result, source_location=loc)


def visit_state_get(context: IRFunctionBuildContext, expr: awst_nodes.StateGet) -> ValueProvider:
    intrinsic_factory = OpFactory(context, expr.source_location)
    value_wtype = expr.wtype
    if isinstance(value_wtype, wtypes.WTuple):
        default_vp = context.visitor.visit_expr(expr.default)
        maybe_value_vp, exists = _build_state_get_ex(context, expr.field, expr.source_location)
        return conditional_value_provider(
            context,
            condition=exists,
            wtype=expr.wtype,
            true_factory=lambda: maybe_value_vp,
            false_factory=lambda: default_vp,
            loc=expr.source_location,
        )
    else:
        default = context.visitor.visit_and_materialise_single(expr.default)
        maybe_value_vp, exists = _build_state_get_ex(context, expr.field, expr.source_location)
        (maybe_value,) = context.visitor.materialise_value_provider(maybe_value_vp, "value")
        return intrinsic_factory.select(
            condition=exists,
            true=maybe_value,
            false=default,
            temp_desc="state_get",
            ir_type=wtype_to_ir_type(expr.wtype, expr.source_location),
        )


def visit_state_get_ex(
    context: IRFunctionBuildContext, expr: awst_nodes.StateGetEx
) -> ValueProvider:
    maybe_value_vp, exists = _build_state_get_ex(context, expr.field, expr.source_location)
    maybe_values = context.visitor.materialise_value_provider(maybe_value_vp, "maybe_value")
    return ValueTuple(
        values=[*maybe_values, exists],
        source_location=expr.source_location,
    )


def visit_state_delete(
    context: IRFunctionBuildContext, statement: awst_nodes.StateDelete
) -> ValueProvider | None:
    match statement:
        case awst_nodes.StateDelete(
            field=awst_nodes.BoxValueExpression(key=awst_key),
            wtype=wtypes.bool_wtype
            | wtypes.void_wtype,
        ):
            op = AVMOp.box_del
            awst_account = None
        case awst_nodes.StateDelete(
            field=awst_nodes.AppStateExpression(key=awst_key), wtype=wtypes.void_wtype
        ):
            op = AVMOp.app_global_del
            awst_account = None
        case awst_nodes.StateDelete(
            field=awst_nodes.AppAccountStateExpression(key=awst_key, account=awst_account),
            wtype=wtypes.void_wtype,
        ):
            op = AVMOp.app_local_del
        case awst_nodes.StateDelete():
            raise ValueError(
                f"Unexpected StateDelete field type: {statement.field}, wtype: {statement.wtype}"
            )
        case _:
            typing.assert_never(statement)

    args = []
    if awst_account is not None:
        account_value = context.visitor.visit_and_materialise_single(awst_account)
        args.append(account_value)
    key_value = context.visitor.visit_and_materialise_single(awst_key)
    args.append(key_value)

    state_delete = Intrinsic(op=op, args=args, source_location=statement.source_location)
    if statement.wtype == wtypes.bool_wtype:
        return state_delete

    context.block_builder.add(state_delete)
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
) -> tuple[ValueProvider, Value]:
    key = context.visitor.visit_and_materialise_single(expr.key)
    args: list[Value]
    native_wtype = expr.wtype
    if isinstance(expr.wtype, wtypes.WTuple):
        storage_wtype: wtypes.WType = wtype_to_arc4_wtype(native_wtype, source_location)
    else:
        storage_wtype = native_wtype
    true_value_ir_type = get_ex_value_ir_type = wtype_to_ir_type(
        storage_wtype, expr.source_location
    )
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
            get_ex_value_ir_type = PrimitiveIRType.uint64
            op = AVMOp.box_len
        else:
            op = AVMOp.box_get
            match wtypes.persistable_stack_type(expr.wtype, source_location):
                case AVMType.uint64:
                    get_ex_value_ir_type = PrimitiveIRType.bytes
                    convert_op = AVMOp.btoi
                case AVMType.bytes:
                    pass
                case invalid:
                    typing.assert_never(invalid)
    get_ex = Intrinsic(
        op=op,
        args=args,
        types=[get_ex_value_ir_type, PrimitiveIRType.bool],
        source_location=source_location,
    )
    value_tmp, did_exist_tmp = context.visitor.materialise_value_provider(
        get_ex, ("maybe_value", "maybe_exists")
    )

    if native_wtype != storage_wtype and not for_existence_check:
        from puya.ir.builder import arc4

        def decode_value() -> ValueProvider:
            assert isinstance(storage_wtype, wtypes.ARC4Type), "expected ARC4Type"
            return arc4.decode_arc4_value(
                context, value_tmp, storage_wtype, native_wtype, source_location
            )

        def undefined_value() -> ValueProvider:
            undefined = [
                Undefined(
                    ir_type=ir_type,
                    source_location=source_location,
                )
                for ir_type in wtype_to_ir_types(native_wtype, source_location)
            ]
            return ValueTuple(
                values=undefined,
                source_location=source_location,
            )

        assert convert_op is None, "unexpected convert_op"

        values = conditional_value_provider(
            context,
            condition=did_exist_tmp,
            wtype=native_wtype,
            true_factory=decode_value,
            false_factory=undefined_value,
            loc=source_location,
        )
        return values, did_exist_tmp
    elif convert_op is None:
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
