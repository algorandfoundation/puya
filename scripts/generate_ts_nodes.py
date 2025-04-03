import abc
import collections.abc
import decimal
import enum
import inspect
import types
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping
from pathlib import Path

import attrs
import immutabledict

from puya import avm, parse, program_refs, utils
from puya.awst import (
    nodes as awst_nodes,
    txn_fields,
    wtypes,
)

_VCS_ROOT = Path(__file__).parent.parent

_DEFAULT_OUT_PATH = _VCS_ROOT / "tests" / "output" / "nodes.ts.txt"

_EXPORT_UNIONS = {
    awst_nodes.Lvalue: "LValue",
    awst_nodes.CompileTimeConstantExpression: "Constant",
    awst_nodes.ARC4MethodConfig: "ARC4MethodConfig",
}

_SIMPLE_TYPE_NAME_MAPPINGS: typing.Final[Mapping[type, str]] = {
    type(None): "null",
    str: "string",
    int: "bigint",
    bool: "boolean",
    bytes: "Uint8Array",
    decimal.Decimal: "string",
    awst_nodes.Function: "_Function",
    **{
        t: t.__name__
        for t in (
            txn_fields.TxnField,
            parse.SourceLocation,
            program_refs.ContractReference,
            program_refs.LogicSigReference,
            avm.OnCompletionAction,
        )
    },
}

_MODULE_QUALIFICATIONS = {
    wtypes.WType.__module__: "wtypes",
    awst_nodes.Node.__module__: None,
}


def generate_file(*, out_path: Path = _DEFAULT_OUT_PATH) -> None:
    ts_data = list[TsData]()
    after_imports = False
    for module_member_name, module_value in vars(awst_nodes).items():
        # we start once we encounter the base Node type, anything before that is from imports
        if module_value is awst_nodes.Node:
            after_imports = True
        if module_member_name.startswith("_") or not after_imports:
            pass
        elif isinstance(module_value, types.UnionType):
            name_to_use = _EXPORT_UNIONS.get(module_value)
            if name_to_use is not None:
                ts_data.append(TsTypeUnion.build(name_to_use, module_value))
        elif isinstance(module_value, type):
            klass = module_value
            if issubclass(klass, enum.Enum):
                ts_data.append(TsEnum.build(klass))
            else:
                try:
                    attrs_fields = attrs.fields(klass)  # type: ignore[arg-type]
                except attrs.exceptions.NotAnAttrsClassError:
                    pass
                else:
                    ts_data.append(TsType.build(klass, attrs_fields))

    lines = print_types(ts_data)
    out_text = (
        "\n".join(lines)
        .replace("ContractMemberVisitor", "ContractMemberNodeVisitor")
        .replace("contractMember:", "contractMemberNode:")
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_text, encoding="utf-8")


@attrs.frozen
class TsType:
    name: str
    base_types: list[str]
    fields: dict[str, str]
    is_abstract: bool
    visitor_type: str | None

    @classmethod
    def build(cls, klass: type, attrs_fields: tuple[attrs.Attribute, ...]) -> typing.Self:  # type: ignore[type-arg]
        cls_name = convert_type_annotation(klass)
        # Use this instead of attrs_field.type because this does str eval.
        # Can't just use this though as it can include things like properties
        klass_annotations = inspect.get_annotations(klass, eval_str=True)
        attrs_members = {}
        for attrs_field in attrs_fields:
            try:
                field_annotation = klass_annotations[attrs_field.name]
            except KeyError:
                pass
            else:
                member_name_camel = to_lower_camel_case(attrs_field.name)
                attrs_members[member_name_camel] = convert_type_annotation(field_annotation)
        bases = [b for b in klass.__bases__ if b is not object]
        try:
            bases.remove(abc.ABC)
        except ValueError:
            is_abstract = klass is awst_nodes.Node
        else:
            is_abstract = True

        accept_method = getattr(klass, "accept", None)
        if accept_method is None:
            visitor_type = None
        else:
            accept_annotations = inspect.get_annotations(accept_method)
            accept_annotations.pop("return")
            (accept_arg_type,) = accept_annotations.values()
            visitor_type = typing.get_origin(accept_arg_type).__name__

        return cls(
            name=cls_name,
            is_abstract=is_abstract,
            base_types=[convert_type_annotation(b) for b in bases],
            fields=attrs_members,
            visitor_type=visitor_type,
        )

    def render(self) -> Iterator[str]:
        abstract_kw = " abstract " if self.is_abstract else " "
        bases = self.base_types
        if len(bases) == 1:
            extends = f" extends {bases[0]} "
        elif len(bases) > 1:
            extends = f" extends classes({",".join(bases)}) "
        else:
            extends = ""
        yield f"export{abstract_kw}class {self.name}{extends}{{"

        yield f"  constructor(props: Props<{self.name}>) {{"
        if len(bases) == 1:
            yield "    super(props)"
        elif len(bases) > 1:
            yield "    super("
            yield ", ".join("[props]" for _ in bases)
            yield ")"
        for field_name in self.fields:
            yield f"    this.{field_name} = props.{field_name}"
        yield "  }"

        for field_name, field_type in self.fields.items():
            if self.name == awst_nodes.SingleEvaluation.__name__ and field_name == "id":
                yield f"  readonly {field_name}: symbol"
            else:
                yield f"  readonly {field_name}: {field_type}"

        visitor_type_name = self.visitor_type
        if visitor_type_name is not None:
            if self.is_abstract:
                yield f"  abstract accept<T>(visitor: {visitor_type_name}<T>): T"
            else:
                yield f"  accept<T>(visitor: {visitor_type_name}<T>): T {{"
                yield f"     return visitor.visit{self.name}(this)"
                yield "   }"
        yield "}"


