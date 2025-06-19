from puya.ir import models as ir
from puya.ir.builder._utils import assign_temp
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import IRType
from puya.parse import SourceLocation


def new_slot(context: IRRegisterContext, slot_type: IRType, loc: SourceLocation) -> ir.Register:
    return assign_temp(
        context,
        ir.NewSlot(
            source_location=loc,
            ir_type=slot_type,
        ),
        temp_description="slot",
        source_location=loc,
    )


def write_slot(
    context: IRRegisterContext, slot: ir.Value, value: ir.Value, loc: SourceLocation | None
) -> None:
    context.add_op(
        ir.WriteSlot(
            slot=slot,
            value=value,
            source_location=loc,
        )
    )


def read_slot(context: IRRegisterContext, slot: ir.Value, loc: SourceLocation | None) -> ir.Value:
    return assign_temp(
        context,
        ir.ReadSlot(slot=slot, source_location=loc),
        temp_description="slot_contents",
        source_location=loc,
    )
