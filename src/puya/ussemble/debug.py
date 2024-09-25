from collections.abc import Mapping, Sequence

import attrs
from cattrs.preconf.json import make_converter

from puya.ussemble import models


@attrs.frozen
class Event:
    subroutine: str | None = None
    block: str | None = None
    op: str | None = None
    callsub: str | None = None
    retsub: bool = False
    params: Mapping[str, str] | None = None
    """Also defines the p-stack, which holds the parameters passed via the stack to a function"""
    stack_in: Sequence[str] | None = None
    stack_out: Sequence[str] | None = None
    """The variables defined relative to a function's current subroutine frame"""
    defined_out: Sequence[str] | None = None


@attrs.frozen
class DebugOutput:
    version: int
    sources: list[str]
    mappings: str
    op_pc_offset: int
    pc_events: Mapping[int, Event]


_converter = make_converter(omit_if_default=True)


def build_debug_info(
    source_map: Mapping[int, models.Node],
    events: Mapping[int, Event],
    *,
    offset_pc_from_constant_blocks: bool,
) -> bytes:
    files = sorted(
        map(str, {s.source_location.file for s in source_map.values() if s.source_location})
    )
    op_pc_offset = pc_offset = 0
    if offset_pc_from_constant_blocks:
        for idx, (pc, node) in enumerate(source_map.items()):
            # stop at first op that is not a constant block
            if not isinstance(node, models.IntBlock | models.BytesBlock):
                op_pc_offset = idx
                pc_offset = pc
                break
    events = {pc - pc_offset: event for pc, event in events.items() if pc >= pc_offset}
    source_map = {pc - pc_offset: node for pc, node in source_map.items() if pc >= pc_offset}
    mappings = _get_src_mappings(source_map, files)

    debug = DebugOutput(
        version=3,
        sources=files,
        mappings=";".join(mappings),
        op_pc_offset=op_pc_offset,
        pc_events=events,
    )
    json = _converter.dumps(debug, DebugOutput, indent=2)
    return json.encode("utf-8")


def _get_src_mappings(
    source_map: Mapping[int, models.Node],
    files: Sequence[str],
) -> list[str]:
    mappings = []

    previous_source_index = 0
    previous_line = 0
    previous_column = 0
    for pc in range(max(source_map) + 1):
        try:
            op = source_map[pc]
        except KeyError:
            mappings.append("")
            continue
        else:
            loc = op.source_location
            if not loc or not loc.file:
                mappings.append("")
                continue
        source_index = files.index(str(loc.file))
        line = loc.line - 1  # make 0-indexed
        column = loc.column or 0

        mappings.append(
            _base64vlq_encode(
                0,  # generated col offset, always 0 for AVM byte code
                source_index - previous_source_index,
                line - previous_line,
                column - previous_column,
            )
        )
        previous_source_index = source_index
        previous_line = line
        previous_column = column
    return mappings


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


def _bytes_desc(value: bytes) -> str:
    return value.hex()
