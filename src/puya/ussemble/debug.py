from collections.abc import Mapping, Sequence

from puya.compilation_artifacts import DebugEvent, DebugInfo
from puya.parse import SourceLocation
from puya.ussemble import models
from puya.ussemble.context import AssembleContext
from puya.utils import normalize_path


def build_debug_info(
    ctx: AssembleContext,
    pc_ops: Mapping[int, models.AVMOp],
    pc_events: Mapping[int, DebugEvent],
) -> DebugInfo:
    op_pc_offset = pc_offset = 0
    if ctx.offset_pc_from_constant_blocks:
        for idx, (pc, node) in enumerate(pc_ops.items()):
            # stop at first op that is not a constant block
            if node.op_code not in ("intcblock", "bytecblock"):
                # only need to set pc_offset if there was a constant block present (i.e. idx != 0)
                # this is because the first op will be after the version byte and so will always
                # have a pc of 1, but a op_pc_offset of 0 means the values are not offset
                if idx:
                    op_pc_offset = idx
                    pc_offset = pc
                break
    events = {pc - pc_offset: event for pc, event in pc_events.items() if pc >= pc_offset}
    source_map = {
        pc - pc_offset: node.source_location for pc, node in pc_ops.items() if pc >= pc_offset
    }

    files = sorted(map(normalize_path, {s.file for s in source_map.values() if s and s.file}))
    mappings = _get_src_mappings(source_map, files)

    return DebugInfo(
        version=3,
        sources=files,
        mappings=";".join(mappings),
        op_pc_offset=op_pc_offset,
        pc_events=events,
    )


def _get_src_mappings(
    source_map: Mapping[int, SourceLocation | None],
    files: Sequence[str],
) -> list[str]:
    mappings = []
    previous_source_index = 0
    previous_line = 0
    previous_column = 0
    for pc in range(max(source_map) + 1):
        loc = source_map.get(pc)
        if not loc or not loc.file:
            mappings.append("")
            continue
        source_index = files.index(normalize_path(loc.file))
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
