from puya.awst import wtypes
from puya.awst.nodes import Expression, IntrinsicCall
from puya.errors import InternalError
from puya.parse import SourceLocation


def bytes_len(expr: Expression, loc: SourceLocation | None = None) -> IntrinsicCall:
    loc = loc or expr.source_location
    if expr.wtype != wtypes.bytes_wtype:
        raise InternalError("Expression for bytes_len must have wtype of bytes", loc)
    return IntrinsicCall(
        op_code="len",
        stack_args=[expr],
        wtype=wtypes.uint64_wtype,
        source_location=loc,
    )


def concat(
    a: Expression,
    b: Expression,
    loc: SourceLocation | None = None,
    result_type: wtypes.WType = wtypes.bytes_wtype,
) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="concat",
        stack_args=[a, b],
        wtype=result_type,
        source_location=loc or (a.source_location + b.source_location),
    )


def itob(expr: Expression, loc: SourceLocation | None = None) -> IntrinsicCall:
    return itob_as(expr, wtypes.bytes_wtype, loc)


def itob_as(
    expr: Expression, wtype: wtypes.WType, loc: SourceLocation | None = None
) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="itob",
        stack_args=[expr],
        wtype=wtype,
        source_location=loc or expr.source_location,
    )


def btoi(bytes_arg: Expression, location: SourceLocation | None = None) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="btoi",
        stack_args=[bytes_arg],
        wtype=wtypes.uint64_wtype,
        source_location=location or bytes_arg.source_location,
    )


def txn(immediate: str, wtype: wtypes.WType, location: SourceLocation) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="txn",
        immediates=[immediate],
        wtype=wtype,
        source_location=location,
    )


def txn_app_args(index: int, loc: SourceLocation) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="txna",
        immediates=["ApplicationArgs", index],
        source_location=loc,
        wtype=wtypes.bytes_wtype,
    )


def log(to_log: Expression, loc: SourceLocation) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="log",
        stack_args=[to_log],
        wtype=wtypes.void_wtype,
        source_location=loc,
    )


def select(
    *, condition: Expression, false: Expression, true: Expression, loc: SourceLocation
) -> IntrinsicCall:
    if false.wtype != true.wtype:
        raise InternalError(f"false WType ({false}) does not match true WType ({true})", loc)
    return IntrinsicCall(
        op_code="select",
        stack_args=[
            false,
            true,
            condition,
        ],
        wtype=false.wtype,
        source_location=loc,
    )


def extract(
    value: Expression,
    start: int,
    length: int = 0,
    loc: SourceLocation | None = None,
    result_type: wtypes.WType = wtypes.bytes_wtype,
) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="extract",
        immediates=[start, length],
        wtype=result_type,
        stack_args=[value],
        source_location=loc or value.source_location,
    )


def extract3(
    value: Expression,
    start: Expression,
    length: Expression,
    loc: SourceLocation | None = None,
    result_type: wtypes.WType = wtypes.bytes_wtype,
) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="extract3",
        wtype=result_type,
        stack_args=[value, start, length],
        source_location=loc or value.source_location,
    )


def zero_address(
    loc: SourceLocation, *, as_type: wtypes.WType = wtypes.account_wtype
) -> IntrinsicCall:
    return IntrinsicCall(
        wtype=as_type,
        op_code="global",
        immediates=["ZeroAddress"],
        source_location=loc,
    )
