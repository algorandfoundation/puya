from decimal import Decimal

import pytest
from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.ir import models as ir
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext
from puya.log import LogLevel, logging_context
from puya.options import PuyaOptions
from puya.parse import ParseResult, SourceLocation

_location = SourceLocation(
    file="test_ir.ts",
    line=1,
)


@pytest.mark.parametrize("value", [-1, 2**64])
def test_uint64_validation(value: int) -> None:
    expr = awst.UInt64Constant(value=value, source_location=_location)
    assert _build_ir_and_return_errors(expr) == ["invalid uint64 value"]


@pytest.mark.parametrize("value", [-1, 2**512])
def test_biguint_validation(value: int) -> None:
    expr = awst.BigUIntConstant(value=value, source_location=_location)
    assert _build_ir_and_return_errors(expr) == ["invalid biguint value"]


@pytest.mark.parametrize("value", [-1, 2**8])
def test_arc4_uintn_validation(value: int) -> None:
    expr = awst.IntegerConstant(
        value=value, wtype=wtypes.arc4_byte_alias, source_location=_location
    )
    assert _build_ir_and_return_errors(expr) == ["invalid arc4.uint8 value"]


@pytest.mark.parametrize(
    "value",
    [
        Decimal("-1.00"),
        Decimal("2.56"),
        Decimal("0.111"),
        Decimal("inf"),
    ],
)
def test_decimal_validation(value: Decimal) -> None:
    expr = awst.DecimalConstant(
        value=value,
        wtype=wtypes.ARC4UFixedNxM(bits=8, precision=2, source_location=None),
        source_location=_location,
    )
    assert _build_ir_and_return_errors(expr) == ["invalid decimal value"]


def _build_ir_and_return_errors(expr: awst.Expression) -> list[str]:
    function = awst.Subroutine(
        name="test_ir",
        body=awst.Block(body=[awst.ExpressionStatement(expr)], source_location=_location),
        source_location=_location,
        module_name="test_ir",
        args=(),
        return_type=wtypes.void_wtype,
        docstring=None,
    )
    ctx = IRBuildContext(
        options=PuyaOptions(),
        # TODO: only parse_result.sources need to be on an IRBuildContext
        parse_result=ParseResult(
            sources=[],
            manager=None,  # type: ignore[arg-type]
            ordered_modules=[],
        ),
        module_awsts={},
        subroutines={},
        embedded_funcs=[],
    )
    subroutine = ir.Subroutine(
        source_location=_location,
        module_name="test_ir",
        class_name=None,
        method_name="test_ir",
        parameters=(),
        returns=(),
        body=[],
    )
    with logging_context() as log_ctx:
        FunctionIRBuilder.build_body(ctx, function, subroutine, on_create=None)
    return [log.message for log in log_ctx.logs if log.level == LogLevel.error]
