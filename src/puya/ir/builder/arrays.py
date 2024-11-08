from collections.abc import Sequence

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.errors import CodeError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory
from puya.ir.context import IRFunctionBuildContext
from puya.ir.types_ import IRType
from puya.parse import SourceLocation


def check_supported_array(wtype: wtypes.WType, loc: SourceLocation) -> wtypes.WType:
    if not isinstance(wtype, wtypes.WArray) or wtype.element_type != wtypes.uint64_wtype:
        raise CodeError("only uint64 arrays supported", loc)
    return wtype.element_type


def array_length(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    loc: SourceLocation,
) -> ir.Register:
    element_wtype = check_supported_array(array.wtype, loc)
    factory = OpFactory(context, loc)
    slot = context.visitor.visit_and_materialise_single(array)
    contents = factory.assign(
        ir.ReadSlot(slot=slot, source_location=loc, type=IRType.bytes),
        "array_contents",
    )
    contents_length = factory.len(contents, "contents_length")
    return factory.div_floor(contents_length, _get_element_size(element_wtype), "array_length")


def read_array_index(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    index_awst: awst.Expression,
    loc: SourceLocation,
) -> ir.Register:
    element_wtype = check_supported_array(array.wtype, loc)
    factory = OpFactory(context, loc)
    slot = context.visitor.visit_and_materialise_single(array)
    index = context.visitor.visit_and_materialise_single(index_awst)
    contents = factory.assign(
        ir.ReadSlot(slot=slot, type=IRType.bytes, source_location=loc),
        "array_contents",
    )
    contents_index = factory.mul(index, _get_element_size(element_wtype), "contents_index")
    return factory.extract_uint64(contents, contents_index, "value")


def assign_array_index(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    index_awst: awst.Expression,
    value_provider: ir.ValueProvider,
    loc: SourceLocation,
) -> Sequence[ir.Value]:
    element_wtype = check_supported_array(array.wtype, loc)
    factory = OpFactory(context, loc)
    slot = context.visitor.visit_and_materialise_single(array)
    index = context.visitor.visit_and_materialise_single(index_awst)
    contents = factory.assign(
        ir.ReadSlot(slot=slot, type=IRType.bytes, source_location=loc),
        "array_contents",
    )
    contents_index = factory.mul(index, _get_element_size(element_wtype), "contents_index")
    (value,) = context.visitor.materialise_value_provider(value_provider, "value")
    value_bytes = factory.itob(value, "value_bytes")
    contents = factory.replace(contents, contents_index, value_bytes, "updated_array_contents")
    context.block_builder.add(
        ir.WriteSlot(
            slot=slot,
            value=contents,
            source_location=loc,
        )
    )
    return (value,)


def extend_array(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    items_awst: awst.Expression,
    loc: SourceLocation,
) -> None:
    check_supported_array(array.wtype, loc)
    factory = OpFactory(context, loc)
    slot = context.visitor.visit_and_materialise_single(array)
    contents = factory.assign(
        ir.ReadSlot(slot=slot, source_location=loc, type=IRType.bytes),
        "array_contents",
    )
    items = context.visitor.visit_and_materialise(items_awst, temp_description="other")
    for item in items:
        item_bytes = factory.itob(item, "item_bytes")
        contents = factory.assign(
            factory.concat(
                contents, item_bytes, "concat", error_message="max array length exceeded"
            ),
            "array_contents",
        )
    context.block_builder.add(
        ir.WriteSlot(
            slot=slot,
            value=contents,
            source_location=loc,
        )
    )


def _get_element_size(wtype: wtypes.WType) -> int:
    assert wtype == wtypes.uint64_wtype, "TODO: other wtypes"
    return 8
