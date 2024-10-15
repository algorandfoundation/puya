import base64
import json
import typing
from collections.abc import Collection, Mapping, Sequence

from puya import log
from puya.errors import InternalError
from puya.models import (
    ARC4ABIMethod,
    ARC4BareMethod,
    ARC4CreateOption,
    ARC4MethodConfig,
    ARC4Struct,
    ContractMetaData,
    ContractState,
    OnCompletionAction,
    StateTotals,
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


def _encode_schema_declaration(state: ContractState) -> JSONDict:
    return {
        "type": state.storage_type.name,
        "key": state.key_or_prefix.decode("utf-8"),  # TODO: support not utf8 keys?
        "descr": state.description,
    }


def _encode_state_declaration(state: StateTotals) -> JSONDict:
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


def _encode_schema(state: Collection[ContractState]) -> JSONDict:
    return {
        "declared": {
            s.name: _encode_schema_declaration(s) for s in sorted(state, key=lambda s: s.name)
        },
        "reserved": {},  # TODO?
    }


def _encode_call_config(config: ARC4MethodConfig) -> JSONDict:
    match config.create:
        case ARC4CreateOption.require:
            call_config = "CREATE"
        case ARC4CreateOption.allow:
            call_config = "ALL"
        case ARC4CreateOption.disallow:
            call_config = "CALL"
        case never:
            typing.assert_never(never)
    return {OCA_ARC32_MAPPING[oca]: call_config for oca in config.allowed_completion_types}


def _encode_bare_method_configs(methods: list[ARC4BareMethod]) -> JSONDict:
    result: dict[str, JSONValue] = {}
    for method in methods:
        result.update(**_encode_call_config(method.config))
    return result


def _get_signature(method: ARC4ABIMethod) -> str:
    return f"{method.config.name}({','.join(m.type_ for m in method.args)}){method.returns.type_}"


def _encode_default_arg(
    metadata: ContractMetaData, source: str, loc: SourceLocation | None
) -> JSONDict:
    if state := metadata.global_state.get(source):
        return {
            "source": "global-state",
            # TODO: handle non utf-8 bytes
            "data": state.key_or_prefix.decode("utf-8"),
        }
    if state := metadata.local_state.get(source):
        return {
            "source": "local-state",
            "data": state.key_or_prefix.decode("utf-8"),
        }
    for method in metadata.arc4_methods:
        if isinstance(method, ARC4ABIMethod) and method.name == source:
            return {
                "source": "abi-method",
                "data": _encode_abi_method(method),
            }
    # TODO: constants
    raise InternalError(f"Cannot find source '{source}' on {metadata.ref}", loc)


def _encode_arc32_method_hint(metadata: ContractMetaData, method: ARC4ABIMethod) -> JSONDict:
    structs = {a.name: metadata.structs[a.struct] for a in method.args if a.struct}
    if method.returns.struct:
        structs["output"] = metadata.structs[method.returns.struct]
    return {
        # deprecated by ARC-22
        "read_only": True if method.config.readonly else None,
        "default_arguments": (
            {
                parameter: _encode_default_arg(metadata, source, method.config.source_location)
                for parameter, source in method.config.default_args.items()
            }
            if method.config.default_args
            else None
        ),
        "call_config": _encode_call_config(method.config),
        "structs": _encode_arc32_method_structs(structs),
    }


def _encode_arc32_method_structs(structs: Mapping[str, ARC4Struct]) -> JSONDict | None:
    if len(structs):
        return {
            struct_purpose: {
                "name": struct_def.name,
                "elements": [[f.name, f.type] for f in struct_def.fields],
            }
            for struct_purpose, struct_def in structs.items()
        }
    return None


def _encode_arc32_hints(metadata: ContractMetaData, methods: list[ARC4ABIMethod]) -> JSONDict:
    return {
        _get_signature(method): _encode_arc32_method_hint(metadata, method) for method in methods
    }


def _encode_abi_method(method: ARC4ABIMethod) -> JSONDict:
    return {
        "name": method.config.name,
        "args": [
            {
                "type": arg.type_,
                "name": arg.name,
                "desc": arg.desc,
            }
            for arg in method.args
        ],
        "readonly": method.config.readonly,  # ARC-22
        "returns": {
            "type": method.returns.type_,
            "desc": method.returns.desc,
        },
        "desc": method.desc,
    }


def _encode_arc4_contract(
    name: str, desc: str | None, methods: Sequence[ARC4ABIMethod]
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
    approval_program: str, clear_program: str, metadata: ContractMetaData
) -> str:
    bare_methods = [m for m in metadata.arc4_methods if isinstance(m, ARC4BareMethod)]
    abi_methods = [m for m in metadata.arc4_methods if isinstance(m, ARC4ABIMethod)]
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
