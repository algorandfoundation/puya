import enum
import itertools
import struct
import typing
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence

from puya import log
from puya.algo_constants import HASH_PREFIX_PROGRAM
from puya.compilation_artifacts import DebugEvent
from puya.errors import InternalError
from puya.parse import SourceLocation
from puya.teal import models as teal
from puya.teal.stack_manipulations import apply_stack_manipulations
from puya.ussemble import models
from puya.ussemble.context import AssembleContext
from puya.ussemble.debug import build_debug_info
from puya.ussemble.models import AVMOp
from puya.ussemble.op_spec import OP_SPECS
from puya.ussemble.op_spec_models import ImmediateEnum, ImmediateKind, OpSpec
from puya.utils import is_edwards25519_point, sha512_256_hash

logger = log.get_logger(__name__)

_AVM_VARINT_BRANCH_VERSION = 13
# `varintBranchInitialSize` in go-algorand assemble
_VARINT_BRANCH_INITIAL_SIZE = 3
# `assemblerSaltSearchLimit` in go-algorand assemble. 0..127 candidates are tried.
# Probability of all being on-curve is ~2^-128.
_ASSEMBLER_SALT_SEARCH_LIMIT = 128

_BRANCHING_OPS = {
    op.name
    for op in OP_SPECS.values()
    if any(i in (ImmediateKind.label, ImmediateKind.label_array) for i in op.immediates)
}
# note multi-branch (switch, match) remain the same for now
_VARINT_BRANCHING_OPS = {"b", "bz", "bnz", "callsub"}
_CONSTANT_OPS = {
    op.name for op in OP_SPECS.values() if op.name.startswith(("intc", "bytec", "push"))
}
_STACK_OPS = {
    "popn",
    "dupn",
    "pop",
    "dup",
    "dup2",
    "dig",
    "bury",
    "swap",
    "cover",
    "uncover",
    "frame_dig",
    "frame_bury",
}
assert _STACK_OPS <= OP_SPECS.keys(), "invalid stack op"  # noqa: SIM300


def assemble_bytecode_and_debug_info(
    ctx: AssembleContext, program: teal.TealProgram
) -> models.AssembledProgram:
    version_bytes = _encode_varuint(program.avm_version)
    use_varint_branches = program.avm_version >= _AVM_VARINT_BRANCH_VERSION
    pc_events = defaultdict[int, DebugEvent](lambda: DebugEvent())

    lowered_ops = list[models.AVMOp]()
    label_op_index = dict[str, int]()
    error_messages = dict[int, str]()

    # first pass does avm op lowering, caching labels and error messages
    for subroutine in program.all_subroutines:
        for block in subroutine.blocks:
            assert block.label not in label_op_index, "expected unique block labels"
            label_op_index[block.label] = len(lowered_ops)
            for op in block.ops:
                if isinstance(op, teal.Intrinsic | teal.Assert | teal.Err) and op.error_message:
                    error_messages[len(lowered_ops)] = op.error_message
                lowered_ops.append(_lower_op(ctx, op))

    # second pass calculates pcs and resolves varint branch offsets
    pcs, branch_offsets = _compute_pcs(
        lowered_ops,
        label_op_index,
        start_pc=len(version_bytes),
        varint_branches=use_varint_branches,
    )
    label_pcs = {label: pcs[index] for label, index in label_op_index.items()}
    pc_ops = {pcs[index]: avm_op for index, avm_op in enumerate(lowered_ops)}

    # populate pc_events for every op in pc order
    for index in range(len(lowered_ops)):
        event = pc_events[pcs[index]]
        if index in error_messages:
            event["error"] = error_messages[index]
    op_stats = defaultdict[_OpKind, list[int]](list)

    # iterate again to capture debug info using calculated pcs
    if ctx.options.debug_level:
        function_block_ids = {s.blocks[0].label: s.signature.name for s in program.all_subroutines}
        pcs_iter = iter(pcs)
        pc = next(pcs_iter)
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
                current_event["block"] = block.label
                current_event["stack_in"] = stack.copy()
                defined = set[str]()

                for op in block.ops:
                    _add_op_debug_events(
                        pc_events[pc],
                        function_block_ids,
                        op,
                        # note: stack & defined are mutated
                        stack,
                        defined,
                    )
                    pc = next(pcs_iter)

    # third pass assembles final byte code
    bytecode = [version_bytes]
    for op_index, avm_op in enumerate(lowered_ops):

        def get_label_offset(label: models.Label) -> int:
            # label offset for varuint branches already cached
            # label offset for AVM v<13 or non varuint branches is the
            # signed PC difference between the label PC location and
            # the end of the current op
            return branch_offsets.get(op_index, label_pcs[label.name] - pcs[op_index + 1])  # noqa: B023

        op_bytes = _encode_op(
            avm_op, get_label_offset=get_label_offset, varint_label_immediates=use_varint_branches
        )
        bytecode.append(op_bytes)

        op_kind = _get_op_kind(avm_op)
        op_stats[op_kind].append(len(op_bytes))

    program_bytecode = b"".join(bytecode)
    final_bytecode = (
        program_bytecode if not program.autosalt else _apply_autosalt(program_bytecode)
    )
    salt = final_bytecode[len(program_bytecode) :]
    if salt:
        op_stats[_OpKind.constant].append(len(salt))

    return models.AssembledProgram(
        bytecode=final_bytecode,
        debug_info=build_debug_info(ctx, pc_ops, pc_events),
        template_variables={
            var: ctx.provided_template_variables.get(var, (None, None))[0]
            for var in ctx.template_variable_types
        },
        stats=_get_op_stats(op_stats),
        instruction_boundaries=pcs,
        salt=salt,
    )


