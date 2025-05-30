from puya.awst import wtypes
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Register
from puya.ir.types_ import IRType, wtype_to_ir_type
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation


def build_tuple_registers(
    context: IRFunctionBuildContext,
    base_name: str,
    wtype: wtypes.WType,
    source_location: SourceLocation,
) -> list[Register]:
    return [
        context.new_register(name, ir_type, source_location)
        for name, ir_type in build_tuple_item_names(base_name, wtype, source_location)
    ]


def build_tuple_item_names(
    base_name: str,
    wtype: wtypes.WType,
    source_location: SourceLocation,
) -> list[tuple[str, IRType]]:
    if not isinstance(wtype, wtypes.WTuple):
        return [(base_name, wtype_to_ir_type(wtype, source_location))]
    return [
        reg
        for idx, item_type in enumerate(wtype.types)
        for reg in build_tuple_item_names(
            format_tuple_index(wtype, base_name, idx), item_type, source_location
        )
    ]
