from collections.abc import Sequence

import attrs

from puya.awst import wtypes

# used to map puyapy/_gen.pyi stubs to awst
# referenced by both scripts/generate_stubs.py and src/puya/awst_build/eb/intrinsics.py


@attrs.define
class ArgMapping:
    arg_name: str
    """Name of puyapy argument to obtain value from"""
    allowed_types: Sequence[wtypes.WType | type] = attrs.field(factory=tuple)
    """Valid types for this argument"""

    @allowed_types.validator
    def check(self, _attribute: object, value: Sequence[wtypes.WType | type]) -> None:
        if wtypes.biguint_wtype in value and wtypes.uint64_wtype in value:
            raise ValueError("overlap in integral types")

    def is_allowed_constant(self, constant: object) -> bool:
        if type(constant) in self.allowed_types:
            return True
        for allowed_type in self.allowed_types:
            if isinstance(allowed_type, wtypes.WType) and allowed_type.is_valid_literal(constant):
                return True
        return False


@attrs.define
class FunctionOpMapping:
    op_code: str
    """TEAL op code for this mapping"""
    immediates: Sequence[str | ArgMapping] = attrs.field(factory=tuple)
    """A list of constant values or references to an puyapy argument to include in immediate"""
    stack_inputs: Sequence[ArgMapping] = attrs.field(factory=tuple)
    """References to an puyapy argument"""
    stack_outputs: Sequence[wtypes.WType] = attrs.field(factory=tuple)
    """Types output by TEAL op"""