def _program_hash_on_curve(program: bytes) -> bool:
    return is_edwards25519_point(sha512_256_hash(HASH_PREFIX_PROGRAM + program))


def _apply_autosalt(program: bytes) -> bytes:
    """Append a trailing intcblock salt so the program hash is off-curve (as needed)."""
    # program is already off-curve, return as is
    if not _program_hash_on_curve(program):
        return program

    intcblock_code = OP_SPECS["intcblock"].code
    for salt in range(_ASSEMBLER_SALT_SEARCH_LIMIT):
        # trailing `intcblock 1 <salt>` constant block to alter the hash
        candidate = program + bytes((intcblock_code, 1, salt))
        if not _program_hash_on_curve(candidate):
            return candidate
    raise InternalError(
        "could not find a trailing intcblock salt that yields an off-curve program"
    )


class _OpKind(enum.Enum):
    constant = enum.auto()
    control_flow = enum.auto()
    stack = enum.auto()
    other = enum.auto()


def _get_op_kind(op: AVMOp) -> _OpKind:
    if op.op_code in _BRANCHING_OPS:
        return _OpKind.control_flow
    elif op.op_code in _CONSTANT_OPS:
        return _OpKind.constant
    elif op.op_code in _STACK_OPS:
        return _OpKind.stack
    else:
        return _OpKind.other


def _get_op_stats(op_stats: Mapping[_OpKind, list[int]]) -> Mapping[str, int]:
    result = {
        "total_bytes": 1,  # 1 byte for program version
        "total_ops": 0,
    }
    for kind in _OpKind:
        kind_stats = op_stats[kind]
        num_bytes = sum(kind_stats)
        num_ops = len(kind_stats)
        result[f"{kind.name}_bytes"] = num_bytes
        result[f"{kind.name}_ops"] = num_ops
        result["total_bytes"] += num_bytes
        result["total_ops"] += num_ops
    return result


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
    event["op"] = op.teal(with_comments=True)

    apply_stack_manipulations(op.stack_manipulations, stack=stack, defined=defined)

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
        case teal.TealOp(op_code="switch" | "match" as op_code, immediates=label_ids) if (
            _is_sequence(label_ids, str)
        ):
            return models.AVMOp(
                op_code=op_code,
                immediates=[[models.Label(label_id) for label_id in label_ids]],
                source_location=loc,
            )
        case teal.TealOp() if op.op_code not in _BRANCHING_OPS:
            return models.AVMOp(op_code=op.op_code, immediates=op.immediates, source_location=loc)
        case _:
            raise InternalError(f"invalid teal op: {op}", loc)


