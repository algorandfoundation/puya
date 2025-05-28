# test cases for supported scenarios that can't currently be expressed in algorand python
import typing
from collections.abc import Sequence

import pytest

from puya.awst import wtypes
from puya.errors import log_exceptions
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.encodings import wtype_to_encoding
from puya.ir.models import BytesConstant, Op, Register, Subroutine, Undefined, Value, ValueProvider
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import AVMBytesEncoding, IRType, wtype_to_ir_type
from puya.log import LogLevel, logging_context
from puya.parse import SourceLocation


def _encoding_name(wtype: wtypes.WType) -> str:
    return wtype_to_encoding(wtype, None).name


def _ir_name(wtype: wtypes.WType) -> str:
    return wtype_to_ir_type(wtype, SourceLocation(file=None, line=1), allow_tuple=True).name


uint8 = wtypes.ARC4UIntN(n=8)


@pytest.mark.parametrize(
    ("arc4_type", "target_type"),
    [
        (wtypes.arc4_address_alias, wtypes.account_wtype),
        (wtypes.arc4_address_alias, wtypes.bytes_wtype),
        (wtypes.arc4_string_alias, wtypes.string_wtype),
        (wtypes.ARC4UIntN(n=8), wtypes.bool_wtype),
        (
            wtypes.ARC4StaticArray(element_type=uint8, array_size=3),
            wtypes.WTuple(types=(uint8,) * 3),
        ),
        (
            wtypes.ARC4StaticArray(element_type=uint8, array_size=3),
            wtypes.bytes_wtype,
        ),
        (
            wtypes.ARC4StaticArray(element_type=wtypes.ARC4UIntN(n=64), array_size=3),
            wtypes.WTuple(types=(wtypes.uint64_wtype,) * 3),
        ),
    ],
    ids=_ir_name,
)
def test_supported_decodes(arc4_type: wtypes.ARC4Type, target_type: wtypes.WType) -> None:
    errors = _call_decode_value(arc4_type, target_type)

    assert not errors, "expected no errors"


@pytest.mark.parametrize(
    ("arc4_type", "target_type"),
    [
        (wtypes.arc4_address_alias, wtypes.uint64_wtype),
        (wtypes.arc4_string_alias, wtypes.bytes_wtype),
        (wtypes.ARC4DynamicArray(element_type=wtypes.arc4_byte_alias), wtypes.string_wtype),
        (
            wtypes.arc4_address_alias,
            wtypes.WTuple(types=(wtypes.uint64_wtype,) * 3),
        ),
    ],
    ids=_ir_name,
)
def test_unsupported_decodes(arc4_type: wtypes.ARC4Type, target_type: wtypes.WType) -> None:
    errors = _call_decode_value(arc4_type, target_type)

    assert errors == [f"cannot decode from {_encoding_name(arc4_type)} to {_ir_name(target_type)}"]


def _call_decode_value(arc4_type: wtypes.ARC4Type, target_type: wtypes.WType) -> list[str]:
    from puya.ir.builder.aggregates.arc4_codecs import decode_value

    loc = SourceLocation(file=None, line=1)
    encoding = wtype_to_encoding(arc4_type, loc)
    target_ir_type = wtype_to_ir_type(target_type, loc, allow_tuple=True)
    value = BytesConstant(value=b"", encoding=AVMBytesEncoding.base16, source_location=loc)
    with logging_context() as log_ctx, log_exceptions():
        ctx = _MockRegisterContext()
        decode_value(ctx, value=value, encoding=encoding, target_type=target_ir_type, loc=loc)
    errors = [log.message for log in log_ctx.logs if log.level == LogLevel.error]
    return errors


class _MockRegisterContext(IRRegisterContext):
    @typing.override
    def next_tmp_name(self, description: str) -> str:
        return "tmp"

    def new_register(
        self, name: str, ir_type: IRType, location: SourceLocation | None
    ) -> Register:
        return Register(name=name, version=0, ir_type=ir_type, source_location=location)

    def add_assignment(
        self, targets: list[Register], source: ValueProvider, loc: SourceLocation | None
    ) -> None:
        pass

    def add_op(self, op: Op) -> None:
        pass

    def resolve_embedded_func(self, full_name: PuyaLibIR) -> Subroutine:
        raise NotImplementedError

    @typing.override
    def materialise_value_provider(
        self, provider: ValueProvider, description: str | Sequence[str]
    ) -> list[Value]:
        return [
            Undefined(
                ir_type=ir_type,
                source_location=None,
            )
            for ir_type in provider.types
        ]
