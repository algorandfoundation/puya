from collections.abc import Mapping

import attrs
from cattrs.preconf.json import make_converter

from puya.ussemble import models
from puya.ussemble.visitor import AVMVisitor


@attrs.frozen
class DebugOutput:
    version: int
    sources: list[str]
    names: list[str]
    mappings: str


_converter = make_converter()


def build_debug_info(source_map: Mapping[int, models.Node]) -> bytes:
    mappings = []

    names = sorted(set(map(_get_op_desc, source_map.values())))
    files = sorted(
        map(str, {s.source_location.file for s in source_map.values() if s.source_location})
    )
    source_index = 0
    line = 0
    column = 0
    previous_source_index = 0
    previous_line = 0
    previous_column = 0
    previous_name_index = 0
    for pc in range(max(source_map) + 1):
        try:
            op = source_map[pc]
        except KeyError:
            mappings.append("")
            continue
        name_index = names.index(_get_op_desc(op))
        loc = op.source_location
        if loc and loc.file.exists():
            source_index = files.index(str(loc.file))
            line = loc.line - 1  # make 0-indexed
            column = 0  # loc.column or 0

        mappings.append(
            _base64vlq_encode(
                0,  # generated col offset, always 0 for AVM byte code
                source_index - previous_source_index,
                line - previous_line,
                column - previous_column,
                name_index - previous_name_index,
            )
        )
        previous_source_index = source_index
        previous_line = line
        previous_column = column
        previous_name_index = name_index

    debug = DebugOutput(
        version=3,
        sources=files,
        names=names,
        mappings=";".join(mappings),
    )
    json = _converter.dumps(debug, DebugOutput)
    return json.encode("utf-8")


def _get_op_desc(op: models.Node) -> str:
    return op.accept(OpDescription()).rstrip()


def _base64vlq_encode(*values: int) -> str:
    """Encode integers to a VLQ value"""
    results = []

    b64_chars = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    b64_encode = b64_chars.decode().__getitem__
    shift = 5
    flag = 1 << shift
    mask = flag - 1

    for v in values:
        # add sign bit
        v = (abs(v) << 1) | int(v < 0)
        while True:
            to_encode = v & mask
            v >>= shift
            results.append(b64_encode(to_encode | (v and flag)))
            if not v:
                break
    return "".join(results)


class OpDescription(AVMVisitor[str]):
    def visit_int_block(self, block: models.IntBlock) -> str:
        return f"{block.op_code} {' '.join(map(str, block.constants))}"

    def visit_bytes_block(self, block: models.BytesBlock) -> str:
        return f"{block.op_code} {' '.join(map(_bytes_desc, block.constants))}"

    def visit_intc(self, load: models.IntC) -> str:
        return f"{load.op_code} {load.index}"

    def visit_bytesc(self, load: models.BytesC) -> str:
        return f"{load.op_code} {load.index}"

    def visit_push_int(self, load: models.PushInt) -> str:
        return f"{load.op_code} {load.value}"

    def visit_push_ints(self, load: models.PushInts) -> str:
        return f"{load.op_code} {' '.join(map(str, load.values))}"

    def visit_push_bytes(self, load: models.PushBytes) -> str:
        return f"{load.op_code} {_bytes_desc(load.value)}"

    def visit_push_bytess(self, load: models.PushBytess) -> str:
        return f"{load.op_code} {' '.join(map(_bytes_desc, load.values))}"

    def visit_jump(self, jump: models.Jump) -> str:
        return f"{jump.op_code} {jump.label.name}"

    def visit_multi_jump(self, jump: models.MultiJump) -> str:
        return f"{jump.op_code} {' '.join([label.name for label in jump.labels])}"

    def visit_label(self, jump: models.Label) -> str:
        return f"{jump.name}:"

    def visit_intrinsic(self, intrinsic: models.Intrinsic) -> str:
        return f"{intrinsic.op_code} {' '.join(map(str, intrinsic.immediates))}"


def _bytes_desc(value: bytes) -> str:
    return value.hex()