def _resolve_template_vars[T: (int, bytes)](
    ctx: AssembleContext, typ: type[T], values: Iterable[tuple[T | str, SourceLocation | None]]
) -> Sequence[T]:
    result = []
    for value_or_template, var_loc in values:
        if not isinstance(value_or_template, str):
            value = value_or_template
        else:
            try:
                maybe_value, val_loc = ctx.provided_template_variables[value_or_template]
            except KeyError:
                # if bytecode isn't required for this program, then a dummy value is sufficient
                bytecode_required = ctx.options.output_bytecode and (
                    ctx.artifact_ref in ctx.compilation_set
                )
                if ctx.is_reference or bytecode_required:
                    logger.error(  # noqa: TRY400
                        f"template variable not defined: {value_or_template}", location=var_loc
                    )
                value = typ()
            else:
                if isinstance(maybe_value, typ):
                    value = maybe_value
                else:
                    logger.error(
                        f"invalid template value type for {value_or_template!r},"
                        f" expected {typ.__name__}",
                        location=val_loc or var_loc,
                    )
                    value = typ()
        result.append(value)
    return result


def _compute_pcs(
    ops: Sequence[models.AVMOp],
    label_op_index: Mapping[str, int],
    *,
    start_pc: int,
    varint_branches: bool,
) -> tuple[list[int], dict[int, int]]:
    op_sizes = list[int]()
    varint_branch_indexes = list[int]()
    for index, op in enumerate(ops):
        # actual label offsets can't be determined until all PC values are known
        # so just use placeholder values initially
        if varint_branches and op.op_code in _VARINT_BRANCHING_OPS:
            varint_branch_indexes.append(index)
            # placeholder: opcode byte(s) + maximum branch offset size
            op_sizes.append(_op_code_size(op.op_spec) + _VARINT_BRANCH_INITIAL_SIZE)
        else:
            op_size = len(
                _encode_op(
                    op, get_label_offset=lambda _: 0, varint_label_immediates=varint_branches
                )
            )
            assert op_size, "expected non empty bytecode"
            op_sizes.append(op_size)

    if not varint_branches:  # early exit for v<=12
        return list(itertools.accumulate(op_sizes, initial=start_pc)), {}

    branch_offsets = dict[int, int]()
    # iteratively shrink varint branch placeholders to the minimum size needed,
    # recomputing pcs until no changes are observed
    changed = True
    while changed:
        changed = False
        pcs = list(itertools.accumulate(op_sizes, initial=start_pc))
        for index in varint_branch_indexes:
            op = ops[index]
            (label,) = op.immediates
            assert isinstance(label, models.Label), "expected label immediate"
            op_start = pcs[index]
            op_end = pcs[index + 1]
            dest = pcs[label_op_index[label.name]]
            if dest == op_start:
                raise InternalError(
                    f"jump '{op.op_code}' to start of same instruction cannot be encoded",
                    op.source_location,
                )
            # back jumps are measured from the op start, forward jumps from the op end
            jump = (dest - op_start) if dest < op_start else (dest - op_end)
            branch_offsets[index] = jump
            needed = len(_encode_signed_varint(jump))
            if needed > _VARINT_BRANCH_INITIAL_SIZE:
                raise InternalError(
                    f"branch target for {op.op_code} is too far away",
                    op.source_location,
                )
            op_code_size = _op_code_size(op.op_spec)
            if needed < op_sizes[index] - op_code_size:
                op_sizes[index] = needed + op_code_size
                changed = True
    return pcs, branch_offsets


def _op_code_size(op_spec: OpSpec) -> int:
    """Number of opcode bytes: the prefix byte, plus a sub-opcode byte if present."""
    return 1 if op_spec.sub_code is None else 2


def _encode_op(
    op: models.AVMOp,
    *,
    get_label_offset: Callable[[models.Label], int],
    varint_label_immediates: bool,
) -> bytes:
    op_spec = op.op_spec
    bytecode = _encode_uint8(op_spec.code)
    if op_spec.sub_code is not None:
        bytecode += _encode_uint8(op_spec.sub_code)
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
                if varint_label_immediates:
                    bytecode += _encode_signed_varint(offset)
                else:
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


def _encode_signed_varint(value: int) -> bytes:
    # Go binary.Varint (zig-zag+ULEB128)
    zig_zag = (value << 1) ^ (value >> 63)
    return _encode_varuint(zig_zag)


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


def _is_sequence[T](maybe: object, typ: type[T]) -> typing.TypeGuard[Sequence[T]]:
    return isinstance(maybe, Sequence) and all(isinstance(m, typ) for m in maybe)
