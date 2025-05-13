import typing

import pytest

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.errors import InternalError
from puya.ir.arc4_types import wtype_to_arc4_wtype
from puya.parse import SourceLocation

loc = SourceLocation(file=None, line=1)


def byte_c(val: bytes | None = None, length: int | None = None) -> awst.BytesConstant:
    """
    Return a BytesConstant with the given value and/or len

    If no val, create bzero value of specified len, or empty bytes if no length
    If no length, wtype is unbounded bytes
    """
    return awst.BytesConstant(
        value=val or (b"\0" * length if length is not None else b""),
        source_location=loc,
        wtype=wtypes.BytesWType(length=length),
        encoding=awst.BytesEncoding.unknown,
    )


def test_arc4_equiv_bytes_no_length_is_dynamic_bytes() -> None:
    arc4_type = wtype_to_arc4_wtype(wtypes.bytes_wtype, loc=None)

    assert isinstance(arc4_type, wtypes.ARC4DynamicArray)
    assert arc4_type.element_type == wtypes.arc4_byte_alias


def test_arc4_equiv_bytes_with_length_is_static_bytes() -> None:
    arc4_type = wtype_to_arc4_wtype(wtypes.BytesWType(length=10), loc=None)

    assert isinstance(arc4_type, wtypes.ARC4StaticArray)
    assert arc4_type.array_size == 10
    assert arc4_type.element_type == wtypes.arc4_byte_alias


def test_awst_bytes_constant_validation() -> None:
    # value matches length
    byte_c(val=b"123", length=3)
    # no declared length
    byte_c(val=b"123", length=None)
    # value does not match length
    with pytest.raises(InternalError, match="invalid size for type of bytes constant"):
        byte_c(val=b"123", length=4)


def test_awst_bytes_comparison_validation() -> None:
    awst.BytesComparisonExpression(
        source_location=loc, operator=awst.EqualityComparison.eq, lhs=byte_c(), rhs=byte_c()
    )
    awst.BytesComparisonExpression(
        source_location=loc,
        operator=awst.EqualityComparison.eq,
        lhs=byte_c(length=3),
        rhs=byte_c(length=3),
    )
    awst.BytesComparisonExpression(
        source_location=loc,
        operator=awst.EqualityComparison.eq,
        lhs=byte_c(),
        rhs=byte_c(length=3),
    )
    awst.BytesComparisonExpression(
        source_location=loc,
        operator=awst.EqualityComparison.eq,
        lhs=byte_c(length=4),
        rhs=byte_c(length=3),
    )


bytes_binary_data = [
    (byte_c(), byte_c(), awst.BytesBinaryOperator.add, wtypes.bytes_wtype, None, None),
    (
        byte_c(length=2),
        byte_c(length=2),
        awst.BytesBinaryOperator.add,
        wtypes.bytes_wtype,
        None,
        None,
    ),
    (
        byte_c(length=2),
        byte_c(length=2),
        awst.BytesBinaryOperator.add,
        wtypes.BytesWType(length=4),
        None,
        None,
    ),
    (
        byte_c(length=2),
        byte_c(length=2),
        awst.BytesBinaryOperator.add,
        wtypes.BytesWType(length=5),
        InternalError,
        "wrong length for sized bytes result, expected 4",
    ),
    (
        byte_c(length=2),
        byte_c(length=2),
        awst.BytesBinaryOperator.bit_and,
        wtypes.BytesWType(length=2),
        None,
        None,
    ),
    (
        byte_c(length=2),
        byte_c(length=3),
        awst.BytesBinaryOperator.bit_and,
        wtypes.BytesWType(length=3),
        None,
        None,
    ),
    (
        byte_c(length=2),
        byte_c(length=3),
        awst.BytesBinaryOperator.bit_and,
        wtypes.BytesWType(length=4),
        InternalError,
        "wrong length for sized bytes result, expected 3, got 4",
    ),
    (
        byte_c(),
        byte_c(length=3),
        awst.BytesBinaryOperator.bit_and,
        wtypes.BytesWType(length=3),
        InternalError,
        "sized bytes result type is invalid when either operand is unsized",
    ),
]


@pytest.mark.parametrize(("lhs", "rhs", "op", "wtype", "err", "err_match"), bytes_binary_data)
def test_awst_bytes_binary_validation(
    lhs: awst.Expression,
    rhs: awst.Expression,
    op: awst.BytesBinaryOperator,
    wtype: wtypes.WType,
    err: type[Exception] | None,
    err_match: str | typing.Pattern[str] | None,
) -> None:
    if err or err_match:
        with pytest.raises(err or Exception, match=err_match):
            awst.BytesBinaryOperation(source_location=loc, op=op, left=lhs, right=rhs, wtype=wtype)
    else:
        awst.BytesBinaryOperation(source_location=loc, op=op, left=lhs, right=rhs, wtype=wtype)
