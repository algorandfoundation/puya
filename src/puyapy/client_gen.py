import argparse
import json
import typing
from collections.abc import Iterable, Sequence
from pathlib import Path

import attrs
from cattrs.preconf.json import make_converter

from puya import (
    arc56_models as arc56,
    log,
)
from puya.arc32 import OCA_ARC32_MAPPING
from puya.arc56 import allowed_call_oca, allowed_create_oca
from puya.artifact_metadata import ARC4MethodArg, ARC4Returns
from puya.errors import PuyaError
from puyapy.awst_build.arc4_client_gen import write_arc4_client

logger = log.get_logger(__name__)
ARC32_OCA_MAPPING = {v: k for k, v in OCA_ARC32_MAPPING.items()}


@attrs.define(kw_only=True)
class PuyaGenOptions:
    paths: Sequence[Path] = attrs.field(default=(), repr=lambda p: str(list(map(str, p))))
    log_level: log.LogLevel = log.LogLevel.info
    out_dir: Path | None = None


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="puyapy-clientgen",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Output algopy contract client for typed ARC-4 ABI calls from an "
        "ARC-32 or ARC-56 application spec",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Path for outputting client, defaults to app spec folder",
        default=False,
    )
    parser.add_argument("paths", type=Path, nargs="+", metavar="PATH")
    options = PuyaGenOptions()
    parser.parse_args(namespace=options)
    log.configure_logging(min_log_level=options.log_level)
    output_stubs(options.paths, options.out_dir)


def output_stubs(paths: Sequence[Path], out_dir: Path | None) -> None:
    try:
        app_spec_paths = resolve_app_specs(paths)
        for app_spec_path in app_spec_paths:
            app_spec_json = app_spec_path.read_text("utf8")
            if app_spec_path.name.endswith(".arc56.json"):
                app_spec = parse_arc56(app_spec_json)
            else:
                # TODO: use algokit_utils to do this conversion when it is available?
                app_spec = _convert_arc32_to_arc56(app_spec_json)
            write_arc4_client(app_spec, out_dir or app_spec_path.parent)
    except PuyaError as ex:
        logger.error(str(ex))  # noqa: TRY400


def _convert_arc32_to_arc56(app_spec_json: str) -> arc56.Contract:
    name, structs, methods = _parse_arc32_app_spec_methods(app_spec_json)
    return arc56.Contract(
        name=name,
        structs=structs,
        methods=methods,
    )


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


def parse_arc56(app_spec_json: str) -> arc56.Contract:
    converter = make_converter(omit_if_default=True)
    return converter.loads(app_spec_json, arc56.Contract)


def _parse_arc32_app_spec_methods(
    app_spec_json: str,
) -> tuple[str, dict[str, Sequence[arc56.StructField]], Sequence[arc56.Method]]:
    # only need to parse a limited subset of ARC-32 for client generation
    # i.e. ABI methods, their OCA parameters, and any struct info
    # default args are ignored as they aren't supported for on chain calls currently

    app_spec = json.loads(app_spec_json)
    contract = app_spec["contract"]
    hints = app_spec["hints"]
    contract_name = contract["name"]
    methods = list[arc56.Method]()
    arc4_methods = {m.signature: m for m in _parse_methods(contract["methods"])}
    known_structs = dict[str, Sequence[arc56.StructField]]()
    for arc4_method in arc4_methods.values():
        method_hints = hints[str(arc4_method.signature)]
        arg_to_struct = dict[str, str]()
        for param, struct_name, struct in _parse_structs(method_hints.get("structs", {})):
            for known_struct_name, known_struct in known_structs.items():
                if known_struct == struct:
                    arg_to_struct[param] = known_struct_name
                    break
            else:
                known_structs[struct_name] = struct
                arg_to_struct[param] = struct_name
        methods.append(
            arc56.Method(
                name=arc4_method.signature.name,
                desc=arc4_method.desc,
                args=[
                    arc56.MethodArg(
                        name=a.name,
                        type=a.type_,
                        struct=arg_to_struct.get(a.name),
                    )
                    for a in arc4_method.signature.args
                ],
                returns=arc56.MethodReturns(
                    type=arc4_method.signature.returns.type_,
                    desc=arc4_method.desc,
                    struct=arg_to_struct.get("output"),
                ),
                readonly=bool(method_hints.get("read_only") or arc4_method.readonly),
                actions=_parse_call_config(method_hints["call_config"]),
            )
        )
    return contract_name, known_structs, methods


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
    desc: str | None
    readonly: bool | None


def _parse_methods(methods: list[dict[str, typing.Any]]) -> Iterable[_Method]:
    for method in methods:
        signature = _parse_signature(method)
        yield _Method(
            signature=signature,
            desc=method.get("desc"),
            readonly=method.get("readonly"),
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
                struct=arg.get("struct"),
                client_default=None,  # not supported on chain
            )
            for arg in method["args"]
        ),
        returns=ARC4Returns(
            type_=returns["type"],
            desc=returns.get("desc"),
            struct=returns.get("struct"),
        ),
    )


def _parse_call_config(method_call_config: dict[str, str]) -> arc56.MethodActions:
    create = []
    call = []
    for oca, call_config in method_call_config.items():
        action = ARC32_OCA_MAPPING[oca].name
        match call_config:
            case "CREATE" if allowed_create_oca(action):
                create.append(action)
            case "CALL" if allowed_call_oca(action):
                call.append(action)
            # allowed creates is narrower than calls so only need to check that
            case "ALL" if allowed_create_oca(action):
                create.append(action)
                call.append(action)
            case invalid:
                raise PuyaError(f"invalid call config option: {invalid}")

    return arc56.MethodActions(
        create=create,
        call=call,
    )


def _parse_structs(
    structs: dict[str, dict[str, typing.Any]],
) -> Iterable[tuple[str, str, Sequence[arc56.StructField]]]:
    for param, struct_config in structs.items():
        yield (
            param,
            struct_config["name"],
            [arc56.StructField(name=f[0], type=f[1]) for f in struct_config["elements"]],
        )


if __name__ == "__main__":
    main()
