import argparse
import json
import typing
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import log
from puya.arc32 import OCA_ARC32_MAPPING
from puya.awst_build.arc32_client_gen import write_arc32_client
from puya.errors import PuyaError
from puya.models import (
    ARC4ABIMethod,
    ARC4ABIMethodConfig,
    ARC4CreateOption,
    ARC4Method,
    ARC4MethodArg,
    ARC4Returns,
    ARC32StructDef,
    OnCompletionAction,
)

logger = log.get_logger(__name__)
ARC32_OCA_MAPPING = {v: k for k, v in OCA_ARC32_MAPPING.items()}


@attrs.define(kw_only=True)
class PuyaGenOptions:
    paths: Sequence[Path] = attrs.field(default=(), repr=lambda p: str(list(map(str, p))))
    log_level: log.LogLevel = log.LogLevel.info


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="puyapy-clientgen",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Output algopy contract client for typed ARC4 ABI calls from an "
        "ARC32 application.json spec",
    )
    parser.add_argument("paths", type=Path, nargs="+", metavar="PATH")
    options = PuyaGenOptions()
    parser.parse_args(namespace=options)
    log.configure_logging(min_log_level=options.log_level)
    output_stubs(options.paths)


def output_stubs(paths: Sequence[Path]) -> None:
    try:
        app_spec_paths = resolve_app_specs(paths)
        for app_spec_path in app_spec_paths:
            name, methods = parse_app_spec_methods(app_spec_path.read_text("utf8"))
            write_arc32_client(name, methods, app_spec_path.parent)
    except PuyaError as ex:
        logger.error(str(ex))  # noqa: TRY400


def resolve_app_specs(paths: Sequence[Path]) -> Sequence[Path]:
    app_specs = list[Path]()
    for path in paths:
        if not path.is_dir():
            app_specs.append(path)
        else:
            patterns = ["application.json", "*.arc32.json"]

            app_specs = []
            for pattern in patterns:
                app_specs.extend(path.rglob(pattern))

    app_specs = sorted(set(app_specs))
    if not app_specs:
        raise PuyaError("No app specs found")
    return app_specs


def parse_app_spec_methods(app_spec_json: str) -> tuple[str, Sequence[ARC4Method]]:
    app_spec = json.loads(app_spec_json)
    contract = app_spec["contract"]
    hints = app_spec["hints"]
    contract_name = contract["name"]
    methods = list[ARC4Method]()
    arc4_methods = {m.signature: m for m in _parse_methods(contract["methods"])}
    for arc4_method in arc4_methods.values():
        method_hints = hints[str(arc4_method.signature)]
        create_option, allowed_oca = _call_config(method_hints["call_config"])
        methods.append(
            ARC4ABIMethod(
                name=arc4_method.python_name,
                desc=arc4_method.desc,
                args=arc4_method.signature.args,
                returns=arc4_method.signature.returns,
                config=ARC4ABIMethodConfig(
                    source_location=None,
                    name=arc4_method.signature.name,
                    create=create_option,
                    readonly=bool(method_hints.get("read_only") or arc4_method.readonly),
                    allowed_completion_types=allowed_oca,
                    default_args=immutabledict(
                        _default_args(method_hints.get("default_arguments", {}), arc4_methods)
                    ),
                    structs=immutabledict(_structs(method_hints.get("structs", {}))),
                ),
            )
        )
    return contract_name, methods


@attrs.frozen(kw_only=True)
class _MethodSignature:
    name: str
    args: tuple[ARC4MethodArg, ...]
    returns: ARC4Returns

    def __str__(self) -> str:
        return f"{self.name}({','.join(a.type_ for a in self.args)}){self.returns.type_}"


@attrs.frozen(kw_only=True)
class _Method:
    signature: _MethodSignature
    python_name: str
    desc: str | None
    readonly: bool | None


def _parse_methods(methods: list[dict[str, typing.Any]]) -> Iterable[_Method]:
    arc4_names = dict[str, int]()
    for method in methods:
        signature = _parse_signature(method)
        name_seen = arc4_names[signature.name] = arc4_names.get(signature.name, 0) + 1
        yield _Method(
            signature=signature,
            desc=method.get("desc"),
            readonly=method.get("readonly"),
            # de-duplicate potential collisions
            python_name=signature.name if name_seen == 1 else f"{signature.name}{name_seen}",
        )


def _parse_signature(method: dict[str, typing.Any]) -> _MethodSignature:
    returns = method["returns"]
    return _MethodSignature(
        name=method["name"],
        args=tuple(
            ARC4MethodArg(
                name=arg["name"],
                type_=arg["type"],
                desc=arg.get("desc"),
            )
            for arg in method["args"]
        ),
        returns=ARC4Returns(
            type_=returns["type"],
            desc=returns.get("desc"),
        ),
    )


def _call_config(
    method_call_config: dict[str, str]
) -> tuple[ARC4CreateOption, Sequence[OnCompletionAction]]:
    try:
        (call_config,) = set(method_call_config.values())
    except ValueError as ex:
        raise PuyaError("Different call configs for a single method not supported") from ex
    match call_config:
        case "CREATE":
            create_option = ARC4CreateOption.require
        case "ALL":
            create_option = ARC4CreateOption.allow
        case "CALL":
            create_option = ARC4CreateOption.disallow
        case invalid:
            raise PuyaError(f"invalid call config option: {invalid}")
    allowed_oca = [ARC32_OCA_MAPPING[a] for a in method_call_config]
    return create_option, allowed_oca


def _default_args(
    default_args: dict[str, typing.Any], arc32_python_sig: Mapping[_MethodSignature, _Method]
) -> Iterable[tuple[str, str]]:
    for param, default_arg_config in default_args.items():
        data = default_arg_config["data"]
        source = default_arg_config["source"]
        match source:
            case "global-state":
                yield param, data
            case "local-state":
                yield param, data
            case "abi-method":
                signature = _parse_signature(data)
                yield param, arc32_python_sig[signature].python_name
            case _:
                raise PuyaError(f"Unsupported source '{source}' for default argument: {param}")


def _structs(structs: dict[str, dict[str, typing.Any]]) -> Iterable[tuple[str, ARC32StructDef]]:
    for param, struct_config in structs.items():
        yield param, ARC32StructDef(name=struct_config["name"], elements=struct_config["elements"])


if __name__ == "__main__":
    main()
