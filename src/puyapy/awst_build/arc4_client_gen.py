# FIXME: We don't have python methods anymore. Just methods (either from puyapy or puya-ts)
import re
import textwrap
from collections.abc import Iterable, Sequence
from pathlib import Path

from puya import (
    arc56_models as arc56,
    log,
)
from puya.avm import OnCompletionAction
from puya.errors import CodeError
from puya.utils import make_path_relative_to_cwd
from puyapy.awst_build import constants
from puyapy.awst_build.arc4_utils import arc4_to_pytype, split_tuple_types

logger = log.get_logger(__name__)

_AUTO_GENERATED_COMMENT_PY = "# This file is auto-generated, do not modify"
_AUTO_GENERATED_COMMENT_TS = "// This file is auto-generated, do not modify"
_INDENT = " " * 4
_NON_ALPHA_NUMERIC = re.compile(r"\W+")


def write_arc4_client(contract: arc56.Contract, out_dir: Path) -> None:
    stub_path = out_dir / f"client_{contract.name}.py"
    if _can_overwrite_auto_generated_file(stub_path):
        logger.info(f"writing {make_path_relative_to_cwd(stub_path)}")
        stub_text = _ClientGeneratorPy.generate(contract)
        stub_path.write_text(stub_text, encoding="utf8")
    else:
        logger.error(
            f"Not outputting {make_path_relative_to_cwd(stub_path)} "
            "since content does not appear to be auto-generated"
        )

    stub_path = out_dir / f"client_{contract.name}.ts"
    if _can_overwrite_auto_generated_file(stub_path):
        logger.info(f"writing {make_path_relative_to_cwd(stub_path)}")
        stub_text = _ClientGeneratorTs.generate(contract)
        stub_path.write_text(stub_text, encoding="utf8")
    else:
        logger.error(
            f"Not outputting {make_path_relative_to_cwd(stub_path)} "
            "since content does not appear to be auto-generated"
        )


def _can_overwrite_auto_generated_file(path: Path) -> bool:
    if not path.exists():
        return True
    text = path.read_text(encoding="utf8")
    return text.startswith((_AUTO_GENERATED_COMMENT_PY, _AUTO_GENERATED_COMMENT_TS))


