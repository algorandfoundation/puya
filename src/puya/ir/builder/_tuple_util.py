from collections.abc import Sequence

from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir.models import Value, ValueProvider, ValueTuple
from puya.ir.types_ import get_wtype_arity, sum_wtypes_arity
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
