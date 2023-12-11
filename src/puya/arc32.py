import base64
import json
import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

from puya.avm_type import AVMType
from puya.codegen.emitprogram import CompiledContract
from puya.errors import InternalError
from puya.metadata import ARC4Method, ARC4MethodConfig, ContractState, OnCompletionAction
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


def _encode_source(teal_text: str) -> str:
    return base64.b64encode(teal_text.encode()).decode("utf-8")


def _encode_state_schema(state: Sequence[ContractState]) -> JSONDict:
    return {
        "num_byte_slices": sum(1 for s in state if s.storage_type is AVMType.bytes),
        "num_uints": sum(1 for s in state if s.storage_type is AVMType.uint64),
    }


def _encode_schema_declaration(state: ContractState) -> JSONDict:
    return {
        "type": state.storage_type.name,
        "key": state.key.decode("utf-8"),  # TODO: support not utf8 keys?
        "descr": state.description,
    }


def _encode_schema(state: Sequence[ContractState]) -> JSONDict:
    return {
        "declared": {
            s.name: _encode_schema_declaration(s) for s in sorted(state, key=lambda s: s.name)
        },
        "reserved": {},  # TODO?
    }


def _encode_call_config(config: ARC4MethodConfig) -> JSONDict:
    if config.require_create:
        call_config = "CREATE"
    elif config.allow_create:
        call_config = "ALL"
    else:
        call_config = "CALL"
    return {OCA_ARC32_MAPPING[oca]: call_config for oca in config.allowed_completion_types}


def _encode_bare_method_configs(methods: list[ARC4Method]) -> JSONDict:
    result: dict[str, JSONValue] = {}
    for method in methods:
        result.update(**_encode_call_config(method.config))
    return result


def _get_signature(method: ARC4Method) -> str:
    return f"{method.config.name}({','.join(m.type_ for m in method.args)}){method.returns.type_}"


def _encode_default_arg(contract: CompiledContract, source: str, loc: SourceLocation) -> JSONDict:
    for state in contract.metadata.global_state:
        if state.name == source:
            return {
                "source": "global-state",
                # TODO: handle non utf-8 bytes
                "data": state.key.decode("utf-8"),
            }
    for state in contract.metadata.local_state:
        if state.name == source:
            return {
                "source": "local-state",
                "data": state.key.decode("utf-8"),
            }
    for method in contract.metadata.methods:
        if method.name == source:
            return {
                "source": "abi-method",
                "data": _encode_arc4_method(method),
            }
    # TODO: constants
    raise InternalError(f"Cannot find source '{source}' on {contract.metadata.full_name}", loc)


def _encode_arc32_method_hint(contract: CompiledContract, method: ARC4Method) -> JSONDict:
    return {
        # deprecated by ARC-22
        "read_only": True if method.config.readonly else None,
        "default_arguments": {
            default_arg.parameter: _encode_default_arg(
                contract, default_arg.source, method.config.source_location
            )
            for default_arg in method.config.default_args
        }
        if method.config.default_args
        else None,
        "call_config": _encode_call_config(method.config),
        "structs": _encode_arc32_method_structs(method),
    }


def _encode_arc32_method_structs(method: ARC4Method) -> JSONDict | None:
    if len(method.config.structs):
        return {
            struct_purpose: {
                "name": struct_def.name,
                "elements": struct_def.elements,
            }
            for struct_purpose, struct_def in method.config.structs
        }
    return None


def _encode_arc32_hints(contract: CompiledContract, methods: list[ARC4Method]) -> JSONDict:
    return {
        _get_signature(method): _encode_arc32_method_hint(contract, method) for method in methods
    }


def _encode_arc4_method(method: ARC4Method) -> JSONDict:
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
        # "readonly": method.config.readonly,  # ARC-22
        "returns": {
            "type": method.returns.type_,
            "desc": method.returns.desc,
        },
        "desc": method.desc,
    }


def _encode_arc4_contract(name: str, desc: str | None, methods: Sequence[ARC4Method]) -> JSONDict:
    return {
        "name": name,
        "desc": desc,
        "methods": [_encode_arc4_method(m) for m in methods],
        "networks": {},
    }


def _filter_none(value: JSONDict) -> JSONValue:
    if isinstance(value, dict):
        return {k: _filter_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return list(map(_filter_none, value))
    return value


def create_arc32_json(contract: CompiledContract) -> str:
    metadata = contract.metadata
    bare_methods = [m for m in metadata.methods if m.config.is_bare]
    arc4_methods = [m for m in metadata.methods if not m.config.is_bare]
    app_spec = {
        "hints": _encode_arc32_hints(contract, arc4_methods),
        "source": {
            "approval": _encode_source("\n".join(contract.approval_program.src)),
            "clear": _encode_source("\n".join(contract.clear_program.src)),
        },
        "state": {
            "global": _encode_state_schema(metadata.global_state),
            "local": _encode_state_schema(metadata.local_state),
        },
        "schema": {
            "global": _encode_schema(metadata.global_state),
            "local": _encode_schema(metadata.local_state),
        },
        "contract": _encode_arc4_contract(
            metadata.name_override or metadata.class_name, metadata.description, arc4_methods
        ),
        "bare_call_config": _encode_bare_method_configs(bare_methods),
    }
    return json.dumps(_filter_none(app_spec), indent=4)


def write_arc32(path: Path, contract: CompiledContract) -> None:
    path.write_text(create_arc32_json(contract))