class _ClientGeneratorPy:
    def __init__(self, contract: arc56.Contract):
        self.contract = contract
        self.python_methods = set[str]()
        self.struct_to_class = dict[str, str]()
        self.reserved_class_names = set[str]()
        self.reserved_method_names = set[str]()
        self.class_decls = list[str]()

    @classmethod
    def generate(cls, contract: arc56.Contract) -> str:
        return cls(contract)._gen()  # noqa: SLF001

    def _gen(self) -> str:
        # generate class definitions for any referenced structs in methods
        # don't generate from self.contract.structs as it may contain other struct definitions
        client_class = self._unique_class(self.contract.name)
        for method in self.contract.methods:
            for struct in filter(None, (method.returns.struct, *(a.struct for a in method.args))):
                if struct not in self.struct_to_class and (
                    struct_def := self.contract.structs.get(struct)
                ):
                    self._prepare_struct_class(struct, struct_def)
        return "\n".join(
            (
                _AUTO_GENERATED_COMMENT_PY,
                "# flake8: noqa",  # this works for flake8 and ruff
                "# fmt: off",  # disable formatting"
                "import typing",
                "",
                "import algopy",
                "",
                *self.class_decls,
                "",
                f"class {client_class}(algopy.arc4.ARC4Client, typing.Protocol):",
                *_docstring(self.contract.desc),
                *self._gen_methods(),
            )
        )

    def _prepare_struct_class(self, name: str, fields: Sequence[arc56.StructField]) -> str:
        python_name = self._unique_class(name)
        self.struct_to_class[name] = python_name
        lines = [f"class {python_name}(algopy.arc4.Struct):"]
        for field in fields:
            if isinstance(field.type, str):
                typ = self._get_client_type(field.type)
            else:
                # generate anonymous struct type
                anon_struct = f"{name}_{field.name}"
                typ = self._prepare_struct_class(anon_struct, field.type)
            lines.append(_indent(f"{field.name}: {typ}"))
        if self.class_decls:
            self.class_decls.append("")
        self.class_decls.extend(lines)
        return python_name

    def _get_client_type(self, typ: str) -> str:
        # map ABI / AVM type to algopy type
        if typ == arc56.AVMType.uint64:
            return "algopy.UInt64"
        elif typ == arc56.AVMType.bytes:
            return "algopy.Bytes"
        elif struct := self.contract.structs.get(typ):
            try:
                # use existing definition
                return self.struct_to_class[typ]
            except KeyError:
                # generate and return class name
                return self._prepare_struct_class(typ, struct)
        else:
            return str(arc4_to_pytype(typ, None))

    def _unique_class(self, name: str) -> str:
        base_name = name = _get_safe_name(name)
        seq = 1
        while name in self.reserved_class_names:
            seq += 1
            name = f"{base_name}{seq}"

        self.reserved_class_names.add(name)
        return name

    def _unique_method(self, name: str) -> str:
        base_name = name = _get_safe_name(name)
        seq = 1
        while name in self.reserved_method_names:
            seq += 1
            name = f"{base_name}{seq}"

        self.reserved_method_names.add(name)
        return name

    def _gen_methods(self) -> Iterable[str]:
        if not self.contract.methods:
            yield _indent("pass")
            yield ""
        else:
            for method in self.contract.methods:
                yield self._gen_method(method)

    def _gen_method(self, method: arc56.Method) -> str:
        return_type = self._get_client_type(method.returns.struct or method.returns.type)
        python_method = self._unique_method(method.name)
        return _indent(
            (
                _arc4_method_to_py_decorator(python_method, method),
                f"def {python_method}(",
                _indent(
                    (
                        "self,",
                        *(self._gen_arg(arg) for arg in method.args),
                    )
                ),
                f") -> {return_type}:" + ("" if method.desc else " ..."),
                *_docstring(method.desc),
                "",
            )
        )

    def _gen_arg(self, arg: arc56.MethodArg) -> str:
        python_type = self._get_client_type(arg.struct or arg.type)
        return f"{arg.name}: {python_type},"


