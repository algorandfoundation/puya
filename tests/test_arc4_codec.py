# test cases for supported scenarios that can't currently be expressed in algorand python
import pytest

from puya.awst import nodes, wtypes
from puya.context import CompileContext
from puya.errors import log_exceptions
from puya.ir.arc4_types import get_arc4_name
from puya.ir.main import awst_to_ir
from puya.log import LogLevel, logging_context
from puya.options import PuyaOptions
from puya.parse import SourceLocation


def _arc4_name_or_str(wtype: wtypes.WType) -> str:
    if isinstance(wtype, wtypes.ARC4Type):
        return get_arc4_name(wtype, use_alias=True)
    else:
        return str(wtype)


uint8 = wtypes.ARC4UIntN(n=8)


@pytest.mark.parametrize(
    ("arc4_type", "target_type"),
    [
        (wtypes.arc4_address_alias, wtypes.account_wtype),
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
    ids=_arc4_name_or_str,
)
def test_supported_decodes(arc4_type: wtypes.ARC4Type, target_type: wtypes.WType) -> None:
    func = _build_decode_function(arc4_type, target_type)
    errors = _get_ir_build_errors(func)
    assert not errors, "expected no errors"


@pytest.mark.parametrize(
    ("arc4_type", "target_type"),
    [
        (wtypes.arc4_address_alias, wtypes.uint64_wtype),
        (wtypes.arc4_string_alias, wtypes.bytes_wtype),
        (
            wtypes.arc4_address_alias,
            wtypes.WTuple(types=(wtypes.uint64_wtype,) * 3),
        ),
    ],
    ids=_arc4_name_or_str,
)
def test_unsupported_decodes(arc4_type: wtypes.ARC4Type, target_type: wtypes.WType) -> None:
    func = _build_decode_function(arc4_type, target_type)
    errors = _get_ir_build_errors(func)
    assert errors == [
        f"unsupported ARC-4 decode operation from type {_arc4_name_or_str(arc4_type)}"
    ]


def _get_ir_build_errors(func: nodes.Subroutine) -> list[str]:
    with logging_context() as log_ctx, log_exceptions():
        ctx = CompileContext(
            options=PuyaOptions(),
            compilation_set={},
            sources_by_path={},
        )
        # force iteration
        results = list(awst_to_ir(ctx, [func]))
        assert results is not None
    errors = [log.message for log in log_ctx.logs if log.level == LogLevel.error]
    return errors


def _build_decode_function(
    from_wtype: wtypes.ARC4Type, decode_to: wtypes.WType
) -> nodes.Subroutine:
    loc = SourceLocation(file=None, line=1)
    return nodes.Subroutine(
        id="decode",
        name="decode",
        args=[nodes.SubroutineArgument(name="value", wtype=from_wtype, source_location=loc)],
        body=nodes.Block(
            body=[
                nodes.ReturnStatement(
                    value=nodes.ARC4Decode(
                        value=nodes.VarExpression(
                            name="value", wtype=from_wtype, source_location=loc
                        ),
                        wtype=decode_to,
                        source_location=loc,
                    ),
                    source_location=loc,
                )
            ],
            source_location=loc,
        ),
        return_type=decode_to,
        source_location=loc,
        documentation=nodes.MethodDocumentation(),
    )
