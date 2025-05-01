import typing
from collections.abc import Callable, Sequence

from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import InternalError
from puya.ir.arc4_types import wtype_to_arc4_wtype
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4
from puya.ir.builder._tuple_util import build_tuple_registers
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    assign_targets,
    new_register_version,
)
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    ConditionalBranch,
    Intrinsic,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.types_ import (
    IRType,
    PrimitiveIRType,
    persistable_stack_type,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ValueProvider:
    key = context.visitor.visit_and_materialise_single(expr.key)
    maybe_value, exists = _build_state_get_ex(context, expr, key, expr.source_location)
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
    key = context.visitor.visit_and_materialise_single(expr.key)
    maybe_value, exists = _build_state_get_ex(context, expr, key, expr.source_location)
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
    key = context.visitor.visit_and_materialise_single(expr.key)
    maybe_value, exists = _build_state_get_ex(context, expr, key, expr.source_location)
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
    field = expr.field
    loc = expr.source_location
    key = context.visitor.visit_and_materialise_single(field.key)
    # for global and local storage first return type could actually be uint64 or bytes
    # but we discard that value so just use uint64 for simplicity
    ir_types = [PrimitiveIRType.uint64, PrimitiveIRType.bool]
    if isinstance(expr.field, awst_nodes.AppStateExpression):
        get_ex = Intrinsic(
            op=AVMOp.app_global_get_ex,
            args=[UInt64Constant(value=0, source_location=loc), key],
            types=ir_types,
            source_location=loc,
        )
    elif isinstance(expr.field, awst_nodes.AppAccountStateExpression):
        account = context.visitor.visit_and_materialise_single(expr.field.account)
        get_ex = Intrinsic(
            op=AVMOp.app_local_get_ex,
            args=[account, UInt64Constant(value=0, source_location=loc), key],
            types=ir_types,
            source_location=loc,
        )
    else:
        typing.assert_type(expr.field, awst_nodes.BoxValueExpression)
        # use box_len for existence check, in case len(value) is > 4096
        get_ex = Intrinsic(
            op=AVMOp.box_len,
            args=[key],
            types=ir_types,
            source_location=loc,
        )

    _, maybe_exists = context.visitor.materialise_value_provider(get_ex, ("_", "maybe_exists"))
    return maybe_exists


def visit_state_get(context: IRFunctionBuildContext, expr: awst_nodes.StateGet) -> ValueProvider:
    intrinsic_factory = OpFactory(context, expr.source_location)
    value_wtype = expr.wtype
    # ensure we visit key before default value
    key = context.visitor.visit_and_materialise_single(expr.field.key)
    if value_wtype.scalar_type is None:
        default_decoded_values = context.visitor.visit_and_materialise(expr.default)
        maybe_value_vp, _exists = _build_state_get_ex(
            context,
            expr.field,
            key,
            expr.source_location,
            default_decoded_values=default_decoded_values,
        )
        return maybe_value_vp
    else:
        default = context.visitor.visit_and_materialise_single(expr.default)
        maybe_value_vp, exists = _build_state_get_ex(
            context, expr.field, key, expr.source_location
        )
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
    key = context.visitor.visit_and_materialise_single(expr.field.key)
    maybe_value_vp, exists = _build_state_get_ex(context, expr.field, key, expr.source_location)
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
    expr: awst_nodes.StorageExpression,
    key: Value,
    loc: SourceLocation,
    *,
    default_decoded_values: Sequence[Value] | None = None,
) -> tuple[ValueProvider, Value]:
    native_wtype = expr.wtype
    if isinstance(native_wtype, wtypes.WTuple):
        storage_wtype: wtypes.WType = wtype_to_arc4_wtype(native_wtype, loc)
    else:
        storage_wtype = native_wtype

    requires_btoi = False
    if isinstance(expr, awst_nodes.AppStateExpression):
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        get_storage_value = Intrinsic(
            op=AVMOp.app_global_get_ex,
            args=[current_app_offset, key],
            types=[wtype_to_ir_type(storage_wtype, loc), PrimitiveIRType.bool],
            source_location=loc,
        )
    elif isinstance(expr, awst_nodes.AppAccountStateExpression):
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        account = context.visitor.visit_and_materialise_single(expr.account)
        get_storage_value = Intrinsic(
            op=AVMOp.app_local_get_ex,
            args=[account, current_app_offset, key],
            types=[wtype_to_ir_type(storage_wtype, loc), PrimitiveIRType.bool],
            source_location=loc,
        )
    else:
        typing.assert_type(expr, awst_nodes.BoxValueExpression)
        get_storage_value = Intrinsic(
            op=AVMOp.box_get,
            args=[key],
            source_location=loc,
        )
        # boxes can only store bytes, so uint64 are stored as their bytes encoded value
        # so need to btoi them when loading
        match persistable_stack_type(native_wtype, loc):
            case AVMType.uint64:
                requires_btoi = True
            case AVMType.bytes:
                pass
            case invalid:
                typing.assert_never(invalid)

    storage_value, did_exist = context.visitor.materialise_value_provider(
        get_storage_value, ("maybe_value", "maybe_exists")
    )

    if requires_btoi:
        factory = OpFactory(context, loc)
        # technically this should probably only occur if the value existed,
        # but since the default value of a non-existent box is an empty bytes
        # this still works
        native_values: ValueProvider = factory.btoi(storage_value, "maybe_value_converted")
        assert default_decoded_values is None
    elif native_wtype == storage_wtype:
        native_values = storage_value
        assert default_decoded_values is None
    else:
        # TODO: hmmmm
        assert isinstance(storage_wtype, wtypes.ARC4Type), "expected ARC4Type"
        if default_decoded_values is None:
            false_vp = arc4.undefined_value(native_wtype, loc)
        else:
            false_vp = ValueTuple(values=default_decoded_values, source_location=loc)

        native_values = _conditional_value_provider(
            context,
            condition=did_exist,
            wtype=native_wtype,
            true_factory=lambda: arc4.decode_arc4_value(
                context, storage_value, storage_wtype, native_wtype, loc
            ),
            false_factory=lambda: false_vp,
            loc=loc,
        )
    return native_values, did_exist


