from collections import deque
from collections.abc import Iterator

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.ir import models
from puya.ir.models import Parameter, Subroutine
from puya.ir.types_ import wtype_to_ir_type, wtype_to_ir_types
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation
from puya.utils import set_add


def bfs_block_order(start: models.BasicBlock) -> Iterator[models.BasicBlock]:
    q = deque((start,))
    visited = {start}
    while q:
        block = q.popleft()
        yield block
        q.extend(succ for succ in block.successors if set_add(visited, succ))


def make_subroutine(func: awst_nodes.Function, *, allow_implicits: bool) -> Subroutine:
    """Pre-construct subroutine with an empty body"""
    parameters = [
        param
        for arg in func.args
        for param in _expand_tuple_parameters(
            arg.name,
            arg.wtype,
            allow_implicits=allow_implicits,
            source_location=arg.source_location,
        )
    ]
    returns = wtype_to_ir_types(func.return_type, func.source_location)
    return Subroutine(
        id=func.full_name,
        short_name=func.short_name,
        parameters=parameters,
        returns=returns,
        body=[],
        inline=func.inline,
        source_location=func.source_location,
    )


def _expand_tuple_parameters(
    name: str, typ: wtypes.WType, *, allow_implicits: bool, source_location: SourceLocation
) -> Iterator[Parameter]:
    if isinstance(typ, wtypes.WTuple):
        for item_idx, item_type in enumerate(typ.types):
            item_name = format_tuple_index(typ, name, item_idx)
            yield from _expand_tuple_parameters(
                item_name,
                item_type,
                allow_implicits=allow_implicits,
                source_location=source_location,
            )
    else:
        yield Parameter(
            name=name,
            ir_type=wtype_to_ir_type(typ, source_location),
            version=0,
            implicit_return=(
                allow_implicits and not (typ.immutable or isinstance(typ, wtypes.ReferenceArray))
            ),
            source_location=source_location,
        )
