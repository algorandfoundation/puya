from decimal import Decimal
from pathlib import Path

import pytest

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.awst.nodes import BytesEncoding
from puya.ir import models as ir
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext
from puya.log import LogLevel, logging_context
from puya.options import PuyaOptions
from puya.parse import SourceLocation

_location = SourceLocation(
    file=Path("/test_ir.ts"),
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
        wtype=wtypes.ARC4UFixedNxM(n=8, m=2, source_location=None),
        source_location=_location,
    )
    assert _build_ir_and_return_errors(expr) == ["invalid arc4.ufixed8x2 value"]


def test_bytes_validation() -> None:
    expr = awst.BytesConstant(
        value=b"0" * 4097, encoding=BytesEncoding.base16, source_location=_location
    )
    assert _build_ir_and_return_errors(expr) == ["invalid bytes value"]


def test_string_validation() -> None:
    expr = awst.StringConstant(value="0" * 4097, source_location=_location)
    assert _build_ir_and_return_errors(expr) == ["invalid string value"]


def test_address_validation() -> None:
    expr = awst.AddressConstant(value="bad_address", source_location=_location)
    assert _build_ir_and_return_errors(expr) == ["invalid Algorand address"]


def _build_ir_and_return_errors(expr: awst.Expression) -> list[str]:
    module_name = "test_ir"
    func_name = "test_ir"
    function = awst.Subroutine(
        id=f"{module_name}.{func_name}",
        name=func_name,
        body=awst.Block(body=[awst.ExpressionStatement(expr)], source_location=_location),
        source_location=_location,
        args=(),
        return_type=wtypes.void_wtype,
        documentation=awst.MethodDocumentation(),
    )
    ctx = IRBuildContext(
        options=PuyaOptions(),
        compilation_set={},
        sources_by_path={},
        awst=[],
        subroutines={},
    )
    subroutine = ir.Subroutine(
        source_location=_location,
        full_name=function.id,
        short_name=function.short_name,
        parameters=(),
        returns=(),
        body=[],
    )
    with logging_context() as log_ctx:
        FunctionIRBuilder.build_body(ctx, function, subroutine)
    return [log.message for log in log_ctx.logs if log.level == LogLevel.error]
