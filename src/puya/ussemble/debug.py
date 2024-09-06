from collections.abc import Mapping, Sequence

import attrs
from cattrs.preconf.json import make_converter
from cattrs.strategies import configure_tagged_union

from puya.ussemble import models
from puya.ussemble.context import AssembleContext
from puya.ussemble.visitor import AVMVisitor


@attrs.frozen
class EnterFunction:
    name: str
    params: Mapping[str, str]
    returns: Sequence[str]


@attrs.frozen
class ExitFunction:
    pass


@attrs.frozen
class AddToStack:
    add: list[str] = attrs.field(factory=list)
    """names of variables added to stack"""


@attrs.frozen
class RemoveFromStack:
    remove: int = 0
    """number of variables removed from stack"""


Event = EnterFunction | ExitFunction | AddToStack | RemoveFromStack


@attrs.frozen
class DebugOutput:
    version: int
    sources: list[str]
    names: list[str]
    mappings: str
    pc_events: Mapping[int, Event]


_converter = make_converter()
configure_tagged_union(Event, _converter)


def build_debug_info(
    context: AssembleContext, program_id: str, source_map: Mapping[int, models.Node]
) -> bytes:
    names = sorted(set(map(_get_op_desc, source_map.values())))
    files = sorted(
        map(str, {s.source_location.file for s in source_map.values() if s.source_location})
    )
    mappings = _get_src_mappings(source_map, files, names)
    events = _get_pc_events(context, program_id, source_map)

    debug = DebugOutput(
        version=3,
        sources=files,
        names=names,
        mappings=";".join(mappings),
        pc_events=events,
    )
    json = _converter.dumps(debug, DebugOutput, indent=2)
    return json.encode("utf-8")


def _get_pc_events(
    context: AssembleContext, program_id: str, source_map: Mapping[int, models.Node]
) -> Mapping[int, Event]:
    events = {}

    for pc, node in source_map.items():
        event: Event
        match node:
            case models.Jump(op_code="callsub", label=models.Label(name=func)):
                func_debug = context.debug.function_debug[(program_id, func)]
                event = EnterFunction(
                    name=str(func_debug.full_name),
                    params=func_debug.params,
                    returns=func_debug.returns,
                )
            case models.Intrinsic(op_code="retsub"):
                event = ExitFunction()
            case _:
                continue
        events[pc] = event
    return events


def _get_src_mappings(
    source_map: Mapping[int, models.Node], files: Sequence[str], names: Sequence[str]
) -> list[str]:
    mappings = []

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
    return mappings


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