class _ClientGeneratorTs:
    def __init__(self, contract: arc56.Contract):
        self.contract = contract
        self.python_methods = set[str]()
        self.struct_to_class = dict[str, str]()
        self.reserved_class_names = set[str]()
        self.reserved_method_names = set[str]()
        self.class_decls = list[str]()

    @classmethod
    def generate(cls, contract: arc56.Contract) -> str:
        return cls(contract)._gen()  # noqa: SLF001

    def _gen(self) -> str:
        # generate class definitions for any referenced structs in methods
        # don't generate from self.contract.structs as it may contain other struct definitions
        client_class = self._unique_class(self.contract.name)
        for method in self.contract.methods:
            for struct in filter(None, (method.returns.struct, *(a.struct for a in method.args))):
                if struct not in self.struct_to_class and (
                    struct_def := self.contract.structs.get(struct)
                ):
                    self._prepare_struct_class(struct, struct_def)
        return "\n".join(
            (
                _AUTO_GENERATED_COMMENT_TS,
                "import * from '@algorandfoundation/algorand-typescript'",
                "",
                *self.class_decls,
                "",
                *_tsdoc(self.contract.desc),
                f"export abstract class {client_class} extends Contract {{",
                *self._gen_methods(),
                "}",
                "",
            )
        )

    def _prepare_struct_class(self, name: str, fields: Sequence[arc56.StructField]) -> str:
        ts_name = self._unique_class(name)
        self.struct_to_class[name] = ts_name
        lines = [f"export class {ts_name} extends arc4.Struct<{{"]
        for field in fields:
            if isinstance(field.type, str):
                typ = self._get_client_type(field.type)
            else:
                # generate anonymous struct type
                anon_struct = f"{name}_{field.name}"
                typ = self._prepare_struct_class(anon_struct, field.type)
            lines.append(_indent(f"{field.name}: {typ},"))
        lines.append("}> { }")
        if self.class_decls:
            self.class_decls.append("")
        self.class_decls.extend(lines)
        return ts_name

    def _get_client_type(self, typ: str) -> str:
        # map ABI / AVM type to algots type
        if typ == arc56.AVMType.uint64:
            return "uint64"
        elif typ == arc56.AVMType.bytes:
            return "Bytes"
        elif struct := self.contract.structs.get(typ):
            try:
                # use existing definition
                return self.struct_to_class[typ]
            except KeyError:
                # generate and return class name
                return self._prepare_struct_class(typ, struct)
        else:
            return arc4_to_algots_name(typ)

    def _unique_class(self, name: str) -> str:
        base_name = name = _get_safe_name(name)
        seq = 1
        while name in self.reserved_class_names:
            seq += 1
            name = f"{base_name}{seq}"

        self.reserved_class_names.add(name)
        return name

    def _unique_method(self, name: str) -> str:
        base_name = name = _get_safe_name(name)
        seq = 1
        while name in self.reserved_method_names:
            seq += 1
            name = f"{base_name}{seq}"

        self.reserved_method_names.add(name)
        return name

    def _gen_methods(self) -> Iterable[str]:
        for method in self.contract.methods:
            yield self._gen_method(method)

    def _gen_method(self, method: arc56.Method) -> str:
        return_type = self._get_client_type(method.returns.struct or method.returns.type)
        method_name = self._unique_method(method.name)
        return _indent(
            (
                "",
                *_tsdoc(method.desc),
                _arc4_method_to_ts_decorator(method_name, method),
                f"{method_name}(",
                _indent(tuple(self._gen_arg(arg) for arg in method.args)),
                f"): {return_type} {{",
                _indent('err("stub only")'),
                "}",
            )
        )

    def _gen_arg(self, arg: arc56.MethodArg) -> str:
        arg_type = self._get_client_type(arg.struct or arg.type)
        return f"{arg.name}: {arg_type},"


def _docstring(desc: str | None) -> list[str]:
    if desc is None:
        return []
    return _indent(
        [
            '"""',
            *desc.splitlines(),
            '"""',
        ]
    ).splitlines()


def _tsdoc(desc: str | None) -> list[str]:
    if desc is None:
        return []
    return [
        "/**",
        *(f" * {line}" for line in desc.splitlines()),
        " */",
    ]


def _arc4_method_to_py_decorator(python_method: str, method: arc56.Method) -> str:
    abimethod_args = dict[str, object]()
    if method.name != python_method:
        abimethod_args["name"] = method.name
    if method.readonly:
        abimethod_args["readonly"] = True
    # if any alias types are encountered, force index encoding
    if {a.type for a in method.args}.intersection(("asset", "application", "account")):
        abimethod_args["resource_encoding"] = "index"
    if not _compatible_actions(method.actions.create, method.actions.call):
        # TODO: support this, once decorators support it
        raise CodeError(
            f"unsupported on completion combination for generating an ARC-4 client"
            f" for method: {method.name}"
        )
    actions = sorted(
        {*method.actions.create, *method.actions.call}, key=lambda a: OnCompletionAction[a]
    )
    if set(actions) != {OnCompletionAction.NoOp.name}:
        abimethod_args["allow_actions"] = actions
    if method.actions.create and method.actions.call:
        abimethod_args["create"] = "allow"
    elif method.actions.create:
        abimethod_args["create"] = "require"
    else:
        # disallow is default
        pass
    kwargs = ", ".join(f"{name}={value!r}" for name, value in abimethod_args.items())
    decorator = f"@{constants.ABIMETHOD_DECORATOR_ALIAS}"
    if kwargs:
        decorator += f"({kwargs})"
    return decorator


