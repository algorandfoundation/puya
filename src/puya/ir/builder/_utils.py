from collections.abc import Sequence

from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.models import (
    TMP_VAR_INDICATOR,
    InvokeSubroutine,
    Register,
    Undefined,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.op_utils import assign_targets, convert_constants, mktemp
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import IRType, TupleIRType, ir_type_to_ir_types, wtype_to_ir_type
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation


def assign(
    context: IRRegisterContext,
    source: ValueProvider,
    *,
    name: str,
    ir_type: IRType | None = None,
    assignment_location: SourceLocation | None,
    register_location: SourceLocation | None = None,
) -> Register:
    if ir_type is None:
        (ir_type,) = source.types
    target = context.new_register(name, ir_type, register_location or assignment_location)
    assign_targets(
        context=context,
        source=source,
        targets=[target],
        assignment_location=assignment_location,
    )
    return target


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


def assign_tuple(
    context: IRRegisterContext,
    source: ValueProvider,
    *,
    typed_names: Sequence[tuple[str, IRType]],
    assignment_location: SourceLocation | None,
    register_location: SourceLocation | None = None,
) -> list[Register]:
    if register_location is None:
        register_location = assignment_location
    targets = [
        context.new_register(name, ir_type, register_location) for name, ir_type in typed_names
    ]
    assign_targets(
        context=context,
        source=source,
        targets=targets,
        assignment_location=assignment_location,
    )
    return targets


def assign_temp(
    context: IRRegisterContext,
    source: ValueProvider,
    *,
    temp_description: str,
    source_location: SourceLocation | None,
) -> Register:
    (ir_type,) = source.types
    target = mktemp(context, ir_type, source_location, description=temp_description)
    assign_targets(
        context,
        source=source,
        targets=[target],
        assignment_location=source_location,
    )
    return target


def get_implicit_return_is_original(var_name: str) -> str:
    return f"{var_name}{TMP_VAR_INDICATOR}is_original"


def get_implicit_return_out(var_name: str) -> str:
    return f"{var_name}{TMP_VAR_INDICATOR}out"


def undefined_value(typ: IRType | TupleIRType, loc: SourceLocation) -> ValueProvider:
    """For a given WType, produce an "undefined" ValueProvider of the correct arity.

    It is invalid to request an "undefined" value of type void
    """
    ir_types = ir_type_to_ir_types(typ)
    values = [Undefined(ir_type=ir_type, source_location=loc) for ir_type in ir_types]
    match values:
        case []:
            raise InternalError("unexpected void type", loc)
        case [value]:
            return value
        case _:
            return ValueTuple(values=values, source_location=loc)


def invoke_puya_lib_subroutine(
    context: IRRegisterContext,
    *,
    full_name: PuyaLibIR,
    args: Sequence[Value | int | bytes],
    source_location: SourceLocation | None,
) -> InvokeSubroutine:
    sub = context.resolve_embedded_func(full_name)
    return InvokeSubroutine(
        target=sub,
        args=[convert_constants(arg, source_location) for arg in args],
        source_location=source_location,
    )
