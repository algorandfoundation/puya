from puya.errors import InternalError
from puya.ir import (
    encodings,
    models as ir,
    types_ as types,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import iteration
from puya.ir.builder._utils import assign
from puya.ir.context import IRFunctionBuildContext
from puya.ir.op_utils import OpFactory
from puya.parse import SourceLocation


def validate_encoding(
    context: IRFunctionBuildContext,
    value: ir.Value,
    ir_type: types.EncodedType,
    error_message: str,
    loc: SourceLocation,
) -> None:
    factory = OpFactory(context, loc)
    expected_size = _get_expected_size(context, value, ir_type, loc)
    value_len = factory.len(value)
    size_is_correct = factory.eq(value_len, expected_size)
    factory.assert_value(size_is_correct, error_message=error_message)


def _get_expected_size(
    context: IRFunctionBuildContext,
    value: ir.Value,
    ir_type: types.EncodedType,
    loc: SourceLocation,
) -> ir.Value:
    factory = OpFactory(context, loc)
    encoding = ir_type.encoding
    match encoding:
        case _ if encoding.is_fixed:
            return factory.constant(encoding.checked_num_bytes)
        case encodings.ArrayEncoding() as arr if arr.element.is_fixed:
            length = factory.materialise_single(
                ir.ArrayLength(
                    base=value,
                    base_type=ir_type,
                    array_encoding=encoding,
                    source_location=loc,
                ),
                "length",
            )
            if arr.element.is_bit:
                num_bits = factory.mul(length, arr.element.checked_num_bits)
                num_bytes_value: ir.Value = factory.add(num_bits, 7)
                num_bytes_value = factory.div_floor(num_bytes_value, 8)
            else:
                num_bytes_value = factory.mul(length, arr.element.checked_num_bytes)
            if arr.length_header:
                num_bytes_value = factory.add(num_bytes_value, 2)
            return num_bytes_value
        case encodings.ArrayEncoding(element=element) as arr if element.is_dynamic:
            length = factory.materialise_single(
                ir.ArrayLength(
                    base=value,
                    base_type=ir_type,
                    array_encoding=encoding,
                    source_location=loc,
                ),
                "length",
            )
            num_bytes_reg = factory.mul(length, 2, "num_bytes")
            if not arr.length_header:
                array_data = value
            else:
                array_data = factory.extract_to_end(value, 2, "array_data")
            el_ir_type = types.EncodedType(arr.element)
            with iteration.iterate_and_yield_range(context, length, loc) as index:
                num_bytes_reg = _refresh_mutated_value(context, num_bytes_reg)
                head_offset_bytes = factory.mul(index, 2, "head_offset_bytes")
                item_offset = factory.extract_uint16(
                    array_data,
                    head_offset_bytes,
                    "item_offset",
                    error_message="invalid array encoding",
                )
                offset_is_correct = factory.eq(
                    item_offset,
                    num_bytes_reg,
                    "offset_is_correct",
                )
                factory.assert_value(
                    offset_is_correct, error_message=f"invalid tail pointer for {arr}"
                )
                item = factory.extract_to_end(value=array_data, start=item_offset)
                element_num_bytes = _get_expected_size(context, item, el_ir_type, loc)
                # while in a loop need to ensure we update the following variables and don't
                # create new temporaries
                _increment_and_reassign(context, num_bytes_reg, element_num_bytes, loc)
            num_bytes_reg = _refresh_mutated_value(context, num_bytes_reg)
            if encoding.length_header:
                num_bytes_reg = factory.add(num_bytes_reg, 2, "num_bytes")
            return num_bytes_reg
        case encodings.TupleEncoding(is_dynamic=True):
            num_bytes_value = factory.constant(encoding.get_head_bit_offset(None) // 8)
            value_len = factory.len(value, "tuple_len")
            for idx, el in enumerate(encoding.elements):
                if el.is_dynamic:
                    offset_index = encoding.get_head_bit_offset(idx) // 8
                    offset = factory.extract_uint16(
                        value, offset_index, error_message="invalid tuple encoding"
                    )
                    offset_is_correct = factory.eq(offset, num_bytes_value)
                    factory.assert_value(
                        offset_is_correct,
                        error_message=f"invalid tail pointer at index {idx} of {encoding}",
                    )
                    el_ir_type = types.EncodedType(el)
                    item = factory.substring3(value=value, start=offset, end_ex=value_len)
                    element_num_bytes = _get_expected_size(context, item, el_ir_type, loc)
                    num_bytes_value = factory.add(num_bytes_value, element_num_bytes)
            return num_bytes_value
        case _:
            raise InternalError(f"unexpected encoding: {encoding}", loc)


def _refresh_mutated_value(context: IRFunctionBuildContext, value: ir.Register) -> ir.Register:
    return context.ssa.read_variable(value.name, value.ir_type, context.block_builder.active_block)


def _increment_and_reassign(
    context: IRFunctionBuildContext, lhs: ir.Register, value: ir.Value, loc: SourceLocation
) -> ir.Register:
    """increments the variable associated with lhs by value"""
    intrinsic = ir.Intrinsic(
        op=AVMOp.add,
        args=[_refresh_mutated_value(context, lhs), value],
        source_location=loc,
    )
    return assign(
        context,
        source=intrinsic,
        name=lhs.name,
        ir_type=lhs.ir_type,
        register_location=lhs.source_location,
        assignment_location=loc,
    )
