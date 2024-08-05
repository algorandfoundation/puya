import typing
from collections.abc import Sequence

import attrs

from puya.awst import nodes as awst_nodes
from puya.errors import InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    Assignment,
    BytesConstant,
    Intrinsic,
    InvokeSubroutine,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
)
from puya.ir.types_ import AVMBytesEncoding, IRType
from puya.parse import SourceLocation


def assign(
    context: IRFunctionBuildContext,
    source: ValueProvider,
    *,
    name: str,
    assignment_location: SourceLocation | None,
    register_location: SourceLocation | None = None,
) -> Register:
    (ir_type,) = source.types
    target = context.ssa.new_register(name, ir_type, register_location or assignment_location)
    assign_targets(
        context=context,
        source=source,
        targets=[target],
        assignment_location=assignment_location,
    )
    return target


def new_register_version(context: IRFunctionBuildContext, reg: Register) -> Register:
    return context.ssa.new_register(
        name=reg.name, ir_type=reg.ir_type, location=reg.source_location
    )


def assign_temp(
    context: IRFunctionBuildContext,
    source: ValueProvider,
    *,
    temp_description: str,
    source_location: SourceLocation | None,
) -> Register:
    (ir_type,) = source.types
    target = mktemp(context, ir_type, source_location, description=temp_description)
    assign_targets(
        context,
        source=source,
        targets=[target],
        assignment_location=source_location,
    )
    return target


def assign_targets(
    context: IRFunctionBuildContext,
    *,
    source: ValueProvider,
    targets: list[Register],
    assignment_location: SourceLocation | None,
) -> None:
    for target in targets:
        context.ssa.write_variable(target.name, context.block_builder.active_block, target)
    context.block_builder.add(
        Assignment(targets=targets, source=source, source_location=assignment_location)
    )


def mktemp(
    context: IRFunctionBuildContext,
    ir_type: IRType,
    source_location: SourceLocation | None,
    *,
    description: str,
) -> Register:
    name = context.next_tmp_name(description)
    return context.ssa.new_register(name, ir_type, source_location)


def assign_intrinsic_op(
    context: IRFunctionBuildContext,
    *,
    target: str | Register,
    op: AVMOp,
    args: Sequence[int | bytes | Value],
    source_location: SourceLocation | None,
    immediates: list[int | str] | None = None,
    return_type: IRType | None = None,
) -> Register:
    intrinsic = Intrinsic(
        op=op,
        immediates=immediates or [],
        args=[_convert_constants(a, source_location) for a in args],
        types=(
            [return_type]
            if return_type is not None
            else typing.cast(Sequence[IRType], attrs.NOTHING)
        ),
        source_location=source_location,
    )
    if isinstance(target, str):
        target_reg = mktemp(context, intrinsic.types[0], source_location, description=target)
    else:
        target_reg = new_register_version(context, target)
    assign_targets(
        context,
        targets=[target_reg],
        source=intrinsic,
        assignment_location=source_location,
    )
    return target_reg


def _convert_constants(arg: int | bytes | Value, source_location: SourceLocation | None) -> Value:
    match arg:
        case int(val):
            return UInt64Constant(value=val, source_location=source_location)
        case bytes(b_val):
            return BytesConstant(
                value=b_val, encoding=AVMBytesEncoding.unknown, source_location=source_location
            )
        case _:
            return arg


def invoke_puya_lib_subroutine(
    context: IRFunctionBuildContext,
    *,
    method_name: str,
    module_name: str,
    args: Sequence[Value | int | bytes],
    source_location: SourceLocation,
) -> InvokeSubroutine:
    target = awst_nodes.FreeSubroutineTarget(module_name=module_name, name=method_name)
    func = context.resolve_function_reference(target, source_location)
    try:
        sub = context.subroutines[func]
    except KeyError as ex:
        raise InternalError(f"Could not find subroutine for {target}", source_location) from ex
    return InvokeSubroutine(
        source_location=source_location,
        target=sub,
        args=[_convert_constants(arg, source_location) for arg in args],
    )


def assert_value(
    context: IRFunctionBuildContext, value: Value, *, source_location: SourceLocation, comment: str
) -> None:
    context.block_builder.add(
        Intrinsic(
            op=AVMOp.assert_,
            source_location=source_location,
            args=[value],
            comment=comment,
        )
    )


def extract_const_int(expr: awst_nodes.Expression | int | None) -> int | None:
    """
    Check expr is an IntegerConstant, int literal, or None, and return constant value (or None)
    """
    match expr:
        case None:
            return None
        case awst_nodes.IntegerConstant(value=value):
            return value
        case int(value):
            return value
        case _:
            raise InternalError(
                f"Expected either constant or None for index, got {type(expr).__name__}",
                expr.source_location,
            )