@attrs.frozen
class TsEnum:
    name: str
    values: dict[str, int | str]

    @classmethod
    def build(cls, klass: type[enum.Enum]) -> typing.Self:
        cls_name = convert_type_annotation(klass)
        enum_values = {}
        for member_name, enum_member in klass._member_map_.items():
            member_name_camel = to_lower_camel_case(member_name)
            if isinstance(enum_member.value, int | str):
                enum_value = enum_member.value
            else:
                assert klass is awst_nodes.PuyaLibFunction
                enum_value = member_name
            enum_values[member_name_camel] = enum_value
        return cls(name=cls_name, values=enum_values)

    def render(self) -> Iterator[str]:
        yield f"export enum {self.name} {{"
        for field, value in self.values.items():
            if isinstance(value, str):
                value_str = f'"{value}"'
            else:
                value_str = str(value)
            yield f"  {field} = {value_str},"
        yield "}"


@attrs.frozen
class TsTypeUnion:
    name: str
    members: tuple[str, ...]

    @classmethod
    def build(cls, name: str, value: types.UnionType) -> typing.Self:
        return cls(
            name=name,
            members=tuple(convert_type_annotation(um) for um in value.__args__),
        )

    def render(self) -> Iterator[str]:
        lhs = f"export type {self.name} = "
        if len(self.members) < 3:
            yield f"{lhs}{' | '.join(self.members)}"
        else:
            yield lhs
            for member in self.members:
                yield f"    | {member}"


TsData = TsType | TsEnum | TsTypeUnion


def convert_type_annotation(
    t: type | types.UnionType | types.GenericAlias | typing.NewType,
) -> str:
    if isinstance(t, type):
        try:
            return _SIMPLE_TYPE_NAME_MAPPINGS[t]
        except KeyError:
            pass
        mapped_module_name = _MODULE_QUALIFICATIONS[t.__module__]
        if mapped_module_name is None:
            return t.__name__
        return ".".join((mapped_module_name, t.__name__))
    if isinstance(t, typing.NewType):
        return convert_type_annotation(t.__supertype__)

    origin = typing.get_origin(t)
    if origin is not None:
        args = typing.get_args(t)
        mapped_args = tuple(map(convert_type_annotation, args))
        match origin, mapped_args:
            case (collections.abc.Sequence, (element_type,)):
                return f"Array<{element_type}>"
            case ((collections.abc.Mapping | immutabledict.immutabledict), (key_type, value_type)):
                return f"Map<{key_type}, {value_type}>"
            case ((collections.abc.Set | utils.StableSet), (element_type,)):
                return f"Set<{element_type}>"
            case ((typing.Union | types.UnionType), _):
                return " | ".join(mapped_args)
    raise ValueError(f"unhandled type annotation: {t!r}")


def capitalize_first(x: str) -> str:
    if not x:
        return x
    return x[0].upper() + x[1:]


def lowercase_first(s: str) -> str:
    if not s:
        return s
    return s[0].lower() + s[1:]


def to_camel_case(snake_str: str) -> str:
    return "".join(capitalize_first(x) for x in snake_str.split("_"))


def to_lower_camel_case(snake_str: str) -> str:
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return lowercase_first(camel_string)


def print_types(ts_data: list[TsData]) -> Iterator[str]:
    yield "/* AUTOGENERATED FILE - DO NOT EDIT (see puya/scripts/generate_ts_nodes.py) */"
    yield "import { classes } from 'polytype'"
    yield "import type { Props } from '../typescript-helpers'"
    yield (
        "import type { ContractReference, LogicSigReference, OnCompletionAction } "
        "from './models'"
    )
    yield "import type { SourceLocation } from './source-location'"
    yield "import type { TxnField } from './txn-fields'"
    yield "import type { wtypes } from './wtypes'"

    ts_types = []
    visitor_to_visitable = defaultdict[str, list[TsType]](list)
    unions = []
    root_node_types = []
    for t in ts_data:
        if isinstance(t, TsTypeUnion):
            unions.append(t)
        elif isinstance(t, TsEnum):
            yield from t.render()
        else:
            ts_types.append(t)
            if t.visitor_type and not t.is_abstract:
                visitor_to_visitable[t.visitor_type].append(t)
            if awst_nodes.RootNode.__name__ in t.base_types:
                root_node_types.append(t)
            yield from t.render()

    unions.append(
        TsTypeUnion(
            name="AWST",
            members=tuple(t.name for t in root_node_types),
        )
    )
    for tu in unions:
        yield from tu.render()

    # Concrete type map
    yield "export const concreteNodes = {"
    for ts_type in ts_types:
        if not ts_type.is_abstract:
            yield f"  {lowercase_first(ts_type.name)}: {ts_type.name},"
    # Special cases
    yield "  uInt64Constant: IntegerConstant,"
    yield "  bigUIntConstant: IntegerConstant,"
    yield "} as const"

    # Visitors
    for visitor_base_name, visitables in visitor_to_visitable.items():
        yield f"export interface {visitor_base_name}<T> {{"
        arg_name = lowercase_first(visitor_base_name).removesuffix("Visitor")
        for ts_type in visitables:
            yield f"  visit{ts_type.name}({arg_name}: {ts_type.name}): T"
        yield "}"


if __name__ == "__main__":
    generate_file()
