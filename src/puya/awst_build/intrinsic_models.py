from collections.abc import Sequence
from functools import cached_property

import attrs

from puya.awst import wtypes

# used to map algopy/_gen.pyi stubs to awst
# referenced by both scripts/generate_stubs.py and src/puya/awst_build/eb/intrinsics.py


@attrs.frozen
class StackArgMapping:
    arg_name: str
    """Name of algopy argument to obtain value from"""
    allowed_types: Sequence[wtypes.WType] = attrs.field()
    """Valid types for this argument, in descending priority for literal conversions"""

    @allowed_types.validator
    def check(self, _attribute: object, value: Sequence[wtypes.WType]) -> None:
        if wtypes.biguint_wtype in value and wtypes.uint64_wtype in value:
            raise ValueError("overlap in integral types")


@attrs.frozen
class ImmediateArgMapping:
    arg_name: str
    """Name of algopy argument to obtain value from"""
    literal_type: type[str | int]
    """Literal type for the argument"""


@attrs.frozen
class FunctionOpMapping:
    op_code: str
    """TEAL op code for this mapping"""
    immediates: Sequence[str | ImmediateArgMapping] = attrs.field(factory=tuple)
    """A list of constant values or references to an algopy argument to include in immediate"""
    stack_inputs: Sequence[StackArgMapping] = attrs.field(factory=tuple)
    """References to an algopy argument"""
    stack_outputs: Sequence[wtypes.WType] = attrs.field(factory=tuple)
    """Types output by TEAL op"""
    is_property: bool = False
    """Is this function represented as a property"""

    @cached_property
    def literal_arg_names(self) -> set[str]:
        return {im.arg_name for im in self.immediates if not isinstance(im, str)}
