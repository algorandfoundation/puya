import enum
import typing

from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import BytesEncoding
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops_models import StackType
from puya.parse import SourceLocation


@enum.unique
class AVMBytesEncoding(enum.StrEnum):
    unknown = enum.auto()
    base16 = enum.auto()
    base32 = enum.auto()
    base64 = enum.auto()
    utf8 = enum.auto()


def bytes_enc_to_avm_bytes_enc(bytes_encoding: BytesEncoding) -> AVMBytesEncoding:
    try:
        return AVMBytesEncoding(bytes_encoding.value)
    except ValueError as ex:
        raise InternalError(f"Unhandled BytesEncoding: {bytes_encoding}") from ex


def wtype_to_avm_type(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    source_location: SourceLocation | None = None,
) -> typing.Literal[AVMType.bytes, AVMType.uint64]:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        return wtype_to_avm_type(
            expr_or_wtype.wtype, source_location=source_location or expr_or_wtype.source_location
        )
    else:
        wtype = expr_or_wtype
    match wtype:
        case (
            wtypes.uint64_wtype
            | wtypes.bool_wtype
            | wtypes.asset_wtype
            | wtypes.application_wtype
            | wtypes.WGroupTransaction()
        ):
            return AVMType.uint64
        case (
            wtypes.bytes_wtype
            | wtypes.biguint_wtype
            | wtypes.account_wtype
            | wtypes.ARC4Type()
            | wtypes.string_wtype
        ):
            return AVMType.bytes
        case wtypes.void_wtype:
            raise InternalError("Can't translate void WType to AVMType", source_location)
        case _:
            raise CodeError(
                f"Unsupported nested/compound type encountered: {wtype}",
                source_location,
            )


def wtype_to_avm_types(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    source_location: SourceLocation | None = None,
) -> list[AVMType]:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        wtype = expr_or_wtype.wtype
    else:
        wtype = expr_or_wtype
    if wtype == wtypes.void_wtype:
        return []
    elif isinstance(wtype, wtypes.WTuple):
        return [wtype_to_avm_type(t, source_location) for t in wtype.types]
    else:
        return [wtype_to_avm_type(wtype, source_location)]


def stack_type_to_avm_type(stack_type: StackType) -> AVMType:
    match stack_type:
        case StackType.uint64 | StackType.bool | StackType.asset | StackType.application:
            return AVMType.uint64
        case (
            StackType.bytes
            | StackType.bigint
            | StackType.box_name
            | StackType.address
            | StackType.state_key
        ):
            return AVMType.bytes
        case StackType.any | StackType.address_or_index:
            return AVMType.any
