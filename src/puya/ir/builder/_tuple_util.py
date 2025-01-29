from collections.abc import Sequence

from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Register, Value, ValueProvider, ValueTuple
from puya.ir.types_ import (
    EncodedTupleType,
    IRType,
    get_wtype_arity,
    sum_wtypes_arity,
    wtype_to_ir_type,
)
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation


def get_tuple_item_values(
    *,
    tuple_values: Sequence[Value],
    tuple_wtype: wtypes.WTuple,
    index: int | tuple[int, int | None],
    target_wtype: wtypes.WType,
    source_location: SourceLocation,
) -> ValueProvider:
    if isinstance(index, tuple):
        skip_values = sum_wtypes_arity(tuple_wtype.types[: index[0]])
        target_arity = sum_wtypes_arity(tuple_wtype.types[index[0] : index[1]])
    else:
        skip_values = sum_wtypes_arity(tuple_wtype.types[:index])
        target_arity = get_wtype_arity(tuple_wtype.types[index])

    if target_arity != get_wtype_arity(target_wtype):
        raise InternalError(
            "arity difference between result type and expected type", source_location
        )

    values = tuple_values[skip_values : skip_values + target_arity]

    if len(values) == 1 and not isinstance(target_wtype, wtypes.WTuple):
        return values[0]
    return ValueTuple(values=values, source_location=source_location)


def build_tuple_registers(
    context: IRFunctionBuildContext,
    base_name: str,
    typ: wtypes.WType | IRType,
    source_location: SourceLocation | None,
) -> list[Register]:
    return [
        context.new_register(name, ir_type, source_location)
        for name, ir_type in build_tuple_item_names(base_name, typ, source_location)
    ]


def build_tuple_item_names(
    base_name: str,
    typ: wtypes.WType | IRType,
    source_location: SourceLocation | None,
) -> list[tuple[str, IRType]]:
    if isinstance(typ, wtypes.WTuple):
        return [
            reg
            for idx, item_type in enumerate(typ.types)
            for reg in build_tuple_item_names(
                format_tuple_index(typ, base_name, idx), item_type, source_location
            )
        ]
    elif isinstance(typ, wtypes.WType):
        return [(base_name, wtype_to_ir_type(typ, source_location))]
    elif isinstance(typ, EncodedTupleType):
        return [
            reg
            for idx, item_type in enumerate(typ.elements)
            for reg in build_tuple_item_names(
                format_tuple_index(None, base_name, idx), item_type, source_location
            )
        ]
    elif isinstance(typ, IRType):
        return [(base_name, typ)]
