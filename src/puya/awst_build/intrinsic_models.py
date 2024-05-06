"""
Used to map algopy/_gen.pyi stubs to AWST.
Referenced by both scripts/generate_stubs.py and src/puya/awst_build/eb/intrinsics.py
"""

from collections.abc import Mapping, Sequence, Set
from functools import cached_property

import attrs

from puya.awst import wtypes
from puya.errors import InternalError


@attrs.frozen
class ImmediateArgMapping:
    arg_name: str
    """Name of algopy argument to obtain value from"""
    literal_type: type[str | int]
    """Literal type for the argument"""


@attrs.frozen
class PropertyOpMapping:
    op_code: str
    immediates: Sequence[str]
    stack_outputs: Sequence[wtypes.WType] = attrs.field(validator=attrs.validators.min_len(1))


@attrs.frozen
class FunctionOpMapping:
    op_code: str
    """TEAL op code for this mapping"""
    immediates: Mapping[str, type[str | int] | None] = attrs.field(default={})
    """A sequence of constant values or references to an algopy argument to include in immediate"""
    stack_inputs: Mapping[str, Sequence[wtypes.WType]] = attrs.field(default={})
    """Mapping of stack argument names to valid types for the argument,
     in descending priority for literal conversions"""
    stack_outputs: Sequence[wtypes.WType] = attrs.field(factory=tuple)
    """Types output by TEAL op"""
    is_property: bool = False
    """Is this function represented as a property"""

    @cached_property
    def literal_arg_names(self) -> Set[str]:
        result = set[str]()
        for name, maybe_lit_type in self.immediates.items():
            if maybe_lit_type is not None:
                if name in result:
                    raise InternalError(
                        f"Duplicated immediate input name: {name!r} for {self.op_code!r}"
                    )
                result.add(name)
        return result

    @stack_inputs.validator
    def _validate_stack_inputs(
        self, _attribute: object, value: Mapping[str, Sequence[wtypes.WType]]
    ) -> None:
        for name, types in value.items():
            if not types:
                raise InternalError(
                    f"No stack input types provided for argument {name!r} of {self.op_code!r}"
                )
            if wtypes.biguint_wtype in types and wtypes.uint64_wtype in types:
                raise InternalError(
                    f"Overlap in integral types for argument {name!r} or {self.op_code!r}"
                )

    def __attrs_post_init__(self) -> None:
        duplicates = self.literal_arg_names & self.stack_inputs.keys()
        if duplicates:
            raise InternalError(
                f"Duplicate arg names between stack inputs and immediates for {self.op_code!r}:"
                + ", ".join(duplicates)
            )
