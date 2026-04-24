"""
Used to map algopy/_gen.pyi stubs to AWST.
Referenced by both scripts/generate_stubs.py and src/puya/awst_build/eb/intrinsics.py
"""

from collections.abc import Sequence

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


def result_types_to_pytype(
    result: Sequence[pytypes.RuntimeType] | None,
) -> pytypes.PyType:
    if result is None:
        return pytypes.NeverType
    if not result:
        return pytypes.NoneType
    if len(result) == 1:
        return result[0]
    return pytypes.GenericTupleType.parameterise(result, source_location=None)


@attrs.frozen(kw_only=True)
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
    result: Sequence[pytypes.RuntimeType] | None = attrs.field(
        default=(),
        converter=attrs.converters.optional(tuple[pytypes.RuntimeType, ...]),
    )
    """Types output by TEAL op; None indicates the op never returns (halts)"""
    result_pytype: pytypes.PyType = attrs.field(init=False)
    result_wtype: wtypes.WType = attrs.field(init=False)

    @result_pytype.default
    def _result_pytype(self) -> pytypes.PyType:
        return result_types_to_pytype(self.result)

    @result_wtype.default
    def _result_wtype(self) -> wtypes.WType:
        return self.result_pytype.checked_wtype(location=None)

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
