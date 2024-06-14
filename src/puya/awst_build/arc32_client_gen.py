# TODO: when moving awst_build into it's own puyapy package, this should also move
#       into that new package, but probably outside awst_build
import itertools
import textwrap
import typing
from collections.abc import Iterable, Sequence
from pathlib import Path

from puya import log
from puya.awst_build import constants
from puya.awst_build.arc4_utils import arc4_to_pytype
from puya.models import (
    ARC4ABIMethod,
    ARC4CreateOption,
    ARC4Method,
    ARC4MethodArg,
    ARC32StructDef,
    OnCompletionAction,
)
from puya.utils import make_path_relative_to_cwd, unique

logger = log.get_logger(__name__)

_AUTO_GENERATED_COMMENT = "# This file is auto-generated, do not modify"
_INDENT = " " * 4


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
    abi_methods = [m for m in methods if isinstance(m, ARC4ABIMethod)]
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
                    for s in unique(s for m in abi_methods for s in m.config.structs.values())
                )
            ),
            "",
            f"class {name}(algopy.arc4.ARC4Client, typing.Protocol):",
            *([_indent(["pass"]), ""] if not abi_methods else []),
            *(_abi_method_to_signature(m) for m in abi_methods),
        )
    )


def _abi_struct_to_class(s: ARC32StructDef) -> Iterable[str]:
    return (
        f"class {s.name}(algopy.arc4.Struct):",
        _indent(
            f"{name}: {_arc4_type_to_algopy_cls(elem_type)}" for name, elem_type in s.elements
        ),
    )


def _abi_method_to_signature(m: ARC4ABIMethod) -> str:
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


def _arc4_method_to_decorator(method: ARC4ABIMethod) -> str:
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
    match config.create:
        case ARC4CreateOption.allow:
            abimethod_args["create"] = "allow"
        case ARC4CreateOption.require:
            abimethod_args["create"] = "require"
        case ARC4CreateOption.disallow:
            pass
        case invalid:
            typing.assert_never(invalid)
    kwargs = ", ".join(f"{name}={value!r}" for name, value in abimethod_args.items())
    decorator = f"@{constants.ABIMETHOD_DECORATOR_ALIAS}"
    if kwargs:
        decorator += f"({kwargs})"
    return decorator


def _indent(lines: Iterable[str] | str) -> str:
    if not isinstance(lines, str):
        lines = "\n".join(lines)
    return textwrap.indent(lines, _INDENT)
