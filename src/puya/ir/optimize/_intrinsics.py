"""Shared AVM-op metadata and pure helpers used across the IR optimisation passes."""

import typing
from collections.abc import Mapping

from puya import algo_constants
from puya.ir.avm_ops import AVMOp
from puya.ir.types_ import AVMBytesEncoding

PURE_AVM_OPS = frozenset(
    [
        # group: ops that can't fail at runtime
        # `txn FirstValidTime` could technically fail, but not on mainnet
        "txn",
        "sha256",
        "keccak256",
        "sha3_256",
        "sha512_256",
        "bitlen",
        # group: could only fail on a type error
        "!",
        "!=",
        "&",
        "&&",
        "<",
        "<=",
        "==",
        ">",
        ">=",
        "|",
        "||",
        "~",
        "addw",
        "mulw",
        "itob",
        "len",
        "select",
        "sqrt",
        "shl",
        "shr",
        "b&",
        "b|",
        "b~",
        # group: fail if an input is zero
        "%",
        "/",
        "expw",
        "divmodw",
        "divw",
        # group: fail on over/underflow
        "*",
        "+",
        "-",
        "^",
        "exp",
        # group: fail on index out of bounds
        "arg",
        "arg_0",
        "arg_1",
        "arg_2",
        "arg_3",
        "args",
        "extract",
        "extract3",
        "extract_uint16",
        "extract_uint32",
        "extract_uint64",
        "replace2",
        "replace3",
        "setbit",
        "setbyte",
        "getbit",
        "getbyte",
        "gaid",
        "gaids",
        "gload",
        "gloads",
        "gloadss",
        "substring",
        "substring3",
        "txna",
        "txnas",
        "gtxn",
        "gtxna",
        "gtxnas",
        "gtxns",
        "gtxnsa",
        "gtxnsas",
        "block",
        # group: fail on input too large
        "b%",
        "b*",
        "b+",
        "b-",
        "b/",
        "b^",
        "btoi",
        "b!=",
        "b<",
        "b<=",
        "b==",
        "b>",
        "b>=",
        "bsqrt",
        # group: fail on output too large
        "concat",
        "bzero",
        # group: fail on input format / byte lengths
        "base64_decode",
        "json_ref",
        "ecdsa_pk_decompress",
        "ecdsa_pk_recover",
        "ec_add",
        "ec_pairing_check",
        "ec_scalar_mul",
        "ec_subgroup_check",
        "ec_multi_scalar_mul",
        "ec_map_to",
        "ecdsa_verify",
        "ed25519verify",
        "ed25519verify_bare",
        "vrf_verify",
        "falcon_verify",
        "mimc",
        # AVM vNext ops (currently v13)
        "poseidon2",
        "sha512",
        "sumhash512",
    ]
)

# ops that have no observable side effects outside the function
# note: originally generated based on all ops that:
#       - return a stack value (this, as of v10, yields no false negatives)
#       - AND isn't in the generate_avm_ops.py list of exclusions (which are all control flow
#             or pure stack manipulations)
#       - AND isn't box_create or box_del, they were the only remaining false positives
IMPURE_SIDE_EFFECT_FREE_AVM_OPS = frozenset(
    [
        # group: ops that can't fail at runtime
        "global",  # OpcodeBudget is non-const, otherwise this could be pure
        # group: could only fail on a type error
        "app_global_get",
        "app_global_get_ex",
        "load",
        # group: fail on resource not "available"
        # TODO: determine if any of this group is pure
        "acct_params_get",
        "app_opted_in",
        "app_params_get",
        "asset_holding_get",
        "asset_params_get",
        "app_local_get",
        "app_local_get_ex",
        "balance",
        "min_balance",
        "box_extract",
        "box_get",
        "box_len",
        # group: fail on index out of bounds
        "loads",
        # group: might fail depending on state
        "itxn",
        "itxna",
        "itxnas",
        "gitxn",
        "gitxna",
        "gitxnas",
    ]
)

