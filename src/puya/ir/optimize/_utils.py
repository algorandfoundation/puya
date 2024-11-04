import base64
from collections.abc import Mapping

from puya import algo_constants
from puya.errors import InternalError
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.types_ import AVMBytesEncoding
from puya.utils import biguint_bytes_eval, method_selector_hash


def get_definition(
    subroutine: models.Subroutine, register: models.Register, *, should_exist: bool = True
) -> models.Assignment | models.Phi | None:
    if register in subroutine.parameters:
        return None
    for block in subroutine.body:
        for phi in block.phis:
            if phi.register == register:
                return phi
        for op in block.ops:
            if isinstance(op, models.Assignment) and register in op.targets:
                return op
    if should_exist:
        raise InternalError(f"Register is not defined: {register}", subroutine.source_location)
    return None


def _decode_address(address: str) -> bytes:
    # Pad address so it's a valid b32 string
    padded_address = address + (6 * "=")
    address_bytes = base64.b32decode(padded_address)
    public_key_hash = address_bytes[: algo_constants.PUBLIC_KEY_HASH_LENGTH]
    return public_key_hash


def get_byte_constant(
    register_assignments: Mapping[models.Register, models.Assignment], byte_arg: models.Value
) -> models.BytesConstant | None:
    if byte_arg in register_assignments:
        byte_arg_defn = register_assignments[byte_arg]  # type: ignore[index]
        match byte_arg_defn.source:
            case models.Intrinsic(op=AVMOp.itob, args=[models.UInt64Constant(value=itob_arg)]):
                return models.BytesConstant(
                    source_location=byte_arg_defn.source_location,
                    value=itob_arg.to_bytes(8, byteorder="big", signed=False),
                    encoding=AVMBytesEncoding.base16,
                )
            case models.Intrinsic(
                op=AVMOp.bzero, args=[models.UInt64Constant(value=bzero_arg)]
            ) if bzero_arg <= 64:
                return models.BytesConstant(
                    source_location=byte_arg_defn.source_location,
                    value=b"\x00" * bzero_arg,
                    encoding=AVMBytesEncoding.base16,
                )
            case models.Intrinsic(op=AVMOp.global_, immediates=["ZeroAddress"]):
                return models.BytesConstant(
                    value=_decode_address(algo_constants.ZERO_ADDRESS),
                    encoding=AVMBytesEncoding.base32,
                    source_location=byte_arg.source_location,
                )
    elif isinstance(byte_arg, models.Constant):
        if isinstance(byte_arg, models.BytesConstant):
            return byte_arg
        if isinstance(byte_arg, models.BigUIntConstant):
            return models.BytesConstant(
                value=biguint_bytes_eval(byte_arg.value),
                encoding=AVMBytesEncoding.base16,
                source_location=byte_arg.source_location,
            )
        if isinstance(byte_arg, models.AddressConstant):
            return models.BytesConstant(
                value=_decode_address(byte_arg.value),
                encoding=AVMBytesEncoding.base32,
                source_location=byte_arg.source_location,
            )
        if isinstance(byte_arg, models.MethodConstant):
            return models.BytesConstant(
                value=method_selector_hash(byte_arg.value),
                encoding=AVMBytesEncoding.base16,
                source_location=byte_arg.source_location,
            )
    return None
