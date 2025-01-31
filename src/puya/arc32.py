import base64
import json
import typing
from collections.abc import Collection, Mapping, Sequence

from puya import (
    artifact_metadata as md,
    log,
)
from puya.avm import OnCompletionAction
from puya.awst.nodes import (
    AppStorageKind,
    ARC4CreateOption,
)
from puya.parse import SourceLocation

OCA_ARC32_MAPPING = {
    OnCompletionAction.NoOp: "no_op",
    OnCompletionAction.OptIn: "opt_in",
    OnCompletionAction.CloseOut: "close_out",
    OnCompletionAction.ClearState: "clear_state",
    OnCompletionAction.UpdateApplication: "update_application",
    OnCompletionAction.DeleteApplication: "delete_application",
}

JSONValue: typing.TypeAlias = "str | int | float | bool | None | Sequence[JSONValue] | JSONDict"
JSONDict: typing.TypeAlias = Mapping[str, "JSONValue"]

logger = log.get_logger(__name__)


def _encode_source(teal_text: str) -> str:
    return base64.b64encode(teal_text.encode()).decode("utf-8")


def _encode_schema_declaration(state: md.ContractState) -> JSONDict:
    return {
        "type": state.storage_type.name,
        "key": state.key_or_prefix.decode("utf-8"),  # TODO: support not utf8 keys?
        "descr": state.description,
    }


def _encode_state_declaration(state: md.StateTotals) -> JSONDict:
    return {
        "global": {
            "num_byte_slices": state.global_bytes,
            "num_uints": state.global_uints,
        },
        "local": {
            "num_byte_slices": state.local_bytes,
            "num_uints": state.local_uints,
        },
    }


def _encode_schema(state: Collection[md.ContractState]) -> JSONDict:
    return {
        "declared": {
            s.name: _encode_schema_declaration(s) for s in sorted(state, key=lambda s: s.name)
        },
        "reserved": {},  # TODO?
    }


def _encode_call_config(method: md.ARC4Method) -> JSONDict:
    match method.create:
        case ARC4CreateOption.require:
            call_config = "CREATE"
        case ARC4CreateOption.allow:
            call_config = "ALL"
        case ARC4CreateOption.disallow:
            call_config = "CALL"
        case never:
            typing.assert_never(never)
    return {OCA_ARC32_MAPPING[oca]: call_config for oca in method.allowed_completion_types}


def _encode_bare_method_configs(methods: Sequence[md.ARC4BareMethod]) -> JSONDict:
    result: dict[str, JSONValue] = {}
    for method in methods:
        result.update(**_encode_call_config(method))
    return result


def _get_signature(method: md.ARC4ABIMethod) -> str:
    return f"{method.name}({','.join(m.type_ for m in method.args)}){method.returns.type_}"


def _encode_default_arg(arg: md.ARC4MethodArg, loc: SourceLocation | None) -> JSONDict | None:
    match arg.client_default:
        case None:
            return None
        case md.MethodArgDefaultConstant(data=constant_data, type_=constant_arc4_type):
            if constant_arc4_type == "string":
                string = constant_data[2:].decode("utf8")
                return {"source": "constant", "data": string}
            elif constant_arc4_type.startswith("uint"):
                number = int.from_bytes(constant_data, signed=False)
                return {"source": "constant", "data": number}
            else:
                logger.warning(
                    f"parameter {arg.name!r} has unsupported default constant type for ARC-32",
                    location=loc,
                )
                return None
        case md.MethodArgDefaultFromMethod(
            name=method_name, return_type=return_type, readonly=readonly
        ):
            return {
                "source": "abi-method",
                "data": {
                    "name": method_name,
                    "args": [],
                    "readonly": readonly,  # ARC-22
                    "returns": {"type": return_type},
                },
            }
        case md.MethodArgDefaultFromState(kind=kind, key=key):
            match kind:
                case AppStorageKind.app_global:
                    source_name = "global-state"
                case AppStorageKind.account_local:
                    source_name = "local-state"
                case AppStorageKind.box:
                    logger.error(
                        "default argument from box storage are not supported by ARC-32",
                        location=loc,
                    )
                case unexpected:
                    typing.assert_never(unexpected)
            return {
                "source": source_name,
                # TODO: handle non utf-8 bytes
                "data": key.decode("utf-8"),
            }


def _encode_arc32_method_hint(metadata: md.ContractMetaData, method: md.ARC4ABIMethod) -> JSONDict:
    structs = {a.name: metadata.structs[a.struct] for a in method.args if a.struct}
    if method.returns.struct:
        structs["output"] = metadata.structs[method.returns.struct]
    default_arguments = {
        arg.name: default
        for arg in method.args
        if (default := _encode_default_arg(arg, method.config_location)) is not None
    }
    return {
        # deprecated by ARC-22
        "read_only": True if method.readonly else None,
        "default_arguments": default_arguments or None,
        "call_config": _encode_call_config(method),
        "structs": _encode_arc32_method_structs(structs),
    }


def _encode_arc32_method_structs(structs: Mapping[str, md.ARC4Struct]) -> JSONDict | None:
    if len(structs):
        return {
            struct_purpose: {
                "name": struct_def.name,
                "elements": [[f.name, f.type] for f in struct_def.fields],
            }
            for struct_purpose, struct_def in structs.items()
        }
    return None


def _encode_arc32_hints(
    metadata: md.ContractMetaData, methods: list[md.ARC4ABIMethod]
) -> JSONDict:
    return {
        _get_signature(method): _encode_arc32_method_hint(metadata, method) for method in methods
    }


def _encode_abi_method(method: md.ARC4ABIMethod) -> JSONDict:
    return {
        "name": method.name,
        "args": [
            {
                "type": arg.type_,
                "name": arg.name,
                "desc": arg.desc,
            }
            for arg in method.args
        ],
        "readonly": method.readonly,  # ARC-22
        "returns": {
            "type": method.returns.type_,
            "desc": method.returns.desc,
        },
        "desc": method.desc,
    }


def _encode_arc4_contract(
    name: str, desc: str | None, methods: Sequence[md.ARC4ABIMethod]
) -> JSONDict:
    return {
        "name": name,
        "desc": desc,
        "methods": [_encode_abi_method(m) for m in methods],
        "networks": {},
    }


def _filter_none(value: JSONDict) -> JSONValue:
    if isinstance(value, dict):
        return {k: _filter_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return list(map(_filter_none, value))
    return value


def create_arc32_json(
    approval_program: str, clear_program: str, metadata: md.ContractMetaData
) -> str:
    bare_methods = [m for m in metadata.arc4_methods if isinstance(m, md.ARC4BareMethod)]
    abi_methods = [m for m in metadata.arc4_methods if isinstance(m, md.ARC4ABIMethod)]
    app_spec = {
        "hints": _encode_arc32_hints(metadata, abi_methods),
        "source": {
            "approval": _encode_source(approval_program),
            "clear": _encode_source(clear_program),
        },
        "state": _encode_state_declaration(metadata.state_totals),
        "schema": {
            "global": _encode_schema(metadata.global_state.values()),
            "local": _encode_schema(metadata.local_state.values()),
        },
        "contract": _encode_arc4_contract(metadata.name, metadata.description, abi_methods),
        "bare_call_config": _encode_bare_method_configs(bare_methods),
    }
    return json.dumps(_filter_none(app_spec), indent=4)
