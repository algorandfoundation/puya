import struct
import typing
from collections.abc import Collection

from puya.errors import InternalError
from puya.ussemble import models, visitor
from puya.ussemble._utils import get_label_indexes
from puya.ussemble.context import AssembleContext
from puya.ussemble.op_spec import OP_SPECS
from puya.ussemble.op_spec_models import ImmediateEnum, ImmediateKind


class AssembleVisitor(visitor.AVMVisitor[bytes]):
    def __init__(self, ctx: AssembleContext, ops: list[models.Node]) -> None:
        self._ctx = ctx
        self._ops = ops
        self._label_indexes = get_label_indexes(ops)
        self._op_pc = dict[int, int]()
        self._op_index = 0
        self.bytecode = self._assemble()

    def _assemble(self) -> list[bytes]:
        pc = 0
        # first pass to collect PC
        for op_index, op in enumerate(self._ops):
            self._op_index = op_index
            self._op_pc[op_index] = pc
            op_bytecode = op.accept(self)
            pc = pc + len(op_bytecode)

        # second pass to get bytecode
        bytecode = []
        for op_index, op in enumerate(self._ops):
            self._op_index = op_index
            bytecode.append(op.accept(self))

        return bytecode

    @classmethod
    def assemble(cls, ctx: AssembleContext, ops: list[models.Node]) -> bytes:
        return b"".join(
            (
                _encode_uint8(ctx.options.target_avm_version),
                *cls(ctx, ops).bytecode,
            )
        )

    def visit_intrinsic(self, intrinsic: models.Intrinsic) -> bytes:
        op_spec = OP_SPECS[intrinsic.op_code]
        bytecode = _encode_opcode(intrinsic.op_code)
        for immediate_kind, immediate in zip(
            op_spec.immediates, intrinsic.immediates, strict=True
        ):
            match immediate_kind:
                case ImmediateKind.uint8 if isinstance(immediate, int):
                    bytecode += _encode_uint8(immediate)
                case ImmediateKind.int8 if isinstance(immediate, int):
                    bytecode += _encode_int8(immediate)
                case ImmediateEnum(codes=enum_codes) if isinstance(immediate, str):
                    immediate_code = enum_codes[immediate]
                    bytecode += _encode_uint8(immediate_code)
                case _:  # other immediate types only appear in other AVMOps
                    raise InternalError(f"Invalid immediate type, expected: {immediate_kind}")
        return bytecode

    def visit_jump(self, jump: models.Jump) -> bytes:
        offset = self._get_offset_from_end(jump.label)
        return _encode_opcode(jump.op_code) + _encode_int16(offset)

    def visit_multi_jump(self, jump: models.MultiJump) -> bytes:
        offsets = [self._get_offset_from_end(label) for label in jump.labels]
        length = len(offsets)
        return _encode_opcode(jump.op_code) + b"".join(
            (_encode_uint8(length), *map(_encode_int16, offsets))
        )

    @typing.override
    def visit_label(self, label: models.Label) -> bytes:
        return b""

    def _get_offset_from_end(self, label: models.Label) -> int:
        label_index = self._ops.index(label)
        try:
            return self._op_pc[label_index] - self._op_pc[self._op_index + 1]
        except KeyError:  # during first pass offsets will not be present
            return 0

    def visit_bytes_block(self, block: models.BytesBlock) -> bytes:
        return _encode_opcode("bytecblock") + _encode_bytes_array(block.constants.keys())

    def visit_int_block(self, block: models.IntBlock) -> bytes:
        return _encode_opcode("intcblock") + _encode_int_array(block.constants.keys())

    def visit_push_bytes(self, load: models.PushBytes) -> bytes:
        return _encode_opcode("pushbytes") + _encode_bytes(load.value)

    def visit_push_bytess(self, load: models.PushBytess) -> bytes:
        return _encode_opcode("pushbytess") + _encode_bytes_array(load.values)

    def visit_push_int(self, load: models.PushInt) -> bytes:
        return _encode_opcode("pushint") + _encode_varuint(load.value)

    def visit_push_ints(self, load: models.PushInts) -> bytes:
        return _encode_opcode("pushints") + _encode_int_array(load.values)

    def visit_bytesc(self, load: models.BytesC) -> bytes:
        index = load.index
        if index < 4:
            return _encode_opcode(f"bytec_{index}")
        else:
            return _encode_opcode("bytec") + _encode_uint8(index)

    def visit_intc(self, load: models.IntC) -> bytes:
        index = load.index
        if index < 4:
            return _encode_opcode(f"intc_{index}")
        else:
            return _encode_opcode("intc") + _encode_uint8(index)


_encode_uint8 = struct.Struct(">B").pack
_encode_int8 = struct.Struct(">b").pack
_encode_int16 = struct.Struct(">h").pack


def _encode_bytes(value: bytes) -> bytes:
    return _encode_varuint(len(value)) + value


def _encode_opcode(op_code: str) -> bytes:
    return _encode_uint8(OP_SPECS[op_code].code)


def _encode_varuint(value: int) -> bytes:
    bits = value & 0x7F
    value >>= 7
    result = b""
    while value:
        result += _encode_uint8(0x80 | bits)
        bits = value & 0x7F
        value >>= 7
    return result + _encode_uint8(bits)


def _encode_bytes_array(values: Collection[bytes]) -> bytes:
    return b"".join(
        (
            _encode_varuint(len(values)),
            *map(_encode_bytes, values),
        ),
    )


def _encode_int_array(values: Collection[int]) -> bytes:
    return b"".join((_encode_varuint(len(values)), *map(_encode_varuint, values)))
