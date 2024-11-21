"""
Used to map algopy/_gen.pyi stubs to AWST.
Referenced by both scripts/generate_stubs.py and src/puya/awst_build/eb/intrinsics.py
"""

from collections.abc import Sequence, Set
from functools import cached_property

import attrs

from puya.awst import wtypes
from puya.errors import InternalError
from puyapy.awst_build import pytypes


@attrs.frozen
class PropertyOpMapping:
    op_code: str
    immediate: str
    typ: pytypes.PyType = attrs.field(
        validator=attrs.validators.not_(attrs.validators.in_([pytypes.NoneType]))
    )
    wtype: wtypes.WType = attrs.field(init=False)

    @wtype.default
    def _wtype(self) -> wtypes.WType:
        return self.typ.checked_wtype(location=None)


@attrs.frozen
class FunctionOpMapping:
    op_code: str
    immediates: Sequence[str | int | type[str | int]] = attrs.field(
        default=(), converter=tuple[str | int | type[str | int], ...]
    )
    """A list of immediate literals, or expected type"""
    args: Sequence[Sequence[pytypes.PyType] | int] = attrs.field(
        default=(), converter=tuple[Sequence[pytypes.PyType] | int, ...]
    )
    """A list of allowed argument types, or an index into the immediates sequence"""

    @cached_property
    def literal_arg_positions(self) -> Set[int]:
        return {idx for idx, arg in enumerate(self.args) if isinstance(arg, int)}

    def __attrs_post_init__(self) -> None:
        for idx, imm in enumerate(self.immediates):
            if isinstance(imm, type) and idx not in self.args:
                raise InternalError("expected immediate type to be reference by arg index")

        for idx, arg in enumerate(self.args):
            if isinstance(arg, int):
                try:
                    immediate = self.immediates[arg]
                except IndexError:
                    raise InternalError(
                        f"intrinsic {self.op_code!r} argument {idx}: immediates index out of range"
                    ) from None
                if immediate not in (str, int):
                    raise InternalError(
                        f"intrinsic {self.op_code!r} argument {idx}:"
                        " immediate index does not point to a type"
                    )
            else:
                if not arg:
                    raise InternalError(
                        f"intrinsic {self.op_code!r} argument {idx}: no stack input types provided"
                    )
                if (pytypes.BigUIntType.is_type_or_supertype(*arg)) and (
                    pytypes.UInt64Type.is_type_or_supertype(*arg)
                ):
                    raise InternalError(
                        f"intrinsic {self.op_code!r} argument {idx}: overlap in integer types"
                    )


@attrs.frozen(kw_only=True)
class OpMappingWithOverloads:
    arity: int = attrs.field(validator=attrs.validators.ge(0))
    result: pytypes.PyType = pytypes.NoneType
    """Types output by TEAL op"""
    result_wtype: wtypes.WType = attrs.field(init=False)
    overloads: Sequence[FunctionOpMapping] = attrs.field(
        validator=attrs.validators.min_len(1), converter=tuple[FunctionOpMapping, ...]
    )

    @result_wtype.default
    def _result_wtype(self) -> wtypes.WType:
        return self.result.checked_wtype(location=None)

    @arity.validator
    def _arity_matches(self, _attribute: object, arity: int) -> None:
        if any(len(o.args) != arity for o in self.overloads):
            raise InternalError("arity does not match all overloads")
