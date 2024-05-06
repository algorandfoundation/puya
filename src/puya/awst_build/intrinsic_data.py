import typing
from collections.abc import Mapping, Sequence

from immutabledict import immutabledict

from puya.awst import wtypes
from puya.awst_build.intrinsic_models import (
    FunctionOpMapping,
    PropertyOpMapping,
)

ENUM_CLASSES: typing.Final = immutabledict[str, Mapping[str, str]](
    {
        "Base64": {
            "URLEncoding": "URLEncoding",
            "StdEncoding": "StdEncoding",
        },
        "ECDSA": {
            "Secp256k1": "Secp256k1",
            "Secp256r1": "Secp256r1",
        },
        "VrfVerify": {
            "VrfAlgorand": "VrfAlgorand",
        },
        "EC": {
            "BN254g1": "BN254g1",
            "BN254g2": "BN254g2",
            "BLS12_381g1": "BLS12_381g1",
            "BLS12_381g2": "BLS12_381g2",
        },
    }
)

FUNC_TO_AST_MAPPER: typing.Final = immutabledict[str, Sequence[FunctionOpMapping]](
    {
        "addw": (
            FunctionOpMapping(
                "addw",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                ),
            ),
        ),
        "app_opted_in": (
            FunctionOpMapping(
                "app_opted_in",
                stack_inputs=dict(
                    a=(wtypes.account_wtype, wtypes.uint64_wtype),
                    b=(wtypes.application_wtype, wtypes.uint64_wtype),
                ),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "arg": (
            FunctionOpMapping(
                "args",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
            FunctionOpMapping(
                "arg",
                immediates=dict(a=int),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "balance": (
            FunctionOpMapping(
                "balance",
                stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "base64_decode": (
            FunctionOpMapping(
                "base64_decode",
                immediates=dict(e=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "bitlen": (
            FunctionOpMapping(
                "bitlen",
                stack_inputs=dict(a=(wtypes.bytes_wtype, wtypes.uint64_wtype)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "bsqrt": (
            FunctionOpMapping(
                "bsqrt",
                stack_inputs=dict(a=(wtypes.biguint_wtype,)),
                stack_outputs=(wtypes.biguint_wtype,),
            ),
        ),
        "btoi": (
            FunctionOpMapping(
                "btoi",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "bzero": (
            FunctionOpMapping(
                "bzero",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "concat": (
            FunctionOpMapping(
                "concat",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "divmodw": (
            FunctionOpMapping(
                "divmodw",
                stack_inputs=dict(
                    a=(wtypes.uint64_wtype,),
                    b=(wtypes.uint64_wtype,),
                    c=(wtypes.uint64_wtype,),
                    d=(wtypes.uint64_wtype,),
                ),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                ),
            ),
        ),
        "divw": (
            FunctionOpMapping(
                "divw",
                stack_inputs=dict(
                    a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "ecdsa_pk_decompress": (
            FunctionOpMapping(
                "ecdsa_pk_decompress",
                immediates=dict(v=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(
                    wtypes.bytes_wtype,
                    wtypes.bytes_wtype,
                ),
            ),
        ),
        "ecdsa_pk_recover": (
            FunctionOpMapping(
                "ecdsa_pk_recover",
                immediates=dict(v=str),
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,),
                    b=(wtypes.uint64_wtype,),
                    c=(wtypes.bytes_wtype,),
                    d=(wtypes.bytes_wtype,),
                ),
                stack_outputs=(
                    wtypes.bytes_wtype,
                    wtypes.bytes_wtype,
                ),
            ),
        ),
        "ecdsa_verify": (
            FunctionOpMapping(
                "ecdsa_verify",
                immediates=dict(v=str),
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,),
                    b=(wtypes.bytes_wtype,),
                    c=(wtypes.bytes_wtype,),
                    d=(wtypes.bytes_wtype,),
                    e=(wtypes.bytes_wtype,),
                ),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "ed25519verify": (
            FunctionOpMapping(
                "ed25519verify",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,), c=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "ed25519verify_bare": (
            FunctionOpMapping(
                "ed25519verify_bare",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,), c=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "err": (
            FunctionOpMapping(
                "err",
            ),
        ),
        "exit": (
            FunctionOpMapping(
                "return",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "exp": (
            FunctionOpMapping(
                "exp",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "expw": (
            FunctionOpMapping(
                "expw",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                ),
            ),
        ),
        "extract": (
            FunctionOpMapping(
                "extract3",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
            FunctionOpMapping(
                "extract",
                immediates=dict(b=int, c=int),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "extract_uint16": (
            FunctionOpMapping(
                "extract_uint16",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "extract_uint32": (
            FunctionOpMapping(
                "extract_uint32",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "extract_uint64": (
            FunctionOpMapping(
                "extract_uint64",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "gaid": (
            FunctionOpMapping(
                "gaids",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.application_wtype,),
            ),
            FunctionOpMapping(
                "gaid",
                immediates=dict(a=int),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "getbit": (
            FunctionOpMapping(
                "getbit",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype, wtypes.uint64_wtype), b=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "getbyte": (
            FunctionOpMapping(
                "getbyte",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "gload_bytes": (
            FunctionOpMapping(
                "gloadss",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
            FunctionOpMapping(
                "gload",
                immediates=dict(a=int, b=int),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
            FunctionOpMapping(
                "gloads",
                immediates=dict(b=int),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "gload_uint64": (
            FunctionOpMapping(
                "gloadss",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
            FunctionOpMapping(
                "gload",
                immediates=dict(a=int, b=int),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
            FunctionOpMapping(
                "gloads",
                immediates=dict(b=int),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "itob": (
            FunctionOpMapping(
                "itob",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "keccak256": (
            FunctionOpMapping(
                "keccak256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "min_balance": (
            FunctionOpMapping(
                "min_balance",
                stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "mulw": (
            FunctionOpMapping(
                "mulw",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                ),
            ),
        ),
        "replace": (
            FunctionOpMapping(
                "replace3",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
            FunctionOpMapping(
                "replace2",
                immediates=dict(b=int),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), c=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "select_bytes": (
            FunctionOpMapping(
                "select",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,),
                    b=(wtypes.bytes_wtype,),
                    c=(wtypes.bool_wtype, wtypes.uint64_wtype),
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "select_uint64": (
            FunctionOpMapping(
                "select",
                stack_inputs=dict(
                    a=(wtypes.uint64_wtype,),
                    b=(wtypes.uint64_wtype,),
                    c=(wtypes.bool_wtype, wtypes.uint64_wtype),
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "setbit_bytes": (
            FunctionOpMapping(
                "setbit",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "setbit_uint64": (
            FunctionOpMapping(
                "setbit",
                stack_inputs=dict(
                    a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "setbyte": (
            FunctionOpMapping(
                "setbyte",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "sha256": (
            FunctionOpMapping(
                "sha256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "sha3_256": (
            FunctionOpMapping(
                "sha3_256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "sha512_256": (
            FunctionOpMapping(
                "sha512_256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "shl": (
            FunctionOpMapping(
                "shl",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "shr": (
            FunctionOpMapping(
                "shr",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "sqrt": (
            FunctionOpMapping(
                "sqrt",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "substring": (
            FunctionOpMapping(
                "substring3",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
            FunctionOpMapping(
                "substring",
                immediates=dict(b=int, c=int),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "vrf_verify": (
            FunctionOpMapping(
                "vrf_verify",
                immediates=dict(s=str),
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,), c=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(
                    wtypes.bytes_wtype,
                    wtypes.bool_wtype,
                ),
            ),
        ),
    }
)
NAMESPACE_CLASSES: typing.Final = immutabledict[
    str, immutabledict[str, PropertyOpMapping | Sequence[FunctionOpMapping]]
](
    {
        "AcctParamsGet": immutabledict(
            {
                "acct_balance": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctBalance=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_min_balance": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctMinBalance=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_auth_addr": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctAuthAddr=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_num_uint": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalNumUint=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_num_byte_slice": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalNumByteSlice=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_extra_app_pages": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalExtraAppPages=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_apps_created": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalAppsCreated=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_apps_opted_in": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalAppsOptedIn=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_assets_created": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalAssetsCreated=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_assets": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalAssets=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_boxes": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalBoxes=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "acct_total_box_bytes": (
                    FunctionOpMapping(
                        "acct_params_get",
                        immediates=dict(AcctTotalBoxBytes=None),
                        stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
            }
        ),
        "AppGlobal": immutabledict(
            {
                "get_bytes": (
                    FunctionOpMapping(
                        "app_global_get",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "get_uint64": (
                    FunctionOpMapping(
                        "app_global_get",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "get_ex_bytes": (
                    FunctionOpMapping(
                        "app_global_get_ex",
                        stack_inputs=dict(
                            a=(wtypes.application_wtype, wtypes.uint64_wtype),
                            b=(wtypes.bytes_wtype,),
                        ),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "get_ex_uint64": (
                    FunctionOpMapping(
                        "app_global_get_ex",
                        stack_inputs=dict(
                            a=(wtypes.application_wtype, wtypes.uint64_wtype),
                            b=(wtypes.bytes_wtype,),
                        ),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "delete": (
                    FunctionOpMapping(
                        "app_global_del",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "put": (
                    FunctionOpMapping(
                        "app_global_put",
                        stack_inputs=dict(
                            a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype, wtypes.uint64_wtype)
                        ),
                    ),
                ),
            }
        ),
        "AppLocal": immutabledict(
            {
                "get_bytes": (
                    FunctionOpMapping(
                        "app_local_get",
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                        ),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "get_uint64": (
                    FunctionOpMapping(
                        "app_local_get",
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                        ),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "get_ex_bytes": (
                    FunctionOpMapping(
                        "app_local_get_ex",
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype),
                            b=(wtypes.application_wtype, wtypes.uint64_wtype),
                            c=(wtypes.bytes_wtype,),
                        ),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "get_ex_uint64": (
                    FunctionOpMapping(
                        "app_local_get_ex",
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype),
                            b=(wtypes.application_wtype, wtypes.uint64_wtype),
                            c=(wtypes.bytes_wtype,),
                        ),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "delete": (
                    FunctionOpMapping(
                        "app_local_del",
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                        ),
                    ),
                ),
                "put": (
                    FunctionOpMapping(
                        "app_local_put",
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype),
                            b=(wtypes.bytes_wtype,),
                            c=(wtypes.bytes_wtype, wtypes.uint64_wtype),
                        ),
                    ),
                ),
            }
        ),
        "AppParamsGet": immutabledict(
            {
                "app_approval_program": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppApprovalProgram=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_clear_state_program": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppClearStateProgram=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_global_num_uint": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppGlobalNumUint=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_global_num_byte_slice": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppGlobalNumByteSlice=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_local_num_uint": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppLocalNumUint=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_local_num_byte_slice": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppLocalNumByteSlice=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_extra_program_pages": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppExtraProgramPages=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_creator": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppCreator=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "app_address": (
                    FunctionOpMapping(
                        "app_params_get",
                        immediates=dict(AppAddress=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
            }
        ),
        "AssetHoldingGet": immutabledict(
            {
                "asset_balance": (
                    FunctionOpMapping(
                        "asset_holding_get",
                        immediates=dict(AssetBalance=None),
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype),
                            b=(wtypes.asset_wtype, wtypes.uint64_wtype),
                        ),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_frozen": (
                    FunctionOpMapping(
                        "asset_holding_get",
                        immediates=dict(AssetFrozen=None),
                        stack_inputs=dict(
                            a=(wtypes.account_wtype, wtypes.uint64_wtype),
                            b=(wtypes.asset_wtype, wtypes.uint64_wtype),
                        ),
                        stack_outputs=(
                            wtypes.bool_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
            }
        ),
        "AssetParamsGet": immutabledict(
            {
                "asset_total": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetTotal=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_decimals": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetDecimals=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_default_frozen": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetDefaultFrozen=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.bool_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_unit_name": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetUnitName=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_name": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetName=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_url": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetURL=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_metadata_hash": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetMetadataHash=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_manager": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetManager=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_reserve": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetReserve=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_freeze": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetFreeze=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_clawback": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetClawback=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "asset_creator": (
                    FunctionOpMapping(
                        "asset_params_get",
                        immediates=dict(AssetCreator=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                        stack_outputs=(
                            wtypes.account_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
            }
        ),
        "Block": immutabledict(
            {
                "blk_seed": (
                    FunctionOpMapping(
                        "block",
                        immediates=dict(BlkSeed=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "blk_timestamp": (
                    FunctionOpMapping(
                        "block",
                        immediates=dict(BlkTimestamp=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
            }
        ),
        "Box": immutabledict(
            {
                "create": (
                    FunctionOpMapping(
                        "box_create",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "delete": (
                    FunctionOpMapping(
                        "box_del",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "extract": (
                    FunctionOpMapping(
                        "box_extract",
                        stack_inputs=dict(
                            a=(wtypes.bytes_wtype,),
                            b=(wtypes.uint64_wtype,),
                            c=(wtypes.uint64_wtype,),
                        ),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "get": (
                    FunctionOpMapping(
                        "box_get",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                        stack_outputs=(
                            wtypes.bytes_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "length": (
                    FunctionOpMapping(
                        "box_len",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                        stack_outputs=(
                            wtypes.uint64_wtype,
                            wtypes.bool_wtype,
                        ),
                    ),
                ),
                "put": (
                    FunctionOpMapping(
                        "box_put",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                    ),
                ),
                "replace": (
                    FunctionOpMapping(
                        "box_replace",
                        stack_inputs=dict(
                            a=(wtypes.bytes_wtype,),
                            b=(wtypes.uint64_wtype,),
                            c=(wtypes.bytes_wtype,),
                        ),
                    ),
                ),
                "resize": (
                    FunctionOpMapping(
                        "box_resize",
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                    ),
                ),
                "splice": (
                    FunctionOpMapping(
                        "box_splice",
                        stack_inputs=dict(
                            a=(wtypes.bytes_wtype,),
                            b=(wtypes.uint64_wtype,),
                            c=(wtypes.uint64_wtype,),
                            d=(wtypes.bytes_wtype,),
                        ),
                    ),
                ),
            }
        ),
        "EllipticCurve": immutabledict(
            {
                "add": (
                    FunctionOpMapping(
                        "ec_add",
                        immediates=dict(g=str),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "map_to": (
                    FunctionOpMapping(
                        "ec_map_to",
                        immediates=dict(g=str),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "scalar_mul_multi": (
                    FunctionOpMapping(
                        "ec_multi_scalar_mul",
                        immediates=dict(g=str),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "pairing_check": (
                    FunctionOpMapping(
                        "ec_pairing_check",
                        immediates=dict(g=str),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "scalar_mul": (
                    FunctionOpMapping(
                        "ec_scalar_mul",
                        immediates=dict(g=str),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "subgroup_check": (
                    FunctionOpMapping(
                        "ec_subgroup_check",
                        immediates=dict(g=str),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
            }
        ),
        "GITxn": immutabledict(
            {
                "sender": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Sender=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "fee": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Fee=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "first_valid": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, FirstValid=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "first_valid_time": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, FirstValidTime=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "last_valid": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, LastValid=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "note": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Note=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "lease": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Lease=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "receiver": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Receiver=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "amount": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Amount=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "close_remainder_to": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, CloseRemainderTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "vote_pk": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, VotePK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "selection_pk": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, SelectionPK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "vote_first": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, VoteFirst=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "vote_last": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, VoteLast=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "vote_key_dilution": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, VoteKeyDilution=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "type": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Type=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "type_enum": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, TypeEnum=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "xfer_asset": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, XferAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "asset_amount": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, AssetAmount=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "asset_sender": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, AssetSender=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "asset_receiver": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, AssetReceiver=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "asset_close_to": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, AssetCloseTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "group_index": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, GroupIndex=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "tx_id": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, TxID=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "application_id": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ApplicationID=None),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "on_completion": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, OnCompletion=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "application_args": (
                    FunctionOpMapping(
                        "gitxnas",
                        immediates=dict(t=int, ApplicationArgs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gitxna",
                        immediates=dict(t=int, ApplicationArgs=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_app_args": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, NumAppArgs=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "accounts": (
                    FunctionOpMapping(
                        "gitxnas",
                        immediates=dict(t=int, Accounts=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gitxna",
                        immediates=dict(t=int, Accounts=None, a=int),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "num_accounts": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, NumAccounts=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "approval_program": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ApprovalProgram=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "clear_state_program": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ClearStateProgram=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "rekey_to": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, RekeyTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "config_asset_total": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetTotal=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "config_asset_decimals": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetDecimals=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "config_asset_default_frozen": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetDefaultFrozen=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "config_asset_unit_name": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetUnitName=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_name": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetName=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_url": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetURL=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_metadata_hash": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetMetadataHash=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_manager": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetManager=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_reserve": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetReserve=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_freeze": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetFreeze=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_clawback": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ConfigAssetClawback=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "freeze_asset": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, FreezeAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "freeze_asset_account": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, FreezeAssetAccount=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "freeze_asset_frozen": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, FreezeAssetFrozen=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "assets": (
                    FunctionOpMapping(
                        "gitxnas",
                        immediates=dict(t=int, Assets=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gitxna",
                        immediates=dict(t=int, Assets=None, a=int),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "num_assets": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, NumAssets=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "applications": (
                    FunctionOpMapping(
                        "gitxnas",
                        immediates=dict(t=int, Applications=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "gitxna",
                        immediates=dict(t=int, Applications=None, a=int),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "num_applications": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, NumApplications=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "global_num_uint": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, GlobalNumUint=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "global_num_byte_slice": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, GlobalNumByteSlice=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "local_num_uint": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, LocalNumUint=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "local_num_byte_slice": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, LocalNumByteSlice=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "extra_program_pages": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, ExtraProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "nonparticipation": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, Nonparticipation=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "logs": (
                    FunctionOpMapping(
                        "gitxnas",
                        immediates=dict(t=int, Logs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gitxna",
                        immediates=dict(t=int, Logs=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_logs": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, NumLogs=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "created_asset_id": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, CreatedAssetID=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "created_application_id": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, CreatedApplicationID=None),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "last_log": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, LastLog=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "state_proof_pk": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, StateProofPK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "approval_program_pages": (
                    FunctionOpMapping(
                        "gitxnas",
                        immediates=dict(t=int, ApprovalProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gitxna",
                        immediates=dict(t=int, ApprovalProgramPages=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_approval_program_pages": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, NumApprovalProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "clear_state_program_pages": (
                    FunctionOpMapping(
                        "gitxnas",
                        immediates=dict(t=int, ClearStateProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gitxna",
                        immediates=dict(t=int, ClearStateProgramPages=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_clear_state_program_pages": (
                    FunctionOpMapping(
                        "gitxn",
                        immediates=dict(t=int, NumClearStateProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
            }
        ),
        "GTxn": immutabledict(
            {
                "sender": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Sender=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Sender=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "fee": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Fee=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Fee=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "first_valid": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(FirstValid=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, FirstValid=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "first_valid_time": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(FirstValidTime=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, FirstValidTime=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "last_valid": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(LastValid=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, LastValid=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "note": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Note=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Note=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "lease": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Lease=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Lease=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "receiver": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Receiver=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Receiver=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "amount": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Amount=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Amount=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "close_remainder_to": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(CloseRemainderTo=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, CloseRemainderTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "vote_pk": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(VotePK=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, VotePK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "selection_pk": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(SelectionPK=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, SelectionPK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "vote_first": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(VoteFirst=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, VoteFirst=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "vote_last": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(VoteLast=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, VoteLast=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "vote_key_dilution": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(VoteKeyDilution=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, VoteKeyDilution=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "type": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Type=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Type=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "type_enum": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(TypeEnum=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, TypeEnum=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "xfer_asset": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(XferAsset=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, XferAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "asset_amount": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(AssetAmount=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, AssetAmount=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "asset_sender": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(AssetSender=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, AssetSender=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "asset_receiver": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(AssetReceiver=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, AssetReceiver=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "asset_close_to": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(AssetCloseTo=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, AssetCloseTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "group_index": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(GroupIndex=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, GroupIndex=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "tx_id": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(TxID=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, TxID=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "application_id": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ApplicationID=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ApplicationID=None),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "on_completion": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(OnCompletion=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, OnCompletion=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "application_args": (
                    FunctionOpMapping(
                        "gtxnsas",
                        immediates=dict(ApplicationArgs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnsa",
                        immediates=dict(ApplicationArgs=None, b=int),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxna",
                        immediates=dict(a=int, ApplicationArgs=None, b=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnas",
                        immediates=dict(a=int, ApplicationArgs=None),
                        stack_inputs=dict(b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_app_args": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(NumAppArgs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, NumAppArgs=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "accounts": (
                    FunctionOpMapping(
                        "gtxnsas",
                        immediates=dict(Accounts=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnsa",
                        immediates=dict(Accounts=None, b=int),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxna",
                        immediates=dict(a=int, Accounts=None, b=int),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnas",
                        immediates=dict(a=int, Accounts=None),
                        stack_inputs=dict(b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "num_accounts": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(NumAccounts=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, NumAccounts=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "approval_program": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ApprovalProgram=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ApprovalProgram=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "clear_state_program": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ClearStateProgram=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ClearStateProgram=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "rekey_to": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(RekeyTo=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, RekeyTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAsset=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "config_asset_total": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetTotal=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetTotal=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "config_asset_decimals": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetDecimals=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetDecimals=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "config_asset_default_frozen": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetDefaultFrozen=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetDefaultFrozen=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "config_asset_unit_name": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetUnitName=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetUnitName=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_name": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetName=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetName=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_url": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetURL=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetURL=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_metadata_hash": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetMetadataHash=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetMetadataHash=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_manager": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetManager=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetManager=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_reserve": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetReserve=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetReserve=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_freeze": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetFreeze=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetFreeze=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_clawback": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ConfigAssetClawback=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ConfigAssetClawback=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "freeze_asset": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(FreezeAsset=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, FreezeAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "freeze_asset_account": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(FreezeAssetAccount=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, FreezeAssetAccount=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "freeze_asset_frozen": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(FreezeAssetFrozen=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, FreezeAssetFrozen=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "assets": (
                    FunctionOpMapping(
                        "gtxnsas",
                        immediates=dict(Assets=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnsa",
                        immediates=dict(Assets=None, b=int),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxna",
                        immediates=dict(a=int, Assets=None, b=int),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnas",
                        immediates=dict(a=int, Assets=None),
                        stack_inputs=dict(b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "num_assets": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(NumAssets=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, NumAssets=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "applications": (
                    FunctionOpMapping(
                        "gtxnsas",
                        immediates=dict(Applications=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnsa",
                        immediates=dict(Applications=None, b=int),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxna",
                        immediates=dict(a=int, Applications=None, b=int),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnas",
                        immediates=dict(a=int, Applications=None),
                        stack_inputs=dict(b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "num_applications": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(NumApplications=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, NumApplications=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "global_num_uint": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(GlobalNumUint=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, GlobalNumUint=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "global_num_byte_slice": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(GlobalNumByteSlice=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, GlobalNumByteSlice=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "local_num_uint": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(LocalNumUint=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, LocalNumUint=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "local_num_byte_slice": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(LocalNumByteSlice=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, LocalNumByteSlice=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "extra_program_pages": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(ExtraProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, ExtraProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "nonparticipation": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(Nonparticipation=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, Nonparticipation=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "logs": (
                    FunctionOpMapping(
                        "gtxnsas",
                        immediates=dict(Logs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnsa",
                        immediates=dict(Logs=None, b=int),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxna",
                        immediates=dict(a=int, Logs=None, b=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnas",
                        immediates=dict(a=int, Logs=None),
                        stack_inputs=dict(b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_logs": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(NumLogs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, NumLogs=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "created_asset_id": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(CreatedAssetID=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, CreatedAssetID=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "created_application_id": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(CreatedApplicationID=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, CreatedApplicationID=None),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "last_log": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(LastLog=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, LastLog=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "state_proof_pk": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(StateProofPK=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, StateProofPK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "approval_program_pages": (
                    FunctionOpMapping(
                        "gtxnsas",
                        immediates=dict(ApprovalProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnsa",
                        immediates=dict(ApprovalProgramPages=None, b=int),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxna",
                        immediates=dict(a=int, ApprovalProgramPages=None, b=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnas",
                        immediates=dict(a=int, ApprovalProgramPages=None),
                        stack_inputs=dict(b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_approval_program_pages": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(NumApprovalProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, NumApprovalProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "clear_state_program_pages": (
                    FunctionOpMapping(
                        "gtxnsas",
                        immediates=dict(ClearStateProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnsa",
                        immediates=dict(ClearStateProgramPages=None, b=int),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxna",
                        immediates=dict(a=int, ClearStateProgramPages=None, b=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxnas",
                        immediates=dict(a=int, ClearStateProgramPages=None),
                        stack_inputs=dict(b=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_clear_state_program_pages": (
                    FunctionOpMapping(
                        "gtxns",
                        immediates=dict(NumClearStateProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                    FunctionOpMapping(
                        "gtxn",
                        immediates=dict(a=int, NumClearStateProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
            }
        ),
        "Global": immutabledict(
            {
                "min_txn_fee": PropertyOpMapping(
                    "global",
                    immediates=("MinTxnFee",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "min_balance": PropertyOpMapping(
                    "global",
                    immediates=("MinBalance",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "max_txn_life": PropertyOpMapping(
                    "global",
                    immediates=("MaxTxnLife",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "zero_address": PropertyOpMapping(
                    "global",
                    immediates=("ZeroAddress",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "group_size": PropertyOpMapping(
                    "global",
                    immediates=("GroupSize",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "logic_sig_version": PropertyOpMapping(
                    "global",
                    immediates=("LogicSigVersion",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "round": PropertyOpMapping(
                    "global",
                    immediates=("Round",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "latest_timestamp": PropertyOpMapping(
                    "global",
                    immediates=("LatestTimestamp",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "current_application_id": PropertyOpMapping(
                    "global",
                    immediates=("CurrentApplicationID",),
                    stack_outputs=(wtypes.application_wtype,),
                ),
                "creator_address": PropertyOpMapping(
                    "global",
                    immediates=("CreatorAddress",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "current_application_address": PropertyOpMapping(
                    "global",
                    immediates=("CurrentApplicationAddress",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "group_id": PropertyOpMapping(
                    "global",
                    immediates=("GroupID",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "opcode_budget": (
                    FunctionOpMapping(
                        "global",
                        immediates=dict(OpcodeBudget=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "caller_application_id": PropertyOpMapping(
                    "global",
                    immediates=("CallerApplicationID",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "caller_application_address": PropertyOpMapping(
                    "global",
                    immediates=("CallerApplicationAddress",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "asset_create_min_balance": PropertyOpMapping(
                    "global",
                    immediates=("AssetCreateMinBalance",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "asset_opt_in_min_balance": PropertyOpMapping(
                    "global",
                    immediates=("AssetOptInMinBalance",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "genesis_hash": PropertyOpMapping(
                    "global",
                    immediates=("GenesisHash",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
            }
        ),
        "ITxn": immutabledict(
            {
                "sender": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Sender=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "fee": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Fee=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "first_valid": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(FirstValid=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "first_valid_time": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(FirstValidTime=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "last_valid": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(LastValid=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "note": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Note=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "lease": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Lease=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "receiver": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Receiver=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "amount": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Amount=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "close_remainder_to": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(CloseRemainderTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "vote_pk": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(VotePK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "selection_pk": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(SelectionPK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "vote_first": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(VoteFirst=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "vote_last": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(VoteLast=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "vote_key_dilution": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(VoteKeyDilution=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "type": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Type=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "type_enum": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(TypeEnum=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "xfer_asset": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(XferAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "asset_amount": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(AssetAmount=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "asset_sender": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(AssetSender=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "asset_receiver": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(AssetReceiver=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "asset_close_to": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(AssetCloseTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "group_index": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(GroupIndex=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "tx_id": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(TxID=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "application_id": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ApplicationID=None),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "on_completion": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(OnCompletion=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "application_args": (
                    FunctionOpMapping(
                        "itxnas",
                        immediates=dict(ApplicationArgs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "itxna",
                        immediates=dict(ApplicationArgs=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_app_args": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(NumAppArgs=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "accounts": (
                    FunctionOpMapping(
                        "itxnas",
                        immediates=dict(Accounts=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "itxna",
                        immediates=dict(Accounts=None, a=int),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "num_accounts": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(NumAccounts=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "approval_program": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ApprovalProgram=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "clear_state_program": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ClearStateProgram=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "rekey_to": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(RekeyTo=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "config_asset_total": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetTotal=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "config_asset_decimals": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetDecimals=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "config_asset_default_frozen": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetDefaultFrozen=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "config_asset_unit_name": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetUnitName=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_name": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetName=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_url": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetURL=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_metadata_hash": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetMetadataHash=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "config_asset_manager": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetManager=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_reserve": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetReserve=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_freeze": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetFreeze=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "config_asset_clawback": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ConfigAssetClawback=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "freeze_asset": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(FreezeAsset=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "freeze_asset_account": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(FreezeAssetAccount=None),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "freeze_asset_frozen": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(FreezeAssetFrozen=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "assets": (
                    FunctionOpMapping(
                        "itxnas",
                        immediates=dict(Assets=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "itxna",
                        immediates=dict(Assets=None, a=int),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "num_assets": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(NumAssets=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "applications": (
                    FunctionOpMapping(
                        "itxnas",
                        immediates=dict(Applications=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "itxna",
                        immediates=dict(Applications=None, a=int),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "num_applications": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(NumApplications=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "global_num_uint": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(GlobalNumUint=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "global_num_byte_slice": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(GlobalNumByteSlice=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "local_num_uint": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(LocalNumUint=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "local_num_byte_slice": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(LocalNumByteSlice=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "extra_program_pages": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(ExtraProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "nonparticipation": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(Nonparticipation=None),
                        stack_outputs=(wtypes.bool_wtype,),
                    ),
                ),
                "logs": (
                    FunctionOpMapping(
                        "itxnas",
                        immediates=dict(Logs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "itxna",
                        immediates=dict(Logs=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_logs": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(NumLogs=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "created_asset_id": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(CreatedAssetID=None),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "created_application_id": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(CreatedApplicationID=None),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "last_log": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(LastLog=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "state_proof_pk": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(StateProofPK=None),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "approval_program_pages": (
                    FunctionOpMapping(
                        "itxnas",
                        immediates=dict(ApprovalProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "itxna",
                        immediates=dict(ApprovalProgramPages=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_approval_program_pages": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(NumApprovalProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "clear_state_program_pages": (
                    FunctionOpMapping(
                        "itxnas",
                        immediates=dict(ClearStateProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "itxna",
                        immediates=dict(ClearStateProgramPages=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_clear_state_program_pages": (
                    FunctionOpMapping(
                        "itxn",
                        immediates=dict(NumClearStateProgramPages=None),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
            }
        ),
        "ITxnCreate": immutabledict(
            {
                "begin": (
                    FunctionOpMapping(
                        "itxn_begin",
                    ),
                ),
                "next": (
                    FunctionOpMapping(
                        "itxn_next",
                    ),
                ),
                "submit": (
                    FunctionOpMapping(
                        "itxn_submit",
                    ),
                ),
                "set_sender": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Sender=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_fee": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Fee=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_note": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Note=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_receiver": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Receiver=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_amount": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Amount=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_close_remainder_to": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(CloseRemainderTo=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_vote_pk": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(VotePK=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_selection_pk": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(SelectionPK=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_vote_first": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(VoteFirst=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_vote_last": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(VoteLast=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_vote_key_dilution": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(VoteKeyDilution=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_type": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Type=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_type_enum": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(TypeEnum=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_xfer_asset": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(XferAsset=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                    ),
                ),
                "set_asset_amount": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(AssetAmount=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_asset_sender": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(AssetSender=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_asset_receiver": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(AssetReceiver=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_asset_close_to": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(AssetCloseTo=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_application_id": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ApplicationID=None),
                        stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
                    ),
                ),
                "set_on_completion": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(OnCompletion=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_application_args": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ApplicationArgs=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_accounts": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Accounts=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_approval_program": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ApprovalProgram=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_clear_state_program": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ClearStateProgram=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_rekey_to": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(RekeyTo=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_config_asset": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAsset=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                    ),
                ),
                "set_config_asset_total": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetTotal=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_config_asset_decimals": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetDecimals=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_config_asset_default_frozen": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetDefaultFrozen=None),
                        stack_inputs=dict(a=(wtypes.bool_wtype, wtypes.uint64_wtype)),
                    ),
                ),
                "set_config_asset_unit_name": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetUnitName=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_config_asset_name": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetName=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_config_asset_url": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetURL=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_config_asset_metadata_hash": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetMetadataHash=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_config_asset_manager": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetManager=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_config_asset_reserve": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetReserve=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_config_asset_freeze": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetFreeze=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_config_asset_clawback": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ConfigAssetClawback=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_freeze_asset": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(FreezeAsset=None),
                        stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
                    ),
                ),
                "set_freeze_asset_account": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(FreezeAssetAccount=None),
                        stack_inputs=dict(a=(wtypes.account_wtype,)),
                    ),
                ),
                "set_freeze_asset_frozen": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(FreezeAssetFrozen=None),
                        stack_inputs=dict(a=(wtypes.bool_wtype, wtypes.uint64_wtype)),
                    ),
                ),
                "set_assets": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Assets=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_applications": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Applications=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_global_num_uint": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(GlobalNumUint=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_global_num_byte_slice": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(GlobalNumByteSlice=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_local_num_uint": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(LocalNumUint=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_local_num_byte_slice": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(LocalNumByteSlice=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_extra_program_pages": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ExtraProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                    ),
                ),
                "set_nonparticipation": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(Nonparticipation=None),
                        stack_inputs=dict(a=(wtypes.bool_wtype, wtypes.uint64_wtype)),
                    ),
                ),
                "set_state_proof_pk": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(StateProofPK=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_approval_program_pages": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ApprovalProgramPages=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
                "set_clear_state_program_pages": (
                    FunctionOpMapping(
                        "itxn_field",
                        immediates=dict(ClearStateProgramPages=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                    ),
                ),
            }
        ),
        "JsonRef": immutabledict(
            {
                "json_string": (
                    FunctionOpMapping(
                        "json_ref",
                        immediates=dict(JSONString=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "json_uint64": (
                    FunctionOpMapping(
                        "json_ref",
                        immediates=dict(JSONUint64=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "json_object": (
                    FunctionOpMapping(
                        "json_ref",
                        immediates=dict(JSONObject=None),
                        stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
            }
        ),
        "Scratch": immutabledict(
            {
                "load_bytes": (
                    FunctionOpMapping(
                        "loads",
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "load_uint64": (
                    FunctionOpMapping(
                        "loads",
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.uint64_wtype,),
                    ),
                ),
                "store": (
                    FunctionOpMapping(
                        "stores",
                        stack_inputs=dict(
                            a=(wtypes.uint64_wtype,), b=(wtypes.bytes_wtype, wtypes.uint64_wtype)
                        ),
                    ),
                ),
            }
        ),
        "Txn": immutabledict(
            {
                "sender": PropertyOpMapping(
                    "txn",
                    immediates=("Sender",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "fee": PropertyOpMapping(
                    "txn",
                    immediates=("Fee",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "first_valid": PropertyOpMapping(
                    "txn",
                    immediates=("FirstValid",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "first_valid_time": PropertyOpMapping(
                    "txn",
                    immediates=("FirstValidTime",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "last_valid": PropertyOpMapping(
                    "txn",
                    immediates=("LastValid",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "note": PropertyOpMapping(
                    "txn",
                    immediates=("Note",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "lease": PropertyOpMapping(
                    "txn",
                    immediates=("Lease",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "receiver": PropertyOpMapping(
                    "txn",
                    immediates=("Receiver",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "amount": PropertyOpMapping(
                    "txn",
                    immediates=("Amount",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "close_remainder_to": PropertyOpMapping(
                    "txn",
                    immediates=("CloseRemainderTo",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "vote_pk": PropertyOpMapping(
                    "txn",
                    immediates=("VotePK",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "selection_pk": PropertyOpMapping(
                    "txn",
                    immediates=("SelectionPK",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "vote_first": PropertyOpMapping(
                    "txn",
                    immediates=("VoteFirst",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "vote_last": PropertyOpMapping(
                    "txn",
                    immediates=("VoteLast",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "vote_key_dilution": PropertyOpMapping(
                    "txn",
                    immediates=("VoteKeyDilution",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "type": PropertyOpMapping(
                    "txn",
                    immediates=("Type",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "type_enum": PropertyOpMapping(
                    "txn",
                    immediates=("TypeEnum",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "xfer_asset": PropertyOpMapping(
                    "txn",
                    immediates=("XferAsset",),
                    stack_outputs=(wtypes.asset_wtype,),
                ),
                "asset_amount": PropertyOpMapping(
                    "txn",
                    immediates=("AssetAmount",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "asset_sender": PropertyOpMapping(
                    "txn",
                    immediates=("AssetSender",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "asset_receiver": PropertyOpMapping(
                    "txn",
                    immediates=("AssetReceiver",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "asset_close_to": PropertyOpMapping(
                    "txn",
                    immediates=("AssetCloseTo",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "group_index": PropertyOpMapping(
                    "txn",
                    immediates=("GroupIndex",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "tx_id": PropertyOpMapping(
                    "txn",
                    immediates=("TxID",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "application_id": PropertyOpMapping(
                    "txn",
                    immediates=("ApplicationID",),
                    stack_outputs=(wtypes.application_wtype,),
                ),
                "on_completion": PropertyOpMapping(
                    "txn",
                    immediates=("OnCompletion",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "application_args": (
                    FunctionOpMapping(
                        "txnas",
                        immediates=dict(ApplicationArgs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "txna",
                        immediates=dict(ApplicationArgs=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_app_args": PropertyOpMapping(
                    "txn",
                    immediates=("NumAppArgs",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "accounts": (
                    FunctionOpMapping(
                        "txnas",
                        immediates=dict(Accounts=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                    FunctionOpMapping(
                        "txna",
                        immediates=dict(Accounts=None, a=int),
                        stack_outputs=(wtypes.account_wtype,),
                    ),
                ),
                "num_accounts": PropertyOpMapping(
                    "txn",
                    immediates=("NumAccounts",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "approval_program": PropertyOpMapping(
                    "txn",
                    immediates=("ApprovalProgram",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "clear_state_program": PropertyOpMapping(
                    "txn",
                    immediates=("ClearStateProgram",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "rekey_to": PropertyOpMapping(
                    "txn",
                    immediates=("RekeyTo",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "config_asset": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAsset",),
                    stack_outputs=(wtypes.asset_wtype,),
                ),
                "config_asset_total": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetTotal",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "config_asset_decimals": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetDecimals",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "config_asset_default_frozen": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetDefaultFrozen",),
                    stack_outputs=(wtypes.bool_wtype,),
                ),
                "config_asset_unit_name": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetUnitName",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "config_asset_name": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetName",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "config_asset_url": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetURL",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "config_asset_metadata_hash": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetMetadataHash",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "config_asset_manager": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetManager",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "config_asset_reserve": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetReserve",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "config_asset_freeze": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetFreeze",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "config_asset_clawback": PropertyOpMapping(
                    "txn",
                    immediates=("ConfigAssetClawback",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "freeze_asset": PropertyOpMapping(
                    "txn",
                    immediates=("FreezeAsset",),
                    stack_outputs=(wtypes.asset_wtype,),
                ),
                "freeze_asset_account": PropertyOpMapping(
                    "txn",
                    immediates=("FreezeAssetAccount",),
                    stack_outputs=(wtypes.account_wtype,),
                ),
                "freeze_asset_frozen": PropertyOpMapping(
                    "txn",
                    immediates=("FreezeAssetFrozen",),
                    stack_outputs=(wtypes.bool_wtype,),
                ),
                "assets": (
                    FunctionOpMapping(
                        "txnas",
                        immediates=dict(Assets=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                    FunctionOpMapping(
                        "txna",
                        immediates=dict(Assets=None, a=int),
                        stack_outputs=(wtypes.asset_wtype,),
                    ),
                ),
                "num_assets": PropertyOpMapping(
                    "txn",
                    immediates=("NumAssets",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "applications": (
                    FunctionOpMapping(
                        "txnas",
                        immediates=dict(Applications=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                    FunctionOpMapping(
                        "txna",
                        immediates=dict(Applications=None, a=int),
                        stack_outputs=(wtypes.application_wtype,),
                    ),
                ),
                "num_applications": PropertyOpMapping(
                    "txn",
                    immediates=("NumApplications",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "global_num_uint": PropertyOpMapping(
                    "txn",
                    immediates=("GlobalNumUint",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "global_num_byte_slice": PropertyOpMapping(
                    "txn",
                    immediates=("GlobalNumByteSlice",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "local_num_uint": PropertyOpMapping(
                    "txn",
                    immediates=("LocalNumUint",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "local_num_byte_slice": PropertyOpMapping(
                    "txn",
                    immediates=("LocalNumByteSlice",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "extra_program_pages": PropertyOpMapping(
                    "txn",
                    immediates=("ExtraProgramPages",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "nonparticipation": PropertyOpMapping(
                    "txn",
                    immediates=("Nonparticipation",),
                    stack_outputs=(wtypes.bool_wtype,),
                ),
                "logs": (
                    FunctionOpMapping(
                        "txnas",
                        immediates=dict(Logs=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "txna",
                        immediates=dict(Logs=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_logs": PropertyOpMapping(
                    "txn",
                    immediates=("NumLogs",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "created_asset_id": PropertyOpMapping(
                    "txn",
                    immediates=("CreatedAssetID",),
                    stack_outputs=(wtypes.asset_wtype,),
                ),
                "created_application_id": PropertyOpMapping(
                    "txn",
                    immediates=("CreatedApplicationID",),
                    stack_outputs=(wtypes.application_wtype,),
                ),
                "last_log": PropertyOpMapping(
                    "txn",
                    immediates=("LastLog",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "state_proof_pk": PropertyOpMapping(
                    "txn",
                    immediates=("StateProofPK",),
                    stack_outputs=(wtypes.bytes_wtype,),
                ),
                "approval_program_pages": (
                    FunctionOpMapping(
                        "txnas",
                        immediates=dict(ApprovalProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "txna",
                        immediates=dict(ApprovalProgramPages=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_approval_program_pages": PropertyOpMapping(
                    "txn",
                    immediates=("NumApprovalProgramPages",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
                "clear_state_program_pages": (
                    FunctionOpMapping(
                        "txnas",
                        immediates=dict(ClearStateProgramPages=None),
                        stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                    FunctionOpMapping(
                        "txna",
                        immediates=dict(ClearStateProgramPages=None, a=int),
                        stack_outputs=(wtypes.bytes_wtype,),
                    ),
                ),
                "num_clear_state_program_pages": PropertyOpMapping(
                    "txn",
                    immediates=("NumClearStateProgramPages",),
                    stack_outputs=(wtypes.uint64_wtype,),
                ),
            }
        ),
    }
)
