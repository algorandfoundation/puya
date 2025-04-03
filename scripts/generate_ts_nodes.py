from collections.abc import Iterable
from pathlib import Path

import attrs
import mypy.nodes
import mypy.options
import mypy.types

from puyapy.parse import get_mypy_options, parse_and_typecheck


@attrs.define
class TsType:
    name: str
    base_types: list[str] = attrs.field(factory=list)
    fields: dict[str, str] = attrs.field(factory=dict)


def safe_name(name: str) -> str:
    match name:
        case "Function":
            return "_Function"
        case _:
            return name


def base_type_name(x: mypy.nodes.Expression) -> str:
    match x:
        case mypy.nodes.NameExpr(name=name):
            return safe_name(name)
        case mypy.nodes.MemberExpr(
            expr=mypy.nodes.NameExpr(fullname="puya.awst.nodes.enum"), name=name
        ):
            return safe_name(name)
        case mypy.nodes.MemberExpr(
            expr=mypy.nodes.NameExpr(fullname="puya.awst.txn_fields.enum"), name=name
        ):
            return safe_name(name)
        case mypy.nodes.MemberExpr(expr=mypy.nodes.NameExpr(name="enum"), name=name):
            return name
        case _:
            raise ValueError("Unexpected value")


def capitalize_first(x: str) -> str:
    if len(x) == 0:
        return x
    return x[0].upper() + x[1:]


def to_camel_case(snake_str: str) -> str:
    return "".join(capitalize_first(x) for x in snake_str.split("_"))


def to_lower_camel_case(snake_str: str) -> str:
    # We capitalize the first letter of each component except the first one
    # with the 'capitalize' method and join them together.
    camel_string = to_camel_case(snake_str)
    return camel_string[0].lower() + camel_string[1:]


def extract_type_name(_t: mypy.types.Type) -> str:
    match _t:
        case mypy.types.TypeAliasType(alias=mypy.nodes.TypeAlias(target=target)):
            return extract_type_name(target)
        case mypy.types.UnionType(items=items):
            return " | ".join(
                extract_type_name(t) for t in items if extract_type_name(t) != "Range"
            )
        case mypy.types.NoneType():
            return "null"

        case mypy.types.TypeType(item=item):
            return extract_type_name(item)
        case mypy.types.Instance(type=type, args=args):
            if type.fullname == "typing.Sequence":
                return f"Array<{extract_type_name(args[0])}>"
            if type.fullname == "typing.Mapping":
                return f"Map<{extract_type_name(args[0])}, {extract_type_name(args[1])}>"
            if type.fullname == "immutabledict.immutabledict":
                return f"Map<{extract_type_name(args[0])}, {extract_type_name(args[1])}>"
            if type.fullname == "builtins.tuple":
                return "[" + ", ".join(extract_type_name(t) for t in args) + "]"
            if type.fullname == "puya.utils.StableSet":
                return f"Set<{extract_type_name(args[0])}>"
            if type.fullname == "typing.AbstractSet":
                return f"Set<{extract_type_name(args[0])}>"
            if type.fullname == "builtins.str":
                return "string"
            if type.fullname == "builtins.int":
                return "bigint"
            if type.fullname == "builtins.bool":
                return "boolean"
            if type.fullname == "builtins.bytes":
                return "Uint8Array"
            if type.fullname == "_decimal.Decimal":
                return "string"
            if type.fullname == "puya.awst.nodes.Label":
                return "string"
            if type.fullname.startswith("puya.awst.wtypes"):
                return f"wtypes.{type.fullname[17:]}"
            if type.fullname.startswith("puya."):
                module_name = ".".join(type.fullname.split(".")[:-1])
                return type.fullname[len(module_name) + 1 :]

            return type.fullname
        case _:
            raise ValueError("AAARGH")


def visit_class(c: mypy.nodes.ClassDef) -> TsType:
    type_instance = TsType(safe_name(c.name))
    type_instance.base_types.extend(base_type_name(n) for n in c.base_type_exprs)
    # Special case: Treat this enum as a string enum
    if c.fullname == "puya.awst.nodes.PuyaLibFunction":
        type_instance.base_types.append("StrEnum")
    is_str_enum = "StrEnum" in type_instance.base_types
    enum_auto = 1
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
                            type=mypy.types.Instance(
                                type=mypy.nodes.TypeInfo(fullname="enum.auto")
                            ),
                        ),
                    )
                ]
            ):
                member_name_camel = to_lower_camel_case(member_name)
                type_instance.fields[member_name_camel] = (
                    member_name if is_str_enum else f"{enum_auto}"
                )
                enum_auto += 1
            case mypy.nodes.AssignmentStmt(
                lvalues=[
                    mypy.nodes.NameExpr(
                        name=member_name,
                    )
                ]
            ) if is_str_enum:
                member_name_camel = to_lower_camel_case(member_name)
                type_instance.fields[member_name_camel] = member_name
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
                # if member_name == "methods" and c.name == "Contract":
                #     continue
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
        yield f"  {field} = {ts_type.fields[field]},"
    yield "}"