def _arc4_method_to_ts_decorator(method_name: str, method: arc56.Method) -> str:
    abimethod_args = dict[str, object]()
    if method.name != method_name:
        abimethod_args["name"] = method.name
    if method.readonly:
        abimethod_args["readonly"] = True
    # if any alias types are encountered, force index encoding
    if {a.type for a in method.args}.intersection(("asset", "application", "account")):
        abimethod_args["resourceEncoding"] = "index"
    if not _compatible_actions(method.actions.create, method.actions.call):
        # TODO: support this, once decorators support it
        raise CodeError(
            f"unsupported on completion combination for generating an ARC-4 client"
            f" for method: {method.name}"
        )
    actions = sorted(
        {*method.actions.create, *method.actions.call}, key=lambda a: OnCompletionAction[a]
    )
    if set(actions) != {OnCompletionAction.NoOp.name}:
        abimethod_args["allowActions"] = actions
    if method.actions.create and method.actions.call:
        abimethod_args["onCreate"] = "allow"
    elif method.actions.create:
        abimethod_args["onCreate"] = "require"
    else:
        # disallow is default
        pass
    kwargs = ", ".join(f"{name}: {value!r}" for name, value in abimethod_args.items())
    decorator = "@abimethod"
    if kwargs:
        decorator += f"({{ {kwargs} }})"
    return decorator


def _compatible_actions(create: Sequence[str], call: Sequence[str]) -> bool:
    if not create:
        return True
    if not call:
        return True
    # if both collections are present, then they are compatible if everything in
    # create is also in call
    return all(a in call for a in create)


def _indent(lines: Iterable[str] | str) -> str:
    if not isinstance(lines, str):
        lines = "\n".join(lines)
    return textwrap.indent(lines, _INDENT)


def _get_safe_name(name: str) -> str:
    return _NON_ALPHA_NUMERIC.sub("_", name)


_UINT_REGEX = re.compile(r"^uint(?P<n>[0-9]+)$")
_UFIXED_REGEX = re.compile(r"^ufixed(?P<n>[0-9]+)x(?P<m>[0-9]+)$")
_FIXED_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[(?P<size>[0-9]+)]$")
_DYNAMIC_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[]$")
_TUPLE_REGEX = re.compile(r"^\((?P<types>.+)\)$")
_ARC4_PYTYPE_MAPPING = {
    "bool": "arc4.Bool",
    "string": "arc4.Str",
    "account": "Account",
    "application": "Application",
    "asset": "Asset",
    "void": "void",
    "txn": "gtxn.Transaction",
    "pay": "gtxn.PaymentTxn",
    "keyreg": "gtxn.KeyRegistrationTxn",
    "acfg": "gtxn.AssetConfigTxn",
    "axfer": "gtxn.AssetTransferTxn",
    "afrz": "gtxn.AssetFreezeTxn",
    "appl": "gtxn.ApplicationCallTxn",
    "address": "arc4.Address",
    "byte": "arc4.Byte",
    "byte[]": "arc4.DynamicBytes",
}


def arc4_to_algots_name(typ: str) -> str:
    if known_typ := _ARC4_PYTYPE_MAPPING.get(typ):
        return known_typ
    if uint := _UINT_REGEX.match(typ):
        n = int(uint.group("n"))
        return f"arc4.Uint<{n}>"
    if ufixed := _UFIXED_REGEX.match(typ):
        n, m = map(int, ufixed.group("n", "m"))
        return f"arc4.UFixed<{n}, {m}>"
    if fixed_array := _FIXED_ARRAY_REGEX.match(typ):
        arr_type, size_str = fixed_array.group("type", "size")
        size = int(size_str)
        element_type = arc4_to_algots_name(arr_type)
        return f"FixedArray<{element_type}, {size}>"
    if dynamic_array := _DYNAMIC_ARRAY_REGEX.match(typ):
        arr_type = dynamic_array.group("type")
        element_type = arc4_to_algots_name(arr_type)
        return f"arc4.DynamicArray<{element_type}>"
    if tuple_match := _TUPLE_REGEX.match(typ):
        tuple_types = [
            arc4_to_algots_name(x) for x in split_tuple_types(tuple_match.group("types"))
        ]
        return f"arc4.Tuple<readonly [{', '.join(tuple_types)}]>"
    raise CodeError(f"unknown ARC-4 type '{typ}'")
