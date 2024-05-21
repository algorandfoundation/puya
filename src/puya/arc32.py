import base64
import itertools
import json
import textwrap
import typing
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path

from puya import log
from puya.arc4_util import arc4_to_pytype
from puya.awst_build import constants
from puya.errors import InternalError
from puya.models import (
    ARC4Method,
    ARC4MethodArg,
    ARC4MethodConfig,
    ARC32StructDef,
    CompiledContract,
    ContractState,
    OnCompletionAction,
    StateTotals,
)
from puya.parse import SourceLocation
from puya.utils import make_path_relative_to_cwd, unique

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
_AUTO_GENERATED_COMMENT = "# This file is auto-generated, do not modify"
_INDENT = " " * 4

logger = log.get_logger(__name__)


def _encode_source(teal_text: str) -> str:
    return base64.b64encode(teal_text.encode()).decode("utf-8")


def _encode_schema_declaration(state: ContractState) -> JSONDict:
    return {
        "type": state.storage_type.name,
        "key": state.key.decode("utf-8"),  # TODO: support not utf8 keys?
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


def _encode_default_arg(
    contract: CompiledContract, source: str, loc: SourceLocation | None
) -> JSONDict:
    if state := contract.metadata.global_state.get(source):
        return {
            "source": "global-state",
            # TODO: handle non utf-8 bytes
            "data": state.key.decode("utf-8"),
        }
    if state := contract.metadata.local_state.get(source):
        return {
            "source": "local-state",
            "data": state.key.decode("utf-8"),
        }
    for method in contract.metadata.arc4_methods:
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
        "default_arguments": (
            {
                parameter: _encode_default_arg(contract, source, method.config.source_location)
                for parameter, source in method.config.default_args.items()
            }
            if method.config.default_args
            else None
        ),
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
            for struct_purpose, struct_def in method.config.structs.items()
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
    bare_methods = [m for m in metadata.arc4_methods if m.config.is_bare]
    arc4_methods = [m for m in metadata.arc4_methods if not m.config.is_bare]
    app_spec = {
        "hints": _encode_arc32_hints(contract, arc4_methods),
        "source": {
            "approval": _encode_source("\n".join(contract.approval_program)),
            "clear": _encode_source("\n".join(contract.clear_program)),
        },
        "state": _encode_state_declaration(contract.metadata.state_totals),
        "schema": {
            "global": _encode_schema(metadata.global_state.values()),
            "local": _encode_schema(metadata.local_state.values()),
        },
        "contract": _encode_arc4_contract(metadata.name, metadata.description, arc4_methods),
        "bare_call_config": _encode_bare_method_configs(bare_methods),
    }
    return json.dumps(_filter_none(app_spec), indent=4)


def write_arc32_client(name: str, methods: Sequence[ARC4Method], out_dir: Path) -> None:
    stub_path = out_dir / f"client_{name}.py"
    if _can_overwrite_auto_generated_file(stub_path):
        logger.info(f"Writing {make_path_relative_to_cwd(stub_path)}")
        stub_text = _create_arc32_stub(name, methods)
        stub_path.write_text(stub_text)
    else:
        logger.error(
            f"Not outputting {make_path_relative_to_cwd(stub_path)} "
            "since content does not appear to be auto-generated"
        )


def _can_overwrite_auto_generated_file(path: Path) -> bool:
    return not path.exists() or path.read_text().startswith(_AUTO_GENERATED_COMMENT)


def _create_arc32_stub(name: str, methods: Sequence[ARC4Method]) -> str:
    return "\n".join(
        (
            _AUTO_GENERATED_COMMENT,
            "# flake8: noqa",  # this works for flake8 and ruff
            "# fmt: off",  # disable formatting"
            "import typing",
            "",
            "import algopy",
            "",
            *itertools.chain(
                *(
                    _abi_struct_to_class(s)
                    for s in unique(s for m in methods for s in m.config.structs.values())
                )
            ),
            "",
            f"class {name}(algopy.arc4.ARC4Client, typing.Protocol):",
            *(
                [_indent(["pass"]), ""]
                if not any(True for m in methods if not m.config.is_bare)
                else []
            ),
            *(_abi_method_to_signature(m) for m in methods if not m.config.is_bare),
        )
    )


def _abi_struct_to_class(s: ARC32StructDef) -> Iterable[str]:
    return (
        f"class {s.name}(algopy.arc4.Struct):",
        _indent(
            f"{name}: {_arc4_type_to_algopy_cls(elem_type)}" for name, elem_type in s.elements
        ),
    )


def _abi_method_to_signature(m: ARC4Method) -> str:
    structs = dict(m.config.structs)
    try:
        output_struct = structs["output"]
    except KeyError:
        return_type = _arc4_type_to_algopy_cls(m.returns.type_)
    else:
        return_type = output_struct.name

    return _indent(
        (
            _arc4_method_to_decorator(m),
            f"def {m.name}(",
            _indent(
                (
                    "self,",
                    *(_abi_arg(arg, structs.get(arg.name)) for arg in m.args),
                )
            ),
            f") -> {return_type}: ...",
            "",
        )
    )


def _abi_arg(arg: ARC4MethodArg, struct: ARC32StructDef | None) -> str:
    python_type = struct.name if struct else _arc4_type_to_algopy_cls(arg.type_)
    return f"{arg.name}: {python_type},"


def _arc4_type_to_algopy_cls(typ: str) -> str:
    return str(arc4_to_pytype(typ))


def _arc4_method_to_decorator(method: ARC4Method) -> str:
    config = method.config
    abimethod_args = dict[str, object]()
    if config.name and config.name != method.name:
        abimethod_args["name"] = config.name
    if config.readonly:
        abimethod_args["readonly"] = True
    if config.default_args:
        abimethod_args["default_args"] = dict(config.default_args)
    if config.allowed_completion_types != (OnCompletionAction.NoOp,):
        abimethod_args["allow_actions"] = [oca.name for oca in config.allowed_completion_types]
    if config.allow_create:
        abimethod_args["create"] = "allow"
    elif config.require_create:
        abimethod_args["create"] = "require"
    kwargs = ", ".join(f"{name}={value!r}" for name, value in abimethod_args.items())
    decorator = f"@{constants.ABIMETHOD_DECORATOR_ALIAS}"
    if kwargs:
        decorator += f"({kwargs})"
    return decorator


def _indent(lines: Iterable[str] | str) -> str:
    if not isinstance(lines, str):
        lines = "\n".join(lines)
    return textwrap.indent(lines, _INDENT)