_should_be_empty = PURE_AVM_OPS & IMPURE_SIDE_EFFECT_FREE_AVM_OPS
assert not _should_be_empty, _should_be_empty
SIDE_EFFECT_FREE_AVM_OPS = frozenset([*PURE_AVM_OPS, *IMPURE_SIDE_EFFECT_FREE_AVM_OPS])

COMPILE_TIME_CONSTANT_OPS = frozenset(
    [
        # "generic" comparison ops
        "==",
        "!=",
        # uint64 comparison ops
        "<",
        "<=",
        ">",
        ">=",
        # boolean ops
        "!",
        "&&",
        "||",
        # uint64 bitwise ops
        "&",
        "|",
        "^",
        "~",
        "shl",
        "shr",
        # uint64 math
        "+",
        "-",
        "*",
        "/",
        "%",
        "exp",
        "sqrt",
        # wide math: multi-return - covered by GVN but not here
        "addw",
        "mulw",
        "divw",
        "expw",
        "divmodw",
        # bit/byte ops
        "concat",
        "extract",
        "extract3",
        "getbit",
        "getbyte",
        "len",
        "replace2",
        "replace3",
        "setbit",
        "setbyte",
        "substring",
        "substring3",
        # conversion
        "itob",
        "btoi",
        "extract_uint16",
        "extract_uint32",
        "extract_uint64",
        # byte math
        "b+",
        "b-",
        "b*",
        "b/",
        "b%",
        "bsqrt",
        # byte comparison ops
        "b==",
        "b!=",
        "b<",
        "b<=",
        "b>",
        "b>=",
        # byte bitwise ops
        "b&",
        "b|",
        "b^",
        "b~",
        # misc
        "bzero",
        "select",
        "bitlen",
        # implemented hash ops
        "keccak256",
        "sha256",
        "sha3_256",
        "sha512_256",
        # ! unimplemented for constant arg evaluation
        "base64_decode",
        "json_ref",
        "ec_add",
        "ec_map_to",
        "ec_multi_scalar_mul",
        "ec_pairing_check",
        "ec_scalar_mul",
        "ec_subgroup_check",
        "ecdsa_pk_decompress",
        "ecdsa_pk_recover",
        "ecdsa_verify",
        "ed25519verify",
        "ed25519verify_bare",
        "falcon_verify",
        "mimc",
        "vrf_verify",
        # AVM vNext ops (currently v13)
        "poseidon2",
        "sha512",
        "sumhash512",
    ]
)

assert COMPILE_TIME_CONSTANT_OPS.issubset(PURE_AVM_OPS), COMPILE_TIME_CONSTANT_OPS - PURE_AVM_OPS


def valid_uint64(x: int) -> bool:
    return 0 <= x <= algo_constants.MAX_UINT64


EXTRACT_UINTN_BYTE_SIZE: typing.Final[Mapping[AVMOp, int]] = {
    AVMOp.extract_uint16: 2,
    AVMOp.extract_uint32: 4,
    AVMOp.extract_uint64: 8,
}


def choose_encoding(
    a: AVMBytesEncoding, b: AVMBytesEncoding, *, is_concat: bool = False
) -> AVMBytesEncoding:
    if a == b:
        # special case handling of utf8:
        # most byte/bit ops. would destroy
        # encoding save for concat
        match a:
            case AVMBytesEncoding.utf8:
                return a if is_concat else AVMBytesEncoding.unknown
            case _:
                # preserve encoding if both equal
                return a
    # exclude utf8 from known choices, we don't preserve that encoding choice unless
    # they're both utf8 strings and the op. is a concat, which is covered by the first check
    known_binary_choices = {a, b} - {AVMBytesEncoding.utf8, AVMBytesEncoding.unknown}
    if not known_binary_choices:
        return AVMBytesEncoding.unknown

    # pick the most compact encoding of the known binary encodings
    if AVMBytesEncoding.base64 in known_binary_choices:
        return AVMBytesEncoding.base64
    if AVMBytesEncoding.base32 in known_binary_choices:
        return AVMBytesEncoding.base32
    return AVMBytesEncoding.base16
