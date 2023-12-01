import enum

from wyvern.awst import (
    nodes as awst_nodes,
    wtypes,
)
from wyvern.awst.nodes import BytesEncoding
from wyvern.errors import InternalError
from wyvern.ir.avm_ops_models import StackType
from wyvern.parse import SourceLocation


@enum.unique
class AVMType(enum.Flag):
    bytes = enum.auto()  # noqa: A003
    uint64 = enum.auto()
    any = bytes | uint64  # noqa: A003


@enum.unique
class AVMBytesEncoding(enum.Enum):
    base16 = enum.auto()
    base32 = enum.auto()
    base64 = enum.auto()
    utf8 = enum.auto()


def bytes_enc_to_avm_bytes_enc(bytes_encoding: BytesEncoding) -> AVMBytesEncoding:
    match bytes_encoding:
        case BytesEncoding.base16:
            return AVMBytesEncoding.base16
        case BytesEncoding.base32:
            return AVMBytesEncoding.base32
        case BytesEncoding.base64:
            return AVMBytesEncoding.base64
        case BytesEncoding.utf8:
            return AVMBytesEncoding.utf8
        case _:
            raise InternalError("Unsupported bytes encoding")


def wtype_to_avm_type(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    source_location: SourceLocation | None = None,
) -> AVMType:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        return wtype_to_avm_type(
            expr_or_wtype.wtype, source_location=source_location or expr_or_wtype.source_location
        )
    else:
        wtype = expr_or_wtype
    # TODO: compound types 🤔🤔🤔🤔🤔🤔🤔🤔🤔🤔🤔
    match wtype:
        case wtypes.uint64_wtype | wtypes.bool_wtype | wtypes.asset_wtype:
            return AVMType.uint64
        case (
            wtypes.bytes_wtype
            | wtypes.biguint_wtype
            | wtypes.address_wtype
            | wtypes.abi_string_wtype
        ):
            return AVMType.bytes
        case wtypes.AbiUIntN():
            return AVMType.bytes
        case wtypes.AbiDynamicArray():
            return AVMType.bytes
        case wtypes.AbiStaticArray():
            return AVMType.bytes
        case wtypes.void_wtype:
            raise InternalError("Can't translate void WType to AVMType", source_location)
        case _:
            raise InternalError(
                f"UH OH SPAGHETTI-O's, darn tooting compound type(?!) encountered: {wtype}",
                source_location,
            )


def stack_type_to_avm_type(stack_type: StackType) -> AVMType:
    match stack_type:
        case StackType.uint64 | StackType.bool:
            return AVMType.uint64
        case (
            StackType.bytes
            | StackType.bytes_32
            | StackType.bigint
            | StackType.box_name
            | StackType.address
        ):
            return AVMType.bytes
        case StackType.any | StackType.address_or_index:
            return AVMType.any
