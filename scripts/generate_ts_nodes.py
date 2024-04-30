from typing import Iterable

import attrs
import mypy.nodes
import mypy.types

from puya.awst import nodes as awst_nodes
from pathlib import Path

from puya.compile import parse_with_mypy
from puya.options import PuyaOptions

VCS_ROOT = Path(__file__).parent.parent


@attrs.define
class TsType:
    name: str
    base_types: list[str] = attrs.field(factory=list)
    fields: dict[str, str] = attrs.field(factory=dict)


def base_type_name(x: mypy.nodes.Expression) -> str:
    match x:
        case mypy.nodes.NameExpr(name=name):
            return name
        case mypy.nodes.MemberExpr(
            expr=mypy.nodes.NameExpr(fullname="puya.awst.nodes.enum"), name=name
        ):
            return name
        case _:
            raise ValueError("Unexpected value")


def to_camel_case(snake_str: str) -> str:
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))


def to_lower_camel_case(snake_str: str) -> str:
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return snake_str[0].lower() + camel_string[1:]


def extract_type_name(_t: mypy.types.Type) -> str:
    match _t:
        case mypy.types.TypeAliasType(alias=mypy.nodes.TypeAlias(target=target)):
            return extract_type_name(target)
        case mypy.types.UnionType(items=items):
            return " | ".join(extract_type_name(t) for t in items)
        case mypy.types.NoneType():
            return "undefined"
        case mypy.types.AnyType(missing_import_name=missing_import) if missing_import:
            if missing_import == "puya.awst.nodes.decimal":
                return "number"
            if missing_import == "puya.awst.nodes.enum":
                return "enum"
            else:
                raise ValueError("Unknown missing import: " + missing_import)
        case mypy.types.TypeType(item=item):
            return extract_type_name(item)
        case mypy.types.Instance(type=type, args=args):
            if type.fullname == "typing.Sequence":
                return f"Array<{extract_type_name(args[0])}>"
            if type.fullname == "typing.Mapping":
                return f"Map<{extract_type_name(args[0])}, {extract_type_name(args[1])}>"
            if type.fullname == "builtins.tuple":
                return "[" + ", ".join(extract_type_name(t) for t in args) + "]"
            if type.fullname == "puya.utils.StableSet":
                return f"Set<{extract_type_name(args[0])}>"
            if type.fullname == "builtins.str":
                return "string"
            if type.fullname == "builtins.int":
                return "bigint"
            if type.fullname == "builtins.bool":
                return "boolean"
            if type.fullname == "builtins.bytes":
                return "Uint8Array"
            if type.fullname == "puya.models.ARC4ABIMethodConfig":
                return "ARC4ABIMethodConfig"
            if type.fullname == "puya.models.ARC4BareMethodConfig":
                return "ARC4BareMethodConfig"
            if type.fullname.startswith("puya.awst.nodes."):
                return type.fullname[16:]
            if type.fullname == "puya.parse.SourceLocation":
                return "SourceLocation"
            if type.fullname.startswith("puya.awst.wtypes"):
                return f"wtypes.{type.fullname[17:]}"
            return type.fullname
        case _:
            raise ValueError("AAARGH")


def visit_class(c: mypy.nodes.ClassDef) -> TsType:
    type_instance = TsType(c.name)
    type_instance.base_types.extend(base_type_name(n) for n in c.base_type_exprs)
    is_str_enum = "StrEnum" in type_instance.base_types
    for x in c.defs.body:
        match x:
            case mypy.nodes.AssignmentStmt(
                lvalues=[
                    mypy.nodes.NameExpr(
                        name=member_name,
                    )
                ],
                rvalue=mypy.nodes.StrExpr(value=enum_value),
            ) if enum_value and is_str_enum:
                member_name_camel = to_lower_camel_case(member_name)
                type_instance.fields[member_name_camel] = enum_value
            case mypy.nodes.AssignmentStmt(
                lvalues=[
                    mypy.nodes.NameExpr(
                        name=member_name,
                        node=mypy.nodes.Var(
                            type=member_type,
                        ),
                    )
                ]
            ) if member_type:
                member_name_camel = to_lower_camel_case(member_name)
                type_instance.fields[member_name_camel] = extract_type_name(member_type)
            case mypy.nodes.FuncDef():
                pass
            case _:
                pass

    return type_instance


def print_str_enum(ts_type: TsType) -> Iterable[str]:
    yield f"export enum {ts_type.name} {{"
    for field, value in ts_type.fields.items():
        enum_value = field if value == "enum" else value
        yield f'  {field} = "{enum_value}",'
    yield "}"


def print_num_enum(ts_type: TsType) -> Iterable[str]:
    yield f"export enum {ts_type.name} {{"
    for field in ts_type.fields:
        yield f"  {field},"
    yield "}"


def get_visitor_type(ts_type: TsType, ts_types: list[TsType]) -> str | None:
    match ts_type.name:
        case "Expression" | "Statement" | "ModuleStatement":
            return ts_type.name

    base_types = (t for t in ts_types if t.name in ts_type.base_types)
    base_visitor_types = (get_visitor_type(t, ts_types) for t in base_types)

    return next((t for t in base_visitor_types if t), None)


