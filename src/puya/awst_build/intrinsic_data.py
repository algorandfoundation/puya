import typing
from collections.abc import Mapping, Sequence

from immutabledict import immutabledict

from puya.awst import wtypes
from puya.awst_build.intrinsic_models import FunctionOpMapping

ENUM_CLASSES: typing.Final = immutabledict[str, Mapping[str, str]](
    {
        "algopy.op.Base64": {
            "URLEncoding": "URLEncoding",
            "StdEncoding": "StdEncoding",
        },
        "algopy.op.ECDSA": {
            "Secp256k1": "Secp256k1",
            "Secp256r1": "Secp256r1",
        },
        "algopy.op.VrfVerify": {
            "VrfAlgorand": "VrfAlgorand",
        },
        "algopy.op.EC": {
            "BN254g1": "BN254g1",
            "BN254g2": "BN254g2",
            "BLS12_381g1": "BLS12_381g1",
            "BLS12_381g2": "BLS12_381g2",
        },
    }
)

STUB_TO_AST_MAPPER: typing.Final = immutabledict[str, Sequence[FunctionOpMapping]](
    {
        "algopy.op.addw": (
            FunctionOpMapping(
                "addw",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                ),
            ),
        ),
        "algopy.op.app_opted_in": (
            FunctionOpMapping(
                "app_opted_in",
                stack_inputs=dict(
                    a=(wtypes.account_wtype, wtypes.uint64_wtype),
                    b=(wtypes.application_wtype, wtypes.uint64_wtype),
                ),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.arg": (
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
        "algopy.op.balance": (
            FunctionOpMapping(
                "balance",
                stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.base64_decode": (
            FunctionOpMapping(
                "base64_decode",
                immediates=dict(e=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.bitlen": (
            FunctionOpMapping(
                "bitlen",
                stack_inputs=dict(a=(wtypes.bytes_wtype, wtypes.uint64_wtype)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.bsqrt": (
            FunctionOpMapping(
                "bsqrt",
                stack_inputs=dict(a=(wtypes.biguint_wtype,)),
                stack_outputs=(wtypes.biguint_wtype,),
            ),
        ),
        "algopy.op.btoi": (
            FunctionOpMapping(
                "btoi",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.bzero": (
            FunctionOpMapping(
                "bzero",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.concat": (
            FunctionOpMapping(
                "concat",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.divmodw": (
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
        "algopy.op.divw": (
            FunctionOpMapping(
                "divw",
                stack_inputs=dict(
                    a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ecdsa_pk_decompress": (
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
        "algopy.op.ecdsa_pk_recover": (
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
        "algopy.op.ecdsa_verify": (
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
        "algopy.op.ed25519verify": (
            FunctionOpMapping(
                "ed25519verify",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,), c=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.ed25519verify_bare": (
            FunctionOpMapping(
                "ed25519verify_bare",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,), c=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.err": (
            FunctionOpMapping(
                "err",
            ),
        ),
        "algopy.op.exit": (
            FunctionOpMapping(
                "return",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.exp": (
            FunctionOpMapping(
                "exp",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.expw": (
            FunctionOpMapping(
                "expw",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                ),
            ),
        ),
        "algopy.op.extract": (
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
        "algopy.op.extract_uint16": (
            FunctionOpMapping(
                "extract_uint16",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.extract_uint32": (
            FunctionOpMapping(
                "extract_uint32",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.extract_uint64": (
            FunctionOpMapping(
                "extract_uint64",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.gaid": (
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
        "algopy.op.getbit": (
            FunctionOpMapping(
                "getbit",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype, wtypes.uint64_wtype), b=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.getbyte": (
            FunctionOpMapping(
                "getbyte",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.gload_bytes": (
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
        "algopy.op.gload_uint64": (
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
        "algopy.op.itob": (
            FunctionOpMapping(
                "itob",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.keccak256": (
            FunctionOpMapping(
                "keccak256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.min_balance": (
            FunctionOpMapping(
                "min_balance",
                stack_inputs=dict(a=(wtypes.account_wtype, wtypes.uint64_wtype)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.mulw": (
            FunctionOpMapping(
                "mulw",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.uint64_wtype,
                ),
            ),
        ),
        "algopy.op.replace": (
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
        "algopy.op.select_bytes": (
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
        "algopy.op.select_uint64": (
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
        "algopy.op.setbit_bytes": (
            FunctionOpMapping(
                "setbit",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.setbit_uint64": (
            FunctionOpMapping(
                "setbit",
                stack_inputs=dict(
                    a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.setbyte": (
            FunctionOpMapping(
                "setbyte",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.sha256": (
            FunctionOpMapping(
                "sha256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.sha3_256": (
            FunctionOpMapping(
                "sha3_256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.sha512_256": (
            FunctionOpMapping(
                "sha512_256",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.shl": (
            FunctionOpMapping(
                "shl",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.shr": (
            FunctionOpMapping(
                "shr",
                stack_inputs=dict(a=(wtypes.uint64_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.sqrt": (
            FunctionOpMapping(
                "sqrt",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.substring": (
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
        "algopy.op.vrf_verify": (
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
        "algopy.op.AcctParamsGet.acct_balance": (
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
        "algopy.op.AcctParamsGet.acct_min_balance": (
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
        "algopy.op.AcctParamsGet.acct_auth_addr": (
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
        "algopy.op.AcctParamsGet.acct_total_num_uint": (
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
        "algopy.op.AcctParamsGet.acct_total_num_byte_slice": (
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
        "algopy.op.AcctParamsGet.acct_total_extra_app_pages": (
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
        "algopy.op.AcctParamsGet.acct_total_apps_created": (
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
        "algopy.op.AcctParamsGet.acct_total_apps_opted_in": (
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
        "algopy.op.AcctParamsGet.acct_total_assets_created": (
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
        "algopy.op.AcctParamsGet.acct_total_assets": (
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
        "algopy.op.AcctParamsGet.acct_total_boxes": (
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
        "algopy.op.AcctParamsGet.acct_total_box_bytes": (
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
        "algopy.op.AppGlobal.get_bytes": (
            FunctionOpMapping(
                "app_global_get",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.AppGlobal.get_uint64": (
            FunctionOpMapping(
                "app_global_get",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.AppGlobal.get_ex_bytes": (
            FunctionOpMapping(
                "app_global_get_ex",
                stack_inputs=dict(
                    a=(wtypes.application_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(
                    wtypes.bytes_wtype,
                    wtypes.bool_wtype,
                ),
            ),
        ),
        "algopy.op.AppGlobal.get_ex_uint64": (
            FunctionOpMapping(
                "app_global_get_ex",
                stack_inputs=dict(
                    a=(wtypes.application_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.bool_wtype,
                ),
            ),
        ),
        "algopy.op.AppGlobal.delete": (
            FunctionOpMapping(
                "app_global_del",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.AppGlobal.put": (
            FunctionOpMapping(
                "app_global_put",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype, wtypes.uint64_wtype)
                ),
            ),
        ),
        "algopy.op.AppLocal.get_bytes": (
            FunctionOpMapping(
                "app_local_get",
                stack_inputs=dict(
                    a=(wtypes.account_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.AppLocal.get_uint64": (
            FunctionOpMapping(
                "app_local_get",
                stack_inputs=dict(
                    a=(wtypes.account_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                ),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.AppLocal.get_ex_bytes": (
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
        "algopy.op.AppLocal.get_ex_uint64": (
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
        "algopy.op.AppLocal.delete": (
            FunctionOpMapping(
                "app_local_del",
                stack_inputs=dict(
                    a=(wtypes.account_wtype, wtypes.uint64_wtype), b=(wtypes.bytes_wtype,)
                ),
            ),
        ),
        "algopy.op.AppLocal.put": (
            FunctionOpMapping(
                "app_local_put",
                stack_inputs=dict(
                    a=(wtypes.account_wtype, wtypes.uint64_wtype),
                    b=(wtypes.bytes_wtype,),
                    c=(wtypes.bytes_wtype, wtypes.uint64_wtype),
                ),
            ),
        ),
        "algopy.op.AppParamsGet.app_approval_program": (
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
        "algopy.op.AppParamsGet.app_clear_state_program": (
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
        "algopy.op.AppParamsGet.app_global_num_uint": (
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
        "algopy.op.AppParamsGet.app_global_num_byte_slice": (
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
        "algopy.op.AppParamsGet.app_local_num_uint": (
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
        "algopy.op.AppParamsGet.app_local_num_byte_slice": (
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
        "algopy.op.AppParamsGet.app_extra_program_pages": (
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
        "algopy.op.AppParamsGet.app_creator": (
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
        "algopy.op.AppParamsGet.app_address": (
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
        "algopy.op.AssetHoldingGet.asset_balance": (
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
        "algopy.op.AssetHoldingGet.asset_frozen": (
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
        "algopy.op.AssetParamsGet.asset_total": (
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
        "algopy.op.AssetParamsGet.asset_decimals": (
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
        "algopy.op.AssetParamsGet.asset_default_frozen": (
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
        "algopy.op.AssetParamsGet.asset_unit_name": (
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
        "algopy.op.AssetParamsGet.asset_name": (
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
        "algopy.op.AssetParamsGet.asset_url": (
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
        "algopy.op.AssetParamsGet.asset_metadata_hash": (
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
        "algopy.op.AssetParamsGet.asset_manager": (
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
        "algopy.op.AssetParamsGet.asset_reserve": (
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
        "algopy.op.AssetParamsGet.asset_freeze": (
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
        "algopy.op.AssetParamsGet.asset_clawback": (
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
        "algopy.op.AssetParamsGet.asset_creator": (
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
        "algopy.op.Block.blk_seed": (
            FunctionOpMapping(
                "block",
                immediates=dict(BlkSeed=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Block.blk_timestamp": (
            FunctionOpMapping(
                "block",
                immediates=dict(BlkTimestamp=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Box.create": (
            FunctionOpMapping(
                "box_create",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.Box.delete": (
            FunctionOpMapping(
                "box_del",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.Box.extract": (
            FunctionOpMapping(
                "box_extract",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.uint64_wtype,)
                ),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Box.get": (
            FunctionOpMapping(
                "box_get",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(
                    wtypes.bytes_wtype,
                    wtypes.bool_wtype,
                ),
            ),
        ),
        "algopy.op.Box.length": (
            FunctionOpMapping(
                "box_len",
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(
                    wtypes.uint64_wtype,
                    wtypes.bool_wtype,
                ),
            ),
        ),
        "algopy.op.Box.put": (
            FunctionOpMapping(
                "box_put",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.Box.replace": (
            FunctionOpMapping(
                "box_replace",
                stack_inputs=dict(
                    a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,), c=(wtypes.bytes_wtype,)
                ),
            ),
        ),
        "algopy.op.Box.resize": (
            FunctionOpMapping(
                "box_resize",
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.Box.splice": (
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
        "algopy.op.EllipticCurve.add": (
            FunctionOpMapping(
                "ec_add",
                immediates=dict(g=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.EllipticCurve.map_to": (
            FunctionOpMapping(
                "ec_map_to",
                immediates=dict(g=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.EllipticCurve.scalar_mul_multi": (
            FunctionOpMapping(
                "ec_multi_scalar_mul",
                immediates=dict(g=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.EllipticCurve.pairing_check": (
            FunctionOpMapping(
                "ec_pairing_check",
                immediates=dict(g=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.EllipticCurve.scalar_mul": (
            FunctionOpMapping(
                "ec_scalar_mul",
                immediates=dict(g=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.EllipticCurve.subgroup_check": (
            FunctionOpMapping(
                "ec_subgroup_check",
                immediates=dict(g=str),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.GITxn.sender": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Sender=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.fee": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Fee=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.first_valid": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, FirstValid=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.first_valid_time": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, FirstValidTime=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.last_valid": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, LastValid=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.note": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Note=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.lease": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Lease=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.receiver": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Receiver=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.amount": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Amount=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.close_remainder_to": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, CloseRemainderTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.vote_pk": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, VotePK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.selection_pk": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, SelectionPK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.vote_first": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, VoteFirst=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.vote_last": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, VoteLast=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.vote_key_dilution": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, VoteKeyDilution=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.type": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Type=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.type_enum": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, TypeEnum=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.xfer_asset": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, XferAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.GITxn.asset_amount": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, AssetAmount=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.asset_sender": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, AssetSender=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.asset_receiver": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, AssetReceiver=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.asset_close_to": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, AssetCloseTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.group_index": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, GroupIndex=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.tx_id": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, TxID=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.application_id": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ApplicationID=None),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "algopy.op.GITxn.on_completion": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, OnCompletion=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.application_args": (
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
        "algopy.op.GITxn.num_app_args": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, NumAppArgs=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.accounts": (
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
        "algopy.op.GITxn.num_accounts": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, NumAccounts=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.approval_program": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ApprovalProgram=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.clear_state_program": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ClearStateProgram=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.rekey_to": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, RekeyTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_total": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetTotal=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_decimals": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetDecimals=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_default_frozen": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetDefaultFrozen=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_unit_name": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetUnitName=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_name": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetName=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_url": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetURL=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_metadata_hash": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetMetadataHash=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_manager": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetManager=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_reserve": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetReserve=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_freeze": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetFreeze=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.config_asset_clawback": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ConfigAssetClawback=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.freeze_asset": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, FreezeAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.GITxn.freeze_asset_account": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, FreezeAssetAccount=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.GITxn.freeze_asset_frozen": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, FreezeAssetFrozen=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.GITxn.assets": (
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
        "algopy.op.GITxn.num_assets": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, NumAssets=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.applications": (
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
        "algopy.op.GITxn.num_applications": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, NumApplications=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.global_num_uint": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, GlobalNumUint=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.global_num_byte_slice": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, GlobalNumByteSlice=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.local_num_uint": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, LocalNumUint=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.local_num_byte_slice": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, LocalNumByteSlice=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.extra_program_pages": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, ExtraProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.nonparticipation": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, Nonparticipation=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.GITxn.logs": (
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
        "algopy.op.GITxn.num_logs": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, NumLogs=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.created_asset_id": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, CreatedAssetID=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.GITxn.created_application_id": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, CreatedApplicationID=None),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "algopy.op.GITxn.last_log": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, LastLog=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.state_proof_pk": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, StateProofPK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.GITxn.approval_program_pages": (
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
        "algopy.op.GITxn.num_approval_program_pages": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, NumApprovalProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GITxn.clear_state_program_pages": (
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
        "algopy.op.GITxn.num_clear_state_program_pages": (
            FunctionOpMapping(
                "gitxn",
                immediates=dict(t=int, NumClearStateProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.GTxn.sender": (
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
        "algopy.op.GTxn.fee": (
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
        "algopy.op.GTxn.first_valid": (
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
        "algopy.op.GTxn.first_valid_time": (
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
        "algopy.op.GTxn.last_valid": (
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
        "algopy.op.GTxn.note": (
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
        "algopy.op.GTxn.lease": (
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
        "algopy.op.GTxn.receiver": (
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
        "algopy.op.GTxn.amount": (
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
        "algopy.op.GTxn.close_remainder_to": (
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
        "algopy.op.GTxn.vote_pk": (
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
        "algopy.op.GTxn.selection_pk": (
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
        "algopy.op.GTxn.vote_first": (
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
        "algopy.op.GTxn.vote_last": (
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
        "algopy.op.GTxn.vote_key_dilution": (
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
        "algopy.op.GTxn.type": (
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
        "algopy.op.GTxn.type_enum": (
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
        "algopy.op.GTxn.xfer_asset": (
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
        "algopy.op.GTxn.asset_amount": (
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
        "algopy.op.GTxn.asset_sender": (
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
        "algopy.op.GTxn.asset_receiver": (
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
        "algopy.op.GTxn.asset_close_to": (
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
        "algopy.op.GTxn.group_index": (
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
        "algopy.op.GTxn.tx_id": (
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
        "algopy.op.GTxn.application_id": (
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
        "algopy.op.GTxn.on_completion": (
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
        "algopy.op.GTxn.application_args": (
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
        "algopy.op.GTxn.num_app_args": (
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
        "algopy.op.GTxn.accounts": (
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
        "algopy.op.GTxn.num_accounts": (
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
        "algopy.op.GTxn.approval_program": (
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
        "algopy.op.GTxn.clear_state_program": (
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
        "algopy.op.GTxn.rekey_to": (
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
        "algopy.op.GTxn.config_asset": (
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
        "algopy.op.GTxn.config_asset_total": (
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
        "algopy.op.GTxn.config_asset_decimals": (
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
        "algopy.op.GTxn.config_asset_default_frozen": (
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
        "algopy.op.GTxn.config_asset_unit_name": (
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
        "algopy.op.GTxn.config_asset_name": (
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
        "algopy.op.GTxn.config_asset_url": (
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
        "algopy.op.GTxn.config_asset_metadata_hash": (
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
        "algopy.op.GTxn.config_asset_manager": (
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
        "algopy.op.GTxn.config_asset_reserve": (
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
        "algopy.op.GTxn.config_asset_freeze": (
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
        "algopy.op.GTxn.config_asset_clawback": (
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
        "algopy.op.GTxn.freeze_asset": (
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
        "algopy.op.GTxn.freeze_asset_account": (
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
        "algopy.op.GTxn.freeze_asset_frozen": (
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
        "algopy.op.GTxn.assets": (
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
        "algopy.op.GTxn.num_assets": (
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
        "algopy.op.GTxn.applications": (
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
        "algopy.op.GTxn.num_applications": (
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
        "algopy.op.GTxn.global_num_uint": (
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
        "algopy.op.GTxn.global_num_byte_slice": (
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
        "algopy.op.GTxn.local_num_uint": (
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
        "algopy.op.GTxn.local_num_byte_slice": (
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
        "algopy.op.GTxn.extra_program_pages": (
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
        "algopy.op.GTxn.nonparticipation": (
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
        "algopy.op.GTxn.logs": (
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
        "algopy.op.GTxn.num_logs": (
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
        "algopy.op.GTxn.created_asset_id": (
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
        "algopy.op.GTxn.created_application_id": (
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
        "algopy.op.GTxn.last_log": (
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
        "algopy.op.GTxn.state_proof_pk": (
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
        "algopy.op.GTxn.approval_program_pages": (
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
        "algopy.op.GTxn.num_approval_program_pages": (
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
        "algopy.op.GTxn.clear_state_program_pages": (
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
        "algopy.op.GTxn.num_clear_state_program_pages": (
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
        "algopy.op.Global.min_txn_fee": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(MinTxnFee=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.min_balance": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(MinBalance=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.max_txn_life": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(MaxTxnLife=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.zero_address": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(ZeroAddress=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Global.group_size": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(GroupSize=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.logic_sig_version": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(LogicSigVersion=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.round": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(Round=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.latest_timestamp": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(LatestTimestamp=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.current_application_id": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(CurrentApplicationID=None),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "algopy.op.Global.creator_address": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(CreatorAddress=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Global.current_application_address": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(CurrentApplicationAddress=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Global.group_id": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(GroupID=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Global.opcode_budget": (
            FunctionOpMapping(
                "global",
                immediates=dict(OpcodeBudget=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.caller_application_id": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(CallerApplicationID=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.caller_application_address": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(CallerApplicationAddress=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Global.asset_create_min_balance": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(AssetCreateMinBalance=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.asset_opt_in_min_balance": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(AssetOptInMinBalance=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Global.genesis_hash": (
            FunctionOpMapping(
                "global",
                is_property=True,
                immediates=dict(GenesisHash=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.sender": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Sender=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.fee": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Fee=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.first_valid": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(FirstValid=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.first_valid_time": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(FirstValidTime=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.last_valid": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(LastValid=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.note": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Note=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.lease": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Lease=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.receiver": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Receiver=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.amount": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Amount=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.close_remainder_to": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(CloseRemainderTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.vote_pk": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(VotePK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.selection_pk": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(SelectionPK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.vote_first": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(VoteFirst=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.vote_last": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(VoteLast=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.vote_key_dilution": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(VoteKeyDilution=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.type": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Type=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.type_enum": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(TypeEnum=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.xfer_asset": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(XferAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.ITxn.asset_amount": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(AssetAmount=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.asset_sender": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(AssetSender=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.asset_receiver": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(AssetReceiver=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.asset_close_to": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(AssetCloseTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.group_index": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(GroupIndex=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.tx_id": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(TxID=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.application_id": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ApplicationID=None),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "algopy.op.ITxn.on_completion": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(OnCompletion=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.application_args": (
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
        "algopy.op.ITxn.num_app_args": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(NumAppArgs=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.accounts": (
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
        "algopy.op.ITxn.num_accounts": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(NumAccounts=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.approval_program": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ApprovalProgram=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.clear_state_program": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ClearStateProgram=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.rekey_to": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(RekeyTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_total": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetTotal=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_decimals": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetDecimals=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_default_frozen": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetDefaultFrozen=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_unit_name": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetUnitName=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_name": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetName=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_url": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetURL=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_metadata_hash": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetMetadataHash=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_manager": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetManager=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_reserve": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetReserve=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_freeze": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetFreeze=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.config_asset_clawback": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ConfigAssetClawback=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.freeze_asset": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(FreezeAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.ITxn.freeze_asset_account": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(FreezeAssetAccount=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.ITxn.freeze_asset_frozen": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(FreezeAssetFrozen=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.ITxn.assets": (
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
        "algopy.op.ITxn.num_assets": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(NumAssets=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.applications": (
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
        "algopy.op.ITxn.num_applications": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(NumApplications=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.global_num_uint": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(GlobalNumUint=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.global_num_byte_slice": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(GlobalNumByteSlice=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.local_num_uint": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(LocalNumUint=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.local_num_byte_slice": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(LocalNumByteSlice=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.extra_program_pages": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(ExtraProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.nonparticipation": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(Nonparticipation=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.ITxn.logs": (
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
        "algopy.op.ITxn.num_logs": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(NumLogs=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.created_asset_id": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(CreatedAssetID=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.ITxn.created_application_id": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(CreatedApplicationID=None),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "algopy.op.ITxn.last_log": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(LastLog=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.state_proof_pk": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(StateProofPK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.ITxn.approval_program_pages": (
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
        "algopy.op.ITxn.num_approval_program_pages": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(NumApprovalProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxn.clear_state_program_pages": (
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
        "algopy.op.ITxn.num_clear_state_program_pages": (
            FunctionOpMapping(
                "itxn",
                immediates=dict(NumClearStateProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.ITxnCreate.begin": (
            FunctionOpMapping(
                "itxn_begin",
            ),
        ),
        "algopy.op.ITxnCreate.next": (
            FunctionOpMapping(
                "itxn_next",
            ),
        ),
        "algopy.op.ITxnCreate.submit": (
            FunctionOpMapping(
                "itxn_submit",
            ),
        ),
        "algopy.op.ITxnCreate.set_sender": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Sender=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_fee": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Fee=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_note": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Note=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_receiver": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Receiver=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_amount": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Amount=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_close_remainder_to": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(CloseRemainderTo=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_vote_pk": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(VotePK=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_selection_pk": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(SelectionPK=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_vote_first": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(VoteFirst=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_vote_last": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(VoteLast=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_vote_key_dilution": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(VoteKeyDilution=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_type": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Type=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_type_enum": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(TypeEnum=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_xfer_asset": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(XferAsset=None),
                stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
            ),
        ),
        "algopy.op.ITxnCreate.set_asset_amount": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(AssetAmount=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_asset_sender": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(AssetSender=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_asset_receiver": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(AssetReceiver=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_asset_close_to": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(AssetCloseTo=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_application_id": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ApplicationID=None),
                stack_inputs=dict(a=(wtypes.application_wtype, wtypes.uint64_wtype)),
            ),
        ),
        "algopy.op.ITxnCreate.set_on_completion": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(OnCompletion=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_application_args": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ApplicationArgs=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_accounts": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Accounts=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_approval_program": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ApprovalProgram=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_clear_state_program": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ClearStateProgram=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_rekey_to": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(RekeyTo=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAsset=None),
                stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_total": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetTotal=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_decimals": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetDecimals=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_default_frozen": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetDefaultFrozen=None),
                stack_inputs=dict(a=(wtypes.bool_wtype, wtypes.uint64_wtype)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_unit_name": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetUnitName=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_name": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetName=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_url": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetURL=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_metadata_hash": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetMetadataHash=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_manager": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetManager=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_reserve": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetReserve=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_freeze": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetFreeze=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_config_asset_clawback": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ConfigAssetClawback=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_freeze_asset": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(FreezeAsset=None),
                stack_inputs=dict(a=(wtypes.asset_wtype, wtypes.uint64_wtype)),
            ),
        ),
        "algopy.op.ITxnCreate.set_freeze_asset_account": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(FreezeAssetAccount=None),
                stack_inputs=dict(a=(wtypes.account_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_freeze_asset_frozen": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(FreezeAssetFrozen=None),
                stack_inputs=dict(a=(wtypes.bool_wtype, wtypes.uint64_wtype)),
            ),
        ),
        "algopy.op.ITxnCreate.set_assets": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Assets=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_applications": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Applications=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_global_num_uint": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(GlobalNumUint=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_global_num_byte_slice": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(GlobalNumByteSlice=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_local_num_uint": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(LocalNumUint=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_local_num_byte_slice": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(LocalNumByteSlice=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_extra_program_pages": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ExtraProgramPages=None),
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_nonparticipation": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(Nonparticipation=None),
                stack_inputs=dict(a=(wtypes.bool_wtype, wtypes.uint64_wtype)),
            ),
        ),
        "algopy.op.ITxnCreate.set_state_proof_pk": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(StateProofPK=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_approval_program_pages": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ApprovalProgramPages=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.ITxnCreate.set_clear_state_program_pages": (
            FunctionOpMapping(
                "itxn_field",
                immediates=dict(ClearStateProgramPages=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,)),
            ),
        ),
        "algopy.op.JsonRef.json_string": (
            FunctionOpMapping(
                "json_ref",
                immediates=dict(JSONString=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.JsonRef.json_uint64": (
            FunctionOpMapping(
                "json_ref",
                immediates=dict(JSONUint64=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.JsonRef.json_object": (
            FunctionOpMapping(
                "json_ref",
                immediates=dict(JSONObject=None),
                stack_inputs=dict(a=(wtypes.bytes_wtype,), b=(wtypes.bytes_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Scratch.load_bytes": (
            FunctionOpMapping(
                "loads",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Scratch.load_uint64": (
            FunctionOpMapping(
                "loads",
                stack_inputs=dict(a=(wtypes.uint64_wtype,)),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Scratch.store": (
            FunctionOpMapping(
                "stores",
                stack_inputs=dict(
                    a=(wtypes.uint64_wtype,), b=(wtypes.bytes_wtype, wtypes.uint64_wtype)
                ),
            ),
        ),
        "algopy.op.Txn.sender": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Sender=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.fee": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Fee=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.first_valid": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(FirstValid=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.first_valid_time": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(FirstValidTime=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.last_valid": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(LastValid=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.note": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Note=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.lease": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Lease=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.receiver": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Receiver=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.amount": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Amount=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.close_remainder_to": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(CloseRemainderTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.vote_pk": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(VotePK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.selection_pk": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(SelectionPK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.vote_first": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(VoteFirst=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.vote_last": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(VoteLast=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.vote_key_dilution": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(VoteKeyDilution=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.type": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Type=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.type_enum": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(TypeEnum=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.xfer_asset": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(XferAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.Txn.asset_amount": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(AssetAmount=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.asset_sender": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(AssetSender=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.asset_receiver": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(AssetReceiver=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.asset_close_to": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(AssetCloseTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.group_index": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(GroupIndex=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.tx_id": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(TxID=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.application_id": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ApplicationID=None),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "algopy.op.Txn.on_completion": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(OnCompletion=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.application_args": (
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
        "algopy.op.Txn.num_app_args": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(NumAppArgs=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.accounts": (
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
        "algopy.op.Txn.num_accounts": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(NumAccounts=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.approval_program": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ApprovalProgram=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.clear_state_program": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ClearStateProgram=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.rekey_to": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(RekeyTo=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_total": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetTotal=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_decimals": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetDecimals=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_default_frozen": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetDefaultFrozen=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_unit_name": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetUnitName=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_name": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetName=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_url": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetURL=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_metadata_hash": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetMetadataHash=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_manager": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetManager=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_reserve": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetReserve=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_freeze": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetFreeze=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.config_asset_clawback": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ConfigAssetClawback=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.freeze_asset": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(FreezeAsset=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.Txn.freeze_asset_account": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(FreezeAssetAccount=None),
                stack_outputs=(wtypes.account_wtype,),
            ),
        ),
        "algopy.op.Txn.freeze_asset_frozen": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(FreezeAssetFrozen=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.Txn.assets": (
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
        "algopy.op.Txn.num_assets": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(NumAssets=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.applications": (
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
        "algopy.op.Txn.num_applications": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(NumApplications=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.global_num_uint": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(GlobalNumUint=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.global_num_byte_slice": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(GlobalNumByteSlice=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.local_num_uint": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(LocalNumUint=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.local_num_byte_slice": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(LocalNumByteSlice=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.extra_program_pages": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(ExtraProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.nonparticipation": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(Nonparticipation=None),
                stack_outputs=(wtypes.bool_wtype,),
            ),
        ),
        "algopy.op.Txn.logs": (
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
        "algopy.op.Txn.num_logs": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(NumLogs=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.created_asset_id": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(CreatedAssetID=None),
                stack_outputs=(wtypes.asset_wtype,),
            ),
        ),
        "algopy.op.Txn.created_application_id": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(CreatedApplicationID=None),
                stack_outputs=(wtypes.application_wtype,),
            ),
        ),
        "algopy.op.Txn.last_log": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(LastLog=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.state_proof_pk": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(StateProofPK=None),
                stack_outputs=(wtypes.bytes_wtype,),
            ),
        ),
        "algopy.op.Txn.approval_program_pages": (
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
        "algopy.op.Txn.num_approval_program_pages": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(NumApprovalProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
        "algopy.op.Txn.clear_state_program_pages": (
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
        "algopy.op.Txn.num_clear_state_program_pages": (
            FunctionOpMapping(
                "txn",
                is_property=True,
                immediates=dict(NumClearStateProgramPages=None),
                stack_outputs=(wtypes.uint64_wtype,),
            ),
        ),
    }
)
