import struct
import typing
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence

from puya import log
from puya.errors import CodeError, InternalError
from puya.models import DebugEvent
from puya.parse import SourceLocation
from puya.teal import models as teal
from puya.ussemble import models
from puya.ussemble.context import AssembleContext
from puya.ussemble.debug import build_debug_info
from puya.ussemble.op_spec import OP_SPECS
from puya.ussemble.op_spec_models import ImmediateEnum, ImmediateKind

logger = log.get_logger(__name__)
_BRANCHING_OPS = {
    op.name
    for op in OP_SPECS.values()
    if any(i in (ImmediateKind.label, ImmediateKind.label_array) for i in op.immediates)
}


def assemble_bytecode_and_debug_info(
    ctx: AssembleContext, program: teal.TealProgram
) -> models.AssembledProgram:
    function_block_ids = {s.blocks[0].label: s.signature.name for s in program.all_subroutines}

    version_bytes = _encode_varuint(ctx.options.target_avm_version)
    pc_events = defaultdict[int, DebugEvent](DebugEvent)  # type: ignore[arg-type]
    pc_ops = dict[int, models.AVMOp]()
    label_pcs = dict[str, int]()

    # pc includes version header
    pc = len(version_bytes)
    # first pass lowers teal ops, calculate pcs, and captures debug info
    for subroutine in program.all_subroutines:
        current_event = pc_events[pc]
        current_event["subroutine"] = subroutine.signature.name
        current_event["params"] = {
            p.local_id: p.atype.name or "" for p in subroutine.signature.parameters
        }
        stack = list[str]()
        for block in subroutine.blocks:
            current_event = pc_events[pc]
            # update stack with correct values on entry to a block
            f_stack_height = block.entry_stack_height - len(block.x_stack_in)
            stack[f_stack_height:] = block.x_stack_in
            label_pcs[block.label] = pc
            current_event["block"] = block.label
            current_event["stack_in"] = stack.copy()
            defined = set[str]()

            for op in block.ops:
                current_event = pc_events[pc]
                avm_op = _lower_op(ctx, op)
                # actual label offsets can't be determined until all PC values are known
                # so just use a placeholder value initially
                op_size = len(_encode_op(avm_op, get_label_offset=lambda _: 0))
                assert op_size, "expected non empty bytecode"
                _add_op_debug_events(
                    current_event,
                    function_block_ids,
                    op,
                    # note: stack & defined are mutated
                    stack,
                    defined,
                )
                pc_ops[pc] = avm_op
                pc += op_size

    # all pc values, including pc after final op
    pcs = [*pc_ops, pc]
    # second pass assembles final byte code
    bytecode = [version_bytes]
    for op_index, avm_op in enumerate(pc_ops.values()):

        def get_label_offset(label: models.Label) -> int:
            # label offset is the signed PC difference
            # between the label PC location and the end of the current op
            return label_pcs[label.name] - pcs[op_index + 1]  # noqa: B023

        bytecode.append(_encode_op(avm_op, get_label_offset=get_label_offset))

    return models.AssembledProgram(
        bytecode=b"".join(bytecode),
        debug_info=build_debug_info(
            ctx,
            pc_ops,
            pc_events,
        ),
    )


def _add_op_debug_events(
    event: DebugEvent,
    subroutine_ids: Mapping[str, str],
    op: teal.TealOp,
    stack: list[str],
    defined: set[str],
) -> None:
    stack_in = stack.copy()
    num_defined = len(defined)
    if op.op_code == "callsub":
        (func_block,) = op.immediates
        assert isinstance(func_block, str), "expected label"
        event["callsub"] = subroutine_ids[func_block]
    elif op.op_code == "retsub":
        event["retsub"] = True
    event["op"] = op.teal()

    for sm in op.stack_manipulations:
        match sm:
            case teal.StackConsume(n=n):
                for _ in range(n):
                    stack.pop()
            case teal.StackExtend() as se:
                stack.extend(se.local_ids)
            case teal.StackDefine() as sd:
                defined.update(sd.local_ids)
            case teal.StackInsert() as si:
                index = len(stack) - si.depth
                stack.insert(index, si.local_id)
            case teal.StackPop() as sp:
                index = len(stack) - sp.depth - 1
                stack.pop(index)
            case _:
                typing.assert_never(sm)

    if len(defined) != num_defined:
        event["defined_out"] = sorted(set(defined) & set(stack))
    if stack_in != stack:
        event["stack_out"] = stack.copy()


