# ruff: noqa: E501
# fmt: off

import enum

from puya.ir.models import SubroutineID


@enum.unique
class PuyaLibIR(SubroutineID, enum.Enum):
    ensure_budget = SubroutineID("_puya_lib.util.ensure_budget")
    is_substring = SubroutineID("_puya_lib.bytes_.is_substring")
    dynamic_array_pop_bit = SubroutineID("_puya_lib.arc4.dynamic_array_pop_bit")
    dynamic_array_pop_fixed_size = SubroutineID("_puya_lib.arc4.dynamic_array_pop_fixed_size")
    dynamic_array_pop_byte_length_head = SubroutineID("_puya_lib.arc4.dynamic_array_pop_byte_length_head")
    dynamic_array_pop_dynamic_element = SubroutineID("_puya_lib.arc4.dynamic_array_pop_dynamic_element")
    dynamic_array_concat_bits = SubroutineID("_puya_lib.arc4.dynamic_array_concat_bits")
    dynamic_array_concat_byte_length_head = SubroutineID("_puya_lib.arc4.dynamic_array_concat_byte_length_head")
    dynamic_array_concat_dynamic_element = SubroutineID("_puya_lib.arc4.dynamic_array_concat_dynamic_element")
    dynamic_array_replace_byte_length_head = SubroutineID("_puya_lib.arc4.dynamic_array_replace_byte_length_head")
    dynamic_array_replace_dynamic_element = SubroutineID("_puya_lib.arc4.dynamic_array_replace_dynamic_element")
    static_array_replace_dynamic_element = SubroutineID("_puya_lib.arc4.static_array_replace_dynamic_element")
    static_array_replace_byte_length_head = SubroutineID("_puya_lib.arc4.static_array_replace_byte_length_head")
    recalculate_head_for_elements_with_byte_length_head = SubroutineID("_puya_lib.arc4.recalculate_head_for_elements_with_byte_length_head")