def _conditional_value_provider(
    context: IRFunctionBuildContext,
    *,
    condition: Value,
    wtype: wtypes.WType,
    true_factory: Callable[[], ValueProvider],
    false_factory: Callable[[], ValueProvider],
    loc: SourceLocation,
) -> ValueProvider:
    """
    Builds a conditional that returns one of two ValueProviders

    true and false values are provided via factories so IR construction emits them at the correct
    time
    """
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


class _EncodeForStorageResult(typing.NamedTuple):
    values: list[Value]
    """Materialized values of ValueProvider"""
    encoded: Value
    """Encoded Value for storage"""
    encoded_ir_type: IRType


def encode_for_storage(
    context: IRFunctionBuildContext,
    kind: awst_nodes.AppStorageKind,
    value: ValueProvider,
    expr_wtype: wtypes.WType,
    loc: SourceLocation,
) -> _EncodeForStorageResult:
    """Encoded provided ValueProvider as a single Value suitable for storage"""
    materialized_values = context.visitor.materialise_value_provider(value, "materialized_values")
    # TODO: also add explicit check for ImmutableArray?
    if not isinstance(expr_wtype, wtypes.WTuple):
        (encoded,) = materialized_values
        encoded_wtype = expr_wtype
    else:
        encoded_wtype = wtype_to_arc4_wtype(expr_wtype, loc)
        encoded_vp = arc4.encode_value_provider(
            context, value, expr_wtype, arc4_wtype=encoded_wtype, loc=loc
        )
        (encoded,) = context.visitor.materialise_value_provider(
            encoded_vp, description="encoded_value"
        )
    # ensure encoding implementation is consistent with metadata
    scalar_type = persistable_stack_type(expr_wtype, loc)

    if scalar_type != encoded.ir_type.avm_type:  # double check
        raise InternalError("inconsistent storage types", loc)

    if kind is awst_nodes.AppStorageKind.box and scalar_type == AVMType.uint64:
        factory = OpFactory(context, loc)
        encoded = factory.itob(encoded, "encoded_value")
        encoded_ir_type = encoded.ir_type
    else:
        # we use the IRType of the original expression, not the value's IRType,
        # since it could be "narrowed" there (e.g. if the value is a constant)
        encoded_ir_type = wtype_to_ir_type(encoded_wtype, loc)

    return _EncodeForStorageResult(materialized_values, encoded, encoded_ir_type)
