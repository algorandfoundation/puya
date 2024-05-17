import typing
from collections.abc import Iterator, Sequence

import attrs

from puya.awst import nodes as awst_nodes
from puya.errors import InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    Assignment,
    BasicBlock,
    BytesConstant,
    Intrinsic,
    InvokeSubroutine,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
)
from puya.ir.types_ import AVMBytesEncoding, IRType
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation


@typing.overload
def assign(
    context: IRFunctionBuildContext,
    source: ValueProvider,
    *,
    names: Sequence[tuple[str, SourceLocation | None]],
    source_location: SourceLocation | None,
) -> Sequence[Register]: ...


@typing.overload
def assign(
    context: IRFunctionBuildContext,
    source: ValueProvider,
    *,
    temp_description: str | Sequence[str],
    source_location: SourceLocation | None,
) -> Sequence[Register]: ...


def assign(
    context: IRFunctionBuildContext,
    source: ValueProvider,
    *,
    names: Sequence[tuple[str, SourceLocation | None]] | None = None,
    temp_description: str | Sequence[str] | None = None,
    source_location: SourceLocation | None,
) -> Sequence[Register]:
    atypes = source.types
    if not atypes:
        raise InternalError(
            "Attempted to assign from expression that has no result", source_location
        )

    if temp_description is not None:
        assert names is None, "One and only one of names and temp_description should be supplied"
        if isinstance(temp_description, str):
            temp_description = [temp_description] * len(atypes)
        targets = [
            mktemp(context, ir_type, source_location, description=descr)
            for ir_type, descr in zip(atypes, temp_description, strict=True)
        ]
    else:
        assert (
            names is not None
        ), "One and only one of names and temp_description should be supplied"
        # non-temporary assignment, so in the case of a multi-valued returning source/provider,
        # names should either be a single value (ie a tuple var name),
        # or it should match the length (ie unpack the tuple)
        if len(names) != len(atypes):
            try:
                ((name, var_loc),) = names
            except ValueError as ex:
                raise InternalError(
                    "Incompatible multi-assignment lengths", source_location
                ) from ex
            names = [(format_tuple_index(name, idx), var_loc) for idx, _ in enumerate(atypes)]
        targets = [
            context.ssa.new_register(name, ir_type, var_loc)
            for (name, var_loc), ir_type in zip(names, atypes, strict=True)
        ]

    assign_targets(
        context=context,
        source=source,
        targets=targets,
        assignment_location=source_location,
    )

    return targets


def reassign(
    context: IRFunctionBuildContext,
    reg: Register,
    source: ValueProvider,
    source_location: SourceLocation | None,
) -> Register:
    (updated,) = assign(
        context,
        source=source,
        names=[(reg.name, reg.source_location)],
        source_location=source_location,
    )
    return updated


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
    register = context.ssa.new_register(
        name=context.next_tmp_name(description),
        ir_type=ir_type,
        location=source_location,
    )
    return register


def assign_intrinsic_op(
    context: IRFunctionBuildContext,
    *,
    target: str | Register,
    op: AVMOp,
    args: Sequence[int | bytes | Value],
    source_location: SourceLocation | None,
    immediates: list[int | str] | None = None,
    return_type: Sequence[IRType] | None = None,
) -> Sequence[Register]:
    def map_arg(arg: int | bytes | Value) -> Value:
        match arg:
            case int(val):
                return UInt64Constant(value=val, source_location=source_location)
            case bytes(b_val):
                return BytesConstant(
                    value=b_val,
                    encoding=AVMBytesEncoding.base16,
                    source_location=source_location,
                )
            case _:
                return arg

    intrinsic = Intrinsic(
        op=op,
        immediates=immediates or [],
        args=[map_arg(a) for a in args],
        types=(
            return_type
            if return_type is not None
            else typing.cast(Sequence[IRType], attrs.NOTHING)
        ),
        source_location=source_location,
    )
    if isinstance(target, str):
        return assign(
            context,
            temp_description=target,
            source=intrinsic,
            source_location=source_location,
        )
    else:
        return assign(
            context,
            names=[(target.name, source_location)],
            source=intrinsic,
            source_location=source_location,
        )


def invoke_puya_lib_subroutine(
    context: IRFunctionBuildContext,
    *,
    method_name: str,
    module_name: str,
    args: list[Value],
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
        args=args,
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


def mkblocks(loc: SourceLocation, *comments: str | None) -> Iterator[BasicBlock]:
    for c in comments:
        yield BasicBlock(comment=c, source_location=loc)


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
