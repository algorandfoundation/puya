import typing

from puya import log
from puya.ir.encodings import (
    BoolEncoding,
    Encoding,
)
from puya.ir.types_ import (
    EncodedType,
    IRType,
    PrimitiveIRType,
    TupleIRType,
)

logger = log.get_logger(__name__)

# packed bits are packed starting with the left most bit
ARC4_TRUE = (1 << 7).to_bytes(1, "big")
ARC4_FALSE = (0).to_bytes(1, "big")


def requires_conversion(
    typ: IRType | TupleIRType, encoding: Encoding, action: typing.Literal["encode", "decode"]
) -> bool:
    if typ == PrimitiveIRType.bool and isinstance(encoding, BoolEncoding):
        return True
    elif isinstance(typ, EncodedType):
        typ_is_bool8 = isinstance(typ.encoding, BoolEncoding) and not typ.encoding.packed
        encoding_is_bool1 = encoding.is_bit
        if typ_is_bool8 and encoding_is_bool1 and action == "encode":
            return False
        # are encodings different?
        return typ.encoding != encoding
    # otherwise requires conversion
    else:
        return True
