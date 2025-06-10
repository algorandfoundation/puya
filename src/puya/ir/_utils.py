from collections import deque
from collections.abc import Iterator, Sequence

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import InternalError
from puya.ir import (
    models,
    models as ir,
)
from puya.ir.encodings import ArrayEncoding, Encoding, TupleEncoding
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
        for param in _expand_tuple_parameters_and_mark_implicit_returns(
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


def _expand_tuple_parameters_and_mark_implicit_returns(
    name: str, typ: wtypes.WType, *, allow_implicits: bool, source_location: SourceLocation
) -> Iterator[Parameter]:
    if isinstance(typ, wtypes.WTuple):
        for item_idx, item_type in enumerate(typ.types):
            item_name = format_tuple_index(typ, name, item_idx)
            yield from _expand_tuple_parameters_and_mark_implicit_returns(
                item_name,
                item_type,
                allow_implicits=allow_implicits,
                source_location=source_location,
            )
    else:
        type_is_mutable = not typ.immutable
        type_is_slot = typ.is_reference
        yield Parameter(
            name=name,
            ir_type=wtype_to_ir_type(typ, source_location),
            version=0,
            implicit_return=(allow_implicits and type_is_mutable and not type_is_slot),
            source_location=source_location,
        )


def get_aggregate_element_encoding(
    aggregate_encoding: TupleEncoding | ArrayEncoding,
    indexes: Sequence[int | ir.Value],
    loc: SourceLocation | None,
) -> Encoding:
    last_i = len(indexes) - 1
    element_encoding = None
    for i, index in enumerate(indexes):
        if isinstance(aggregate_encoding, TupleEncoding) and isinstance(index, int):
            element_encoding = aggregate_encoding.elements[index]
        elif isinstance(aggregate_encoding, ArrayEncoding):
            element_encoding = aggregate_encoding.element
        else:
            raise InternalError(
                f"invalid index sequence: {aggregate_encoding=!s}, {index=!s}", loc
            )
        if i == last_i:
            # last index is the only one that doesn't need to be an aggregate
            pass
        elif isinstance(element_encoding, TupleEncoding | ArrayEncoding):
            aggregate_encoding = element_encoding
        else:
            # invalid index sequence
            raise InternalError(
                f"invalid index sequence: {aggregate_encoding=!s}, {index=!s}", loc
            )
    if element_encoding is None:
        raise InternalError(f"invalid index sequence: {aggregate_encoding=!s}, {indexes=!s}", loc)
    return element_encoding