def get_visitor_type(ts_type: TsType, ts_types: list[TsType]) -> str | None:
    match ts_type.name:
        case "Expression" | "Statement" | "RootNode" | "ContractMemberNode":
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
    yield "  uInt64Constant: IntegerConstant,"
    yield "  bigUIntConstant: IntegerConstant,"
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
    bases = [b for b in ts_type.base_types if b != "ABC"]
    if len(bases) == 1:
        extends = f" extends {bases[0]} "
    elif len(bases) > 1:
        extends = f" extends classes({",".join(bases)}) "
    else:
        extends = ""
    yield f"export{abstract_kw}class {ts_type.name}{extends}{{"

    yield f"  constructor(props: Props<{ts_type.name}>) {{"
    if len(bases) == 1:
        yield "    super(props)"
    elif len(bases) > 1:
        yield "    super("
        yield ", ".join("[props]" for _ in bases)
        yield ")"
    for field_name in ts_type.fields:
        yield f"    this.{field_name} = props.{field_name}"
    yield "  }"

    for field_name, field_type in ts_type.fields.items():
        if field_name == "id" and ts_type.name == "SingleEvaluation":
            yield f"  readonly {field_name}: symbol"
        elif "undefined" in field_type:
            yield f"  readonly {field_name}?: {field_type}"
        else:
            yield f"  readonly {field_name}: {field_type}"
    if not is_abstract and visitor_type:
        yield f"  accept<T>(visitor: {visitor_type}Visitor<T>): T {{"
        yield f"     return visitor.visit{ts_type.name}(this)"
        yield "   }"
    elif is_abstract and visitor_type:
        yield f"  abstract accept<T>(visitor: {visitor_type}Visitor<T>): T"

    yield "}"


def print_types(ts_types: list[TsType]) -> Iterable[str]:
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

    for t in ts_types:
        if t.name == "TxnField":
            continue
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

    yield "export type AWST = Contract | LogicSignature | Subroutine"
    yield "export type ARC4MethodConfig = ARC4BareMethodConfig | ARC4ABIMethodConfig"

    yield from print_concrete_type_map(ts_types)

    yield from print_visitor(ts_types, "Expression")
    yield from print_visitor(ts_types, "Statement")
    yield from print_visitor(ts_types, "ContractMemberNode")
    yield from print_visitor(ts_types, "RootNode")


def write_file(ts_types: list[TsType], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text("\n".join(print_types(ts_types)), encoding="utf-8")


def _get_mypy_options() -> mypy.options.Options:
    mypy_opts = get_mypy_options(custom_typeshed_path=None)

    # allow use of any
    mypy_opts.disallow_any_unimported = False
    mypy_opts.disallow_any_expr = False
    mypy_opts.disallow_any_decorated = False
    mypy_opts.disallow_any_explicit = False

    # Enable new generic syntax
    mypy_opts.enable_incomplete_feature += [mypy.options.NEW_GENERIC_SYNTAX]

    return mypy_opts


def generate_file(*, out_path: Path, puya_path: Path) -> None:
    nodes_path = puya_path / "awst/nodes.py"
    txn_fields_path = puya_path / "awst/txn_fields.py"
    paths = [nodes_path, txn_fields_path]

    ignored_types = ("ContinueStatement", "BreakStatement")

    ts_types = list[TsType]()

    _, ordered_modules = parse_and_typecheck(paths, _get_mypy_options())
    for module in ordered_modules.values():
        if module.path not in (nodes_path, txn_fields_path):
            continue
        for statement in module.node.defs:
            match statement:
                case mypy.nodes.ClassDef() as cdef:
                    if cdef.name.startswith("_"):
                        continue
                    ts_type = visit_class(cdef)
                    if ts_type.name in ignored_types:
                        continue
                    ts_types.append(ts_type)

    write_file(ts_types, out_path)
