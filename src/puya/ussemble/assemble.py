import struct
import typing
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence

from puya import log
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.teal import models as teal
from puya.ussemble import models
from puya.ussemble.context import AssembleContext
from puya.ussemble.debug import build_debug_info
from puya.ussemble.op_spec_models import ImmediateEnum, ImmediateKind

logger = log.get_logger(__name__)


class _AVMProgram:

    def __init__(self) -> None:
        self._ops = list[models.Node]()
        self._events = defaultdict[int, models.DebugEvent](models.DebugEvent)  # type: ignore[arg-type]

    @property
    def ops(self) -> Sequence[models.Node]:
        return self._ops

    def get_debug_info(self, index: int) -> models.DebugEvent:
        return self._events[index]

    def add_op(self, op: models.Node) -> None:
        self._ops.append(op)

    def add_debug_info(self, **info: typing.Unpack[models.DebugEvent]) -> None:
        self._events[len(self._ops)].update(info)


def assemble_bytecode(
    ctx: AssembleContext,
    teal_program: teal.TealProgram,
) -> models.AssembledProgram:
    program = _lower_ops(ctx, teal_program)
    node_pcs = dict[models.Node, int]()
    source_map = dict[int, models.AVMOp]()
    events = defaultdict[int, models.DebugEvent](models.DebugEvent)  # type: ignore[arg-type]

    version_bytes = _encode_varuint(ctx.options.target_avm_version)
    # pc includes version header
    pc = len(version_bytes)
    # first pass to collect PC fo each op
    for op in program.ops:
        node_pcs[op] = pc

        if not isinstance(op, models.Label):
            op_bytecode = _assemble_op(op, get_label_offset=lambda _: 0)
            pc = pc + len(op_bytecode)
    # dummy label to represent the end of the program
    end = models.Label("")
    node_pcs[end] = pc

    # second pass to get actual bytecode
    bytecode = [version_bytes]
    for op_index, (op, next_op) in enumerate(
        zip(program.ops, (*program.ops[1:], end), strict=True)
    ):

        def _get_label_offset(label: models.Label) -> int:
            return node_pcs[label] - node_pcs[next_op]  # noqa: B023

        pc = node_pcs[op]
        if isinstance(op, models.AVMOp):
            source_map[pc] = op
            bytecode.append(_assemble_op(op, get_label_offset=_get_label_offset))
        events[pc].update(program.get_debug_info(op_index))

    return models.AssembledProgram(
        bytecode=b"".join(bytecode),
        debug_info=build_debug_info(
            ctx,
            source_map,
            events,
        ),
    )


def _lower_ops(ctx: AssembleContext, program: teal.TealProgram) -> _AVMProgram:
    function_block_ids = {s.blocks[0].label: s.signature.name for s in program.all_subroutines}

    avm_program = _AVMProgram()

    for subroutine in program.all_subroutines:
        avm_program.add_debug_info(
            subroutine=subroutine.signature.name,
            params={p.local_id: p.atype.name or "" for p in subroutine.signature.parameters},
        )
        stack = list[str]()
        for block in subroutine.blocks:
            # update stack with correct values on entry to a block
            f_stack_height = block.entry_stack_height - len(block.x_stack_in)
            stack[f_stack_height:] = block.x_stack_in
            avm_program.add_op(models.Label(name=block.label))
            avm_program.add_debug_info(
                block=block.label,
                stack_in=stack.copy(),
            )

            for op in block.ops:
                stack_modified = False
                defined = list[str]()
                for sm in op.stack_manipulations:
                    match sm:
                        case teal.StackConsume(n=n):
                            for _ in range(n):
                                stack.pop()
                            stack_modified = True
                        case teal.StackExtend() as se:
                            stack.extend(se.local_ids)
                            if se.defined:
                                defined.extend(se.local_ids)
                            stack_modified = True
                        case teal.StackDefine() as sd:
                            defined.append(sd.local_id)
                        case teal.StackInsert() as si:
                            index = len(stack) - si.depth
                            stack.insert(index, si.local_id)
                            defined.append(si.local_id)
                            stack_modified = True
                        case teal.StackPop() as sp:
                            index = len(stack) - sp.depth - 1
                            stack.pop(index)
                            stack_modified = True
                        case _:
                            typing.assert_never(sm)

                if defined:
                    avm_program.add_debug_info(defined_out=sorted(set(defined) & set(stack)))
                if stack_modified:
                    avm_program.add_debug_info(stack_out=stack.copy())
                avm_op = _lower_op(ctx, op)
                match avm_op:
                    case models.AVMOp(
                        op_code="callsub", immediates=[models.Label(name=func_block)]
                    ):
                        avm_program.add_debug_info(callsub=function_block_ids[func_block])
                    case models.AVMOp(op_code="retsub"):
                        avm_program.add_debug_info(retsub=True)
                avm_program.add_debug_info(op=str(avm_op))
                avm_program.add_op(avm_op)
    return avm_program


def _lower_op(ctx: AssembleContext, op: teal.TealOp) -> models.AVMOp:
    loc = op.source_location
    match op:
        case teal.TemplateVar() | teal.Int() | teal.Byte():
            raise InternalError(f"{op} should not be present", loc)
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
        case teal.CallSub(target=label_id, op_code=op_code):
            return models.AVMOp(
                op_code=op_code,
                immediates=[models.Label(name=label_id)],
                source_location=loc,
            )
        case teal.TealOp(op_code="b" | "bz" | "bnz" as op_code, immediates=immediates):
            try:
                (maybe_label_id,) = immediates
            except ValueError:
                maybe_label_id = None
            if not isinstance(maybe_label_id, str):
                raise InternalError(
                    f"Invalid op code: {op.teal()}",
                    loc,
                )
            return models.AVMOp(
                op_code=op_code,
                immediates=[models.Label(name=maybe_label_id)],
                source_location=loc,
            )
        case teal.TealOp(op_code="switch" | "match" as op_code, immediates=immediates):
            labels = list[str]()
            for maybe_label in immediates:
                if not isinstance(maybe_label, str):
                    raise InternalError(
                        f"Invalid op code: {op.teal()}",
                        loc,
                    )
                labels.append(maybe_label)
            return models.AVMOp(
                op_code=op_code,
                immediates=[[models.Label(label) for label in labels]],
                source_location=loc,
            )
        case teal.TealOp(op_code=op_code, immediates=immediates):
            return models.AVMOp(op_code=op_code, immediates=immediates, source_location=loc)
        case _:
            typing.assert_never()


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


def _assemble_op(op: models.AVMOp, *, get_label_offset: Callable[[models.Label], int]) -> bytes:
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
            case _:  # other immediate types only appear in other AVMOps
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