def _lower_op(ctx: AssembleContext, op: teal.TealOp) -> models.AVMOp:
    loc = op.source_location
    match op:
        case teal.TemplateVar() | teal.Int() | teal.Byte():
            raise InternalError(f"{op} should have been eliminated during TEAL phase", loc)
        case teal.IntBlock(constants=constants):
            return models.AVMOp(
                op_code=op.op_code,
                immediates=[_resolve_template_vars(ctx, int, constants.items())],
                source_location=loc,
            )
        case teal.BytesBlock(constants=constants):
            return models.AVMOp(
                op_code=op.op_code,
                immediates=[
                    _resolve_template_vars(ctx, bytes, [(b, es[1]) for b, es in constants.items()])
                ],
                source_location=loc,
            )
        case teal.PushBytes(value=bytes_value):
            return models.AVMOp(
                op_code=op.op_code,
                immediates=[bytes_value],
                source_location=loc,
            )
        case teal.PushBytess(values=values):
            return models.AVMOp(
                op_code=op.op_code,
                immediates=[[t[0] for t in values]],
                source_location=loc,
            )
        case teal.PushInts(values=values):
            return models.AVMOp(
                op_code=op.op_code,
                immediates=[values],
                source_location=loc,
            )
        case teal.CallSub(target=label_id):
            return models.AVMOp(
                op_code=op.op_code,
                immediates=[models.Label(name=label_id)],
                source_location=loc,
            )
        case teal.TealOp(op_code="b" | "bz" | "bnz", immediates=[str(label_id)]):
            return models.AVMOp(
                op_code=op.op_code,
                immediates=[models.Label(name=label_id)],
                source_location=loc,
            )
        case teal.TealOp(
            op_code="switch" | "match" as op_code, immediates=label_ids
        ) if _is_sequence(label_ids, str):
            return models.AVMOp(
                op_code=op_code,
                immediates=[[models.Label(label_id) for label_id in label_ids]],
                source_location=loc,
            )
        case teal.TealOp() if op.op_code not in _BRANCHING_OPS:
            return models.AVMOp(op_code=op.op_code, immediates=op.immediates, source_location=loc)
        case _:
            raise InternalError(f"invalid teal op: {op}", loc)


_T = typing.TypeVar("_T")


def _resolve_template_vars(
    ctx: AssembleContext, typ: type[_T], values: Iterable[tuple[_T | str, SourceLocation | None]]
) -> Sequence[_T]:
    result = []
    for value_or_template, var_loc in values:
        if not isinstance(value_or_template, str):
            value: _T = value_or_template
        else:
            try:
                maybe_value, val_loc = ctx.template_variables[value_or_template]
            except KeyError:
                raise CodeError(
                    f"template variable not defined: {value_or_template}", var_loc
                ) from None
            if not isinstance(maybe_value, typ):
                raise CodeError(
                    f"invalid template value type for {value_or_template!r},"
                    f" expected {typ.__name__}",
                    val_loc or var_loc,
                )
            value = maybe_value
        result.append(value)
    return result


def _encode_op(op: models.AVMOp, *, get_label_offset: Callable[[models.Label], int]) -> bytes:
    op_spec = op.op_spec
    bytecode = _encode_uint8(op.op_spec.code)
    for immediate_kind, immediate in zip(op_spec.immediates, op.immediates, strict=True):
        match immediate_kind:
            case ImmediateKind.uint8 if isinstance(immediate, int):
                bytecode += _encode_uint8(immediate)
            case ImmediateKind.int8 if isinstance(immediate, int):
                bytecode += _encode_int8(immediate)
            case ImmediateEnum(codes=enum_codes) if isinstance(immediate, str):
                immediate_code = enum_codes[immediate]
                bytecode += _encode_uint8(immediate_code)
            case ImmediateKind.bytes if isinstance(immediate, bytes):
                bytecode += _encode_bytes(immediate)
            case ImmediateKind.varuint if isinstance(immediate, int):
                bytecode += _encode_varuint(immediate)
            case ImmediateKind.varuint_array if _is_sequence(immediate, int):
                bytecode += _encode_varuint_array(immediate)
            case ImmediateKind.bytes_array if _is_sequence(immediate, bytes):
                bytecode += _encode_bytes_array(immediate)
            case ImmediateKind.label if isinstance(immediate, models.Label):
                offset = get_label_offset(immediate)
                bytecode += _encode_label(offset)
            case ImmediateKind.label_array if _is_sequence(immediate, models.Label):
                offsets = [get_label_offset(label) for label in immediate]
                bytecode += _encode_label_array(offsets)
            case _:
                raise InternalError(f"Invalid op: {op}")
    return bytecode


_encode_uint8 = struct.Struct(">B").pack
_encode_int8 = struct.Struct(">b").pack
_encode_label = struct.Struct(">h").pack


def _encode_varuint(value: int) -> bytes:
    bits = value & 0x7F
    value >>= 7
    result = b""
    while value:
        result += _encode_uint8(0x80 | bits)
        bits = value & 0x7F
        value >>= 7
    return result + _encode_uint8(bits)


def _encode_bytes(value: bytes) -> bytes:
    return _encode_varuint(len(value)) + value


def _encode_varuint_array(values: Sequence[int]) -> bytes:
    return b"".join((_encode_varuint(len(values)), *map(_encode_varuint, values)))


def _encode_label_array(values: Sequence[int]) -> bytes:
    # note: op spec describes a label array size as a varuint
    #       however actual algod go implementation is just a single byte
    #       additionally max number of labels is 255
    return b"".join((_encode_uint8(len(values)), *map(_encode_label, values)))


def _encode_bytes_array(values: Sequence[bytes]) -> bytes:
    return b"".join(
        (
            _encode_varuint(len(values)),
            *map(_encode_bytes, values),
        ),
    )


def _is_sequence[_T](maybe: object, typ: type[_T]) -> typing.TypeGuard[Sequence[_T]]:
    return isinstance(maybe, Sequence) and all(isinstance(m, typ) for m in maybe)
