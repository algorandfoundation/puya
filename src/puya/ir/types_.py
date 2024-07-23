import enum
import typing
from collections.abc import Sequence

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


@enum.unique
class IRType(enum.StrEnum):
    bytes = enum.auto()
    uint64 = enum.auto()
    bool = enum.auto()
    biguint = enum.auto()
    itxn_group_idx = enum.auto()  # the group index of the result
    itxn_field_set = enum.auto()  # a collection of fields for a pending itxn submit

    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        maybe_result = self.maybe_avm_type
        if not isinstance(maybe_result, AVMType):
            raise InternalError(f"{maybe_result} cannot be mapped to AVM stack type")
        return maybe_result

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes] | str:
        match self:
            case IRType.uint64 | IRType.bool:
                return AVMType.uint64
            case IRType.bytes | IRType.biguint:
                return AVMType.bytes
            case IRType.itxn_group_idx | IRType.itxn_field_set:
                return self.name
            case _:
                typing.assert_never(self)


def bytes_enc_to_avm_bytes_enc(bytes_encoding: BytesEncoding) -> AVMBytesEncoding:
    try:
        return AVMBytesEncoding(bytes_encoding.value)
    except ValueError as ex:
        raise InternalError(f"Unhandled BytesEncoding: {bytes_encoding}") from ex


def wtype_to_ir_type(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    source_location: SourceLocation | None = None,
) -> IRType:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        return wtype_to_ir_type(
            expr_or_wtype.wtype, source_location=source_location or expr_or_wtype.source_location
        )
    else:
        wtype = expr_or_wtype
    match wtype:
        case wtypes.bool_wtype:
            return IRType.bool
        case wtypes.biguint_wtype:
            return IRType.biguint
        case wtypes.WInnerTransaction():
            return IRType.itxn_group_idx
        case wtypes.WInnerTransactionFields():
            return IRType.itxn_field_set
        case wtypes.void_wtype:
            raise InternalError("can't translate void wtype to irtype", source_location)
        # case wtypes.state_key:
        #     return IRType.state_key  # TODO
        # case wtypes.box_key:
        #     return IRType.box_key  # TODO
    match wtype.scalar_type:
        case AVMType.uint64:
            return IRType.uint64
        case AVMType.bytes:
            return IRType.bytes
        case None:
            raise CodeError(
                f"unsupported nested/compound wtype encountered: {wtype}", source_location
            )
        case _:
            typing.assert_never(wtype.scalar_type)


def get_wtype_arity(wtype: wtypes.WType) -> int:
    """Returns the number of values this wtype represents on the stack"""
    if isinstance(wtype, wtypes.WTuple):
        return sum_wtypes_arity(wtype.types)
    else:
        return 1


def sum_wtypes_arity(types: Sequence[wtypes.WType]) -> int:
    return sum(map(get_wtype_arity, types))


def wtype_to_ir_types(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    source_location: SourceLocation | None = None,
) -> list[IRType]:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        wtype = expr_or_wtype.wtype
    else:
        wtype = expr_or_wtype
    if wtype == wtypes.void_wtype:
        return []
    elif isinstance(wtype, wtypes.WTuple):
        return [
            ir_type
            for wtype in wtype.types
            for ir_type in wtype_to_ir_types(wtype, source_location)
        ]
    else:
        return [wtype_to_ir_type(wtype, source_location)]


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


def stack_type_to_ir_type(stack_type: StackType) -> IRType | None:
    match stack_type:
        case StackType.bool:
            return IRType.bool
        case StackType.bigint:
            return IRType.biguint
        case StackType.uint64 | StackType.asset | StackType.application:
            return IRType.uint64
        case StackType.bytes | StackType.box_name | StackType.address | StackType.state_key:
            return IRType.bytes
        case StackType.any | StackType.address_or_index:
            return None
        case _:
            typing.assert_never(stack_type)
