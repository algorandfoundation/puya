from collections.abc import Iterator
from typing import Sequence

from puya.avm_type import AVMType
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
from puya.ir.types_ import AVMBytesEncoding
from puya.parse import SourceLocation


def assign(
    context: IRFunctionBuildContext,
    source: ValueProvider,
    *,
    names: Sequence[tuple[str, SourceLocation | None]] | None = None,
    temp_description: str | None = None,
    source_location: SourceLocation | None,
) -> Sequence[Register]:
    atypes = source.types
    if not atypes:
        raise InternalError(
            "Attempted to assign from expression that has no result", source_location
        )

    if temp_description is not None:
        assert names is None, "One and only one of names and temp_description should be supplied"
        targets = [
            mktemp(context, atype, source_location, description=temp_description)
            for atype in atypes
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
            context.ssa.new_register(name, atype, var_loc)
            for (name, var_loc), atype in zip(names, atypes, strict=True)
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
    atype: AVMType,
    source_location: SourceLocation | None,
    *,
    description: str,
) -> Register:
    register = context.ssa.new_register(
        name=context.next_tmp_name(description),
        atype=atype,
        location=source_location,
    )
    return register


def format_tuple_index(var_name: str, index: int | str) -> str:
    return f"{var_name}.{index}"


def assign_intrinsic_op(
    context: IRFunctionBuildContext,
    *,
    target: str | Register,
    op: AVMOp,
    args: Sequence[int | bytes | Value],
    source_location: SourceLocation | None,
    immediates: list[int | str] | None = None,
) -> Sequence[Register]:
    def map_arg(arg: int | bytes | Value) -> Value:
        match arg:
            case int(val):
                return UInt64Constant(value=val, source_location=source_location)
            case bytes(b_val):
                return BytesConstant(
                    value=b_val,
                    source_location=source_location,
                    encoding=AVMBytesEncoding.base16,
                )
            case _:
                return arg

    if isinstance(target, str):
        return assign(
            context,
            temp_description=target,
            source_location=source_location,
            source=Intrinsic(
                op=op,
                immediates=immediates or list[int | str](),
                args=[map_arg(a) for a in args],
                source_location=source_location,
            ),
        )
    else:
        return assign(
            context,
            names=[(target.name, source_location)],
            source_location=source_location,
            source=Intrinsic(
                op=op,
                immediates=immediates or list[int | str](),
                args=[map_arg(a) for a in args],
                source_location=source_location,
            ),
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