def print_visitor(ts_types: list[TsType], name: str) -> Iterable[str]:
    yield f"export interface {name}Visitor<T> {{"
    for ts_type in ts_types:
        if "ABC" in ts_type.base_types or ts_type.name == "Node":
            continue

        if get_visitor_type(ts_type, ts_types) == name:
            yield f"  visit{ts_type.name}({name[0].lower()}{name[1:]}: {ts_type.name}): T"

    yield "}"


def print_concrete_type_map(ts_types: list[TsType]) -> Iterable[str]:
    yield "export const concreteNodes = {"
    for ts_type in ts_types:
        if "StrEnum" in ts_type.base_types:
            continue
        if "Enum" in ts_type.base_types:
            continue
        if "ABC" in ts_type.base_types or ts_type.name == "Node":
            continue
        yield f"  {ts_type.name[0].lower()}{ts_type.name[1:]}: {ts_type.name},"

    # Special cases
    yield f"  uInt64Constant: IntegerConstant,"
    yield f"  bigUIntConstant: IntegerConstant,"
    yield "} as const"


def print_type(ts_type: TsType, ts_types: list[TsType]) -> Iterable[str]:

    if "StrEnum" in ts_type.base_types:
        yield from print_str_enum(ts_type)
        return
    if "Enum" in ts_type.base_types:
        yield from print_num_enum(ts_type)
        return
    is_abstract = "ABC" in ts_type.base_types or ts_type.name == "Node"
    visitor_type = get_visitor_type(ts_type, ts_types)

    abstract_kw = " abstract " if is_abstract else " "
    base = next((b for b in ts_type.base_types if b != "ABC"), None)
    if base:
        extends = f" extends {base} "
    else:
        extends = ""
    yield f"export{abstract_kw}class {ts_type.name}{extends}{{"

    if not is_abstract:
        yield f"  constructor(props: Props<{ts_type.name}>) {{"
        if base:
            yield "    super()"
        yield "    Object.assign(this, props)"
        yield "  }"

    for field_name, field_type in ts_type.fields.items():
        if field_name == "wtype":
            if ts_type.name == "Expression" or visitor_type != "Expression":
                yield f"  {field_name}!: {field_type}"
                continue
            elif field_type == "wtypes.WType":
                # Don't emit duplicate wtype properties which don't override the base type
                continue
            else:
                yield f"  declare {field_name}: {field_type}"
                continue

        bang_bang = "" if "undefined" in field_type else "!"
        yield f"  {field_name}{bang_bang}: {field_type}"
    if not is_abstract and visitor_type:
        yield f" accept<T>(visitor: {visitor_type}Visitor<T>): T {{"
        yield f"    return visitor.visit{ts_type.name}(this)"
        yield "  }"
    elif is_abstract and visitor_type:
        yield f" abstract accept<T>(visitor: {visitor_type}Visitor<T>): T"

    yield "}"


def print_types(ts_types: list[TsType]) -> Iterable[str]:
    yield "/* AUTOGENERATED FILE - DO NOT EDIT (see puya/scripts/generate_ts_nodes.py) */"
    yield "import * as wtypes from './wtypes'"
    yield "import { SourceLocation } from './source-location'"
    yield "import { ARC4BareMethodConfig, ARC4ABIMethodConfig } from './arc4'"
    yield "import { Props } from '../typescript-helpers'"

    for t in ts_types:
        yield from print_type(t, ts_types)

    yield "export type LValue = "
    yield "    | VarExpression"
    yield "    | FieldExpression"
    yield "    | IndexExpression"
    yield "    | TupleExpression"
    yield "    | AppStateExpression"
    yield "    | AppAccountStateExpression"

    yield "export type Constant = "
    yield "  | IntegerConstant"
    yield "  | BoolConstant"
    yield "  | BytesConstant"
    yield "  | StringConstant"

    yield from print_concrete_type_map(ts_types)

    yield from print_visitor(ts_types, "Expression")
    yield from print_visitor(ts_types, "Statement")
    yield from print_visitor(ts_types, "ModuleStatement")


def write_file(ts_types: list[TsType], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text("\n".join(print_types(ts_types)), encoding="utf-8")


if __name__ == "__main__":
    nodes_path = VCS_ROOT / "src/puya/awst/nodes.py"
    options = PuyaOptions(paths=[nodes_path])

    ts_types = list[TsType]()

    ctx = parse_with_mypy(options)
    for module in ctx.parse_result.ordered_modules:
        if module.path != str(nodes_path):
            continue
        for statement in module.defs:
            match statement:
                case mypy.nodes.ClassDef() as cdef:
                    if cdef.name.startswith("_"):
                        continue
                    ts_type = visit_class(cdef)
                    ts_types.append(ts_type)

    write_file(ts_types, VCS_ROOT / "_tmp/ts-types.ts")
