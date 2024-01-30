#!/usr/bin/env python3
import builtins
import copy
import json
import keyword
import re
import subprocess
import textwrap
import typing
from collections.abc import Iterable
from pathlib import Path

import attrs
import structlog
from puya.awst import wtypes
from puya.awst_build.intrinsic_models import ArgMapping, FunctionOpMapping

from scripts.transform_lang_spec import (
    Immediate,
    ImmediateKind,
    LanguageSpec,
    Op,
    StackType,
    StackValue,
)

logger = structlog.get_logger(__name__)
INDENT = " " * 4
VCS_ROOT = Path(__file__).parent.parent
CLS_ACCOUNT = "Account"
CLS_BYTES = "Bytes"
CLS_UINT64 = "UInt64"
CLS_BIGINT = "BigUInt"
CLS_MAPPING: dict[str, wtypes.WType | type] = {
    "int": int,
    "bytes": bytes,
    "str": str,
    "bool": wtypes.bool_wtype,
    CLS_ACCOUNT: wtypes.account_wtype,
    CLS_BYTES: wtypes.bytes_wtype,
    CLS_UINT64: wtypes.uint64_wtype,
    CLS_BIGINT: wtypes.biguint_wtype,
}
BYTES_LITERALS = ["bytes"]
UINT64_LITERAL = "int"


class OpCodeGroup(typing.Protocol):
    def includes_op(self, op: str) -> bool:
        ...


@attrs.define(kw_only=True)
class RenamedOpCode:
    name: str
    stack_aliases: dict[str, list[str]] = attrs.field(factory=dict)
    """ops that are aliases for other ops that take stack values instead of immediates"""
    op: str

    def includes_op(self, op: str) -> bool:
        return self.op == op or op in self.stack_aliases


@attrs.define(kw_only=True)
class MergedOpCodes:
    name: str
    ops: dict[str, dict[str, list[str]]]

    def includes_op(self, op: str) -> bool:
        return op in self.ops or any(op in alias_dict for alias_dict in self.ops.values())


@attrs.define(kw_only=True)
class GroupedOpCodes:
    name: str
    """ops that are aliases for other ops that take stack values instead of immediates"""
    ops: dict[str, str] = attrs.field(factory=dict)
    """ops to include in group, mapped to their new name"""

    def includes_op(self, op: str) -> bool:
        return op in self.ops


OPCODE_GROUPS: list[OpCodeGroup] = [
    GroupedOpCodes(
        name="AppGlobals",
        ops={
            "app_global_get": "get",
            "app_global_get_ex": "get_ex",
            "app_global_del": "delete",
            "app_global_put": "put",
        },
    ),
    GroupedOpCodes(name="Scratch", ops={"loads": "load", "stores": "store"}),
    GroupedOpCodes(
        name="AppLocals",
        ops={
            "app_local_get": "get",
            "app_local_get_ex": "get_ex",
            "app_local_del": "delete",
            "app_local_put": "put",
        },
    ),
    GroupedOpCodes(
        name="Box",
        ops={
            "box_create": "create",
            "box_del": "delete",
            "box_extract": "extract",
            "box_get": "get",
            "box_len": "length",
            "box_put": "put",
            "box_replace": "replace",
        },
    ),
    GroupedOpCodes(
        name="CreateInnerTransaction",
        ops={
            "itxn_begin": "begin",
            "itxn_next": "next",
            "itxn_submit": "submit",
            "itxn_field": "set",
        },
    ),
    MergedOpCodes(
        name="InnerTransaction",
        ops={
            "itxn": {},
            "itxnas": {
                "itxna": ["F", "I"],
            },
        },
    ),
    MergedOpCodes(
        name="InnerTransactionGroup",
        ops={
            "gitxn": {},
            "gitxnas": {
                "gitxna": ["T", "F", "I"],
            },
        },
    ),
    MergedOpCodes(
        name="Global",
        ops={"global": {}},
    ),
    MergedOpCodes(
        name="Transaction",
        ops={
            "txn": {},
            "txnas": {
                "txna": ["F", "I"],
            },
        },
    ),
    MergedOpCodes(
        name="TransactionGroup",
        ops={
            "gtxns": {
                "gtxn": ["F", "T"],
            },
            # field is immediate, first stack arg is txn index, second stack arg is array index
            "gtxnsas": {
                "gtxnsa": ["F", "A", "I"],  # group index on stack
                "gtxna": ["F", "T", "I"],  # no stack args
                "gtxnas": ["F", "T", "A"],  # array index on stack
            },
        },
    ),
    RenamedOpCode(
        name="arg",
        op="args",
        stack_aliases={"arg": ["N"]},
    ),
    RenamedOpCode(
        name="extract",
        op="extract3",
        stack_aliases={
            "extract": ["A", "S", "L"],
        },
    ),
    RenamedOpCode(
        name="replace",
        op="replace3",
        stack_aliases={
            "replace2": ["A", "S", "B"],
        },
    ),
    RenamedOpCode(
        name="substring",
        op="substring3",
        stack_aliases={
            "substring": ["A", "S", "E"],
        },
    ),
    RenamedOpCode(
        name="gload",
        op="gloadss",
        stack_aliases={
            "gload": ["T", "I"],
            "gloads": ["A", "I"],
        },
    ),
    RenamedOpCode(
        name="gaid",
        op="gaids",
        stack_aliases={"gaid": ["T"]},
    ),
    RenamedOpCode(
        name="exit",
        op="return",
    ),
]

EXCLUDED_OPCODES = {
    # low level flow control
    "bnz",
    "bz",
    "b",
    "callsub",
    "retsub",
    "proto",
    "switch",
    "match",
    # low level stack manipulation
    "intc",
    *[f"intc_{i}" for i in range(4)],
    "bytec",
    *[f"bytec_{i}" for i in range(4)],
    "pushbytes",
    "pushbytess",
    "pushint",
    "pushints",
    "frame_dig",
    "frame_bury",
    "bury",
    "cover",
    "dig",
    "dup",
    "dup2",
    "dupn",
    "pop",
    "popn",
    "swap",
    "uncover",
    # program scratch slot read/modification (for current program)
    "load",
    "loads",
    "store",
    "stores",
    # maninuplates what other low level ops point to
    "intcblock",
    "bytecblock",
    # would require a TypeVar and can be done with ternary instead
    "select",
    # implicit immediates, covered by optimiser and/or assembler
    "arg_0",
    "arg_1",
    "arg_2",
    "arg_3",
}


@attrs.define
class TypedName:
    name: str
    type: StackType | ImmediateKind | str  # noqa: A003
    doc: str | None


@attrs.define
class FunctionDef:
    name: str
    doc: list[str]
    args: list[TypedName] = attrs.field(factory=list)
    returns: list[TypedName] = attrs.field(factory=list)
    op_mappings: list[FunctionOpMapping] = attrs.field(factory=list)

    @property
    def has_any_arg(self) -> bool:
        return any(r.type == StackType.any for r in self.args)

    @property
    def has_any_return(self) -> bool:
        return any(r.type == StackType.any for r in self.returns)


@attrs.define
class ClassDef:
    name: str
    methods: list[FunctionDef]

    @property
    def has_any_methods(self) -> bool:
        return any(m.has_any_return for m in self.methods)


def main() -> None:
    spec_path = VCS_ROOT / "langspec.puya.json"

    lang_spec_json = json.loads(spec_path.read_text(encoding="utf-8"))
    lang_spec = LanguageSpec.from_json(lang_spec_json)

    function_defs = list[FunctionDef]()
    class_defs = list[ClassDef]()
    enums_to_build = dict[str, bool]()
    for op in lang_spec.ops.values():
        if is_simple_op(op):
            overriding_immediate = get_overriding_immediate(op)
            if overriding_immediate:
                class_defs.append(
                    build_class_from_overriding_immediate(lang_spec, op, overriding_immediate, [])
                )
            else:
                for immediate in op.immediate_args:
                    if immediate.immediate_type == ImmediateKind.arg_enum and (
                        immediate.modifies_stack_input is None
                        and immediate.modifies_stack_output is None
                    ):
                        assert immediate.arg_enum is not None
                        enums_to_build[immediate.arg_enum] = True
                function_defs.extend(build_operation_methods(op, op.name, []))
        else:
            logger.info(f"Ignoring: {op.name}")
    for group in OPCODE_GROUPS:
        match group:
            case MergedOpCodes() as merged:
                class_defs.append(build_merged_ops(lang_spec, merged))
            case GroupedOpCodes() as grouped:
                class_defs.append(build_grouped_ops(lang_spec, grouped))
            case RenamedOpCode() as aliased:
                function_defs.extend(build_aliased_ops(lang_spec, aliased))
            case _:
                raise Exception("Unexpected op code group")
    function_defs.sort(key=lambda x: x.name)
    class_defs.sort(key=lambda x: x.name)

    enum_names = list(enums_to_build.keys())
    output_stub(lang_spec, enum_names, function_defs, class_defs)
    output_ast_gen(lang_spec, enum_names, function_defs, class_defs)


def sub_types(type_name: StackType, *, covariant: bool) -> list[str]:
    bytes_ = [CLS_BYTES, *BYTES_LITERALS] if covariant else [CLS_BYTES]
    uint64 = [CLS_UINT64, UINT64_LITERAL] if covariant else [CLS_UINT64]
    bigint = [CLS_BIGINT] if covariant else [CLS_BIGINT]
    boolean = ["bool"]
    account = [CLS_ACCOUNT]
    sub_types = {
        StackType.bytes: bytes_,
        StackType.bytes_32: bytes_ + account if covariant else account,
        StackType.uint64: uint64,
        StackType.bool: boolean + uint64 if covariant else boolean,
        StackType.any: bytes_ + uint64,
        StackType.box_name: bytes_,
        StackType.address: account,
        StackType.address_or_index: account + uint64,
        StackType.bigint: bigint,
    }

    try:
        return sub_types[type_name]
    except KeyError as ex:
        raise NotImplementedError(
            f"Could not map stack type {type_name} to an puyapy type:" + type_name
        ) from ex


def sub_type(type_name: StackType, *, covariant: bool) -> str:
    return " | ".join(sub_types(type_name, covariant=covariant))


def is_simple_op(op: Op) -> bool:
    if (
        op.name in EXCLUDED_OPCODES
        or any(g.includes_op(op.name) for g in OPCODE_GROUPS)  # handled separately
        or not op.name.isidentifier()
        or keyword.iskeyword(op.name)  # TODO: maybe consider issoftkeyword too?
        or op.name in dir(builtins)
    ):
        return False
    return True


def immediate_kind_to_type(kind: ImmediateKind) -> type:
    match kind:
        case ImmediateKind.uint8 | ImmediateKind.int8 | ImmediateKind.uint64:
            return int
        case ImmediateKind.bytes:
            return bytes
        case ImmediateKind.arg_enum:
            return str
        case _:
            raise Exception(f"Unexpected ImmediateKind: {kind}")


def get_python_type(
    typ: StackType | ImmediateKind | str, *, covariant: bool, any_as: str | None
) -> str:
    match typ:
        case StackType() as stack_type:
            if any_as and stack_type == StackType.any:
                return any_as
            return sub_type(stack_type, covariant=covariant)
        case ImmediateKind() as immediate_kind:
            return immediate_kind_to_type(immediate_kind).__name__
        case _:
            return typ


def build_stub(
    function: FunctionDef,
    prefix: str = "",
    *,
    add_cls_arg: bool = False,
    any_input_as: str | None = None,
    any_output_as: str | None = None,
) -> Iterable[str]:
    signature = list[str]()
    doc = function.doc[:]
    signature.append(f"def {function.name}(")
    args = list[str]()
    if add_cls_arg:
        args.append("cls")
    for arg in function.args:
        python_type = get_python_type(arg.type, covariant=True, any_as=any_input_as)
        args.append(f"{arg.name}: {python_type}")
        if arg.doc:
            doc.append(f":param {python_type} {arg.name}: {arg.doc}")
    if function.args:
        args.append("/")  # TODO: remove once we support kwargs
    signature.append(", ".join(args))

    return_types = [
        get_python_type(ret.type, covariant=False, any_as=any_output_as)
        for ret in function.returns
    ]
    return_docs = [r.doc for r in function.returns if r.doc is not None]
    match return_types:
        case []:
            returns = "None"
        case [returns]:
            pass
        case _:
            returns = f"tuple[{', '.join(return_types)}]"
    if return_docs:
        doc.append(f":returns {returns}: {return_docs[0]}")
        doc.extend(return_docs[1:])
    signature.append(f") -> {returns}:")

    body = list[str]()
    if doc:
        body.append('"""')
        body.extend(doc)
        body.append('"""')
    else:
        body.append("...")

    yield prefix + "".join(signature)
    yield from [textwrap.indent(line, prefix=prefix + INDENT) for line in body]


def build_stub_class(klass: ClassDef) -> Iterable[str]:
    decorator: str
    if klass.has_any_methods:
        decorator = "@classmethod"
        yield f"class _{klass.name}(Generic[_T, _TLiteral]):"
    else:
        decorator = "@staticmethod"
        yield f"class {klass.name}:"
    for method in klass.methods:
        yield INDENT + decorator
        yield from build_stub(
            method,
            prefix=INDENT,
            add_cls_arg=klass.has_any_methods,
            any_input_as="_T | _TLiteral" if klass.has_any_methods else None,
            any_output_as="_T" if klass.has_any_methods else None,
        )
        yield ""
    if klass.has_any_methods:
        yield f"{klass.name}{CLS_BYTES} = _{klass.name}[{', '.join([CLS_BYTES, *BYTES_LITERALS])}]"
        yield f"{klass.name}{CLS_UINT64} = _{klass.name}[{CLS_UINT64}, {UINT64_LITERAL}]"


def _get_modified_stack_value(alias: Op) -> StackValue:
    immediate = get_overriding_immediate(alias)
    assert immediate
    if immediate.modifies_stack_input is not None:
        return alias.stack_inputs[immediate.modifies_stack_input]
    else:
        assert immediate.modifies_stack_output is not None
        return alias.stack_outputs[immediate.modifies_stack_output]


AliasT: typing.TypeAlias = tuple[Op, list[str]]


def build_class_from_overriding_immediate(
    spec: LanguageSpec,
    op: Op,
    immediate: Immediate,
    aliases: list[AliasT],
) -> ClassDef:
    assert immediate.arg_enum
    logger.info(f"Using overriding immediate for {op.name}")

    immediate_arg_index = op.immediate_args.index(immediate)
    immediate_python_name = immediate.name.lower()
    arg_enum_values = spec.arg_enums[immediate.arg_enum]

    # copy inputs so they can be mutated safely
    op = copy.deepcopy(op)
    aliases = copy.deepcopy(aliases)

    # obtain a list of stack values that will be modified for each enum
    stacks_to_modify = [_get_modified_stack_value(o) for o, _ in [(op, None), *aliases]]

    # build a method for each arg enum value
    methods = list[FunctionDef]()
    for value in arg_enum_values:
        stack_type = value.stack_type
        assert stack_type

        for stack_to_modify in stacks_to_modify:
            stack_to_modify.stack_type = stack_type
            stack_to_modify.doc = value.doc

        method = build_operation_method(op, snake_case(value.name), aliases)

        # remove enum arg from signature
        arg = method.args.pop(immediate_arg_index)
        assert arg.name == immediate_python_name

        for op_mapping in method.op_mappings:
            # replace immediate reference to arg enum with a constant enum value
            new_immediates = list[str | ArgMapping]()
            for arg_mapping in op_mapping.immediates:
                if (
                    isinstance(arg_mapping, ArgMapping)
                    and arg_mapping.arg_name == immediate_python_name
                ):
                    new_immediates.append(value.name)
                else:
                    new_immediates.append(arg_mapping)
            op_mapping.immediates = new_immediates

        methods.append(method)

    return ClassDef(name=get_python_enum_class(op.name), methods=methods)


def get_op_doc(op: Op) -> list[str]:
    doc = op.doc[:]
    if op.groups:
        doc.append("")
        doc.append("Groups: " + ", ".join(op.groups))

    teal = " ".join([op.name] + [i.name for i in op.immediate_args])
    stack_before = ", ".join(["..."] + [a.name for a in op.stack_inputs])
    stack_after = ", ".join(["..."] + [a.name for a in op.stack_outputs])

    doc.append("")
    doc.append(f"Stack: [{stack_before}] -> [{stack_after}]")
    doc.append(f"TEAL: {teal}")

    return doc


def map_typed_names(
    values: Iterable[StackValue], replace_any_with: StackType | None = None
) -> Iterable[TypedName]:
    yield from (
        TypedName(
            name=arg.name.lower(),
            type=replace_any_with
            if arg.stack_type == StackType.any and replace_any_with
            else arg.stack_type,
            doc=arg.doc,
        )
        for arg in values
    )


def get_python_enum_class(arg_enum: str) -> str:
    return snake_case(arg_enum).replace("_", " ").title().replace(" ", "")


def get_op_args(op: Op) -> Iterable[TypedName]:
    for immediate in op.immediate_args:
        arg_type: ImmediateKind | str = immediate.immediate_type
        if immediate.immediate_type == ImmediateKind.arg_enum:
            assert immediate.arg_enum, "Arg enum expected"
            arg_type = get_python_enum_class(immediate.arg_enum)

        yield TypedName(
            name=immediate.name.lower(),
            type=arg_type,
            doc=immediate.doc,
        )

    yield from map_typed_names(op.stack_inputs)


def get_op_returns(op: Op, replace_any_with: StackType | None) -> Iterable[TypedName]:
    if op.halts:
        yield TypedName(name="", type="Never", doc=None)
    else:
        yield from map_typed_names(op.stack_outputs, replace_any_with=replace_any_with)


def get_overriding_immediate(op: Op) -> Immediate | None:
    return next(
        (
            immediate
            for immediate in op.immediate_args
            if immediate.modifies_stack_input is not None
            or immediate.modifies_stack_output is not None
        ),
        None,
    )


def build_enum(spec: LanguageSpec, arg_enum: str) -> Iterable[str]:
    values = spec.arg_enums[arg_enum]
    enum_name = get_python_enum_class(arg_enum)
    yield f"class {enum_name}(enum.StrEnum):"
    for value in values:
        yield f"{INDENT}{value.name} = enum.auto()"
    yield ""


def get_wtype_or_type(typ: str) -> wtypes.WType | type:
    return CLS_MAPPING[typ]


def get_wtype(typ: str) -> wtypes.WType:
    wtype = get_wtype_or_type(typ)
    assert isinstance(wtype, wtypes.WType), f"{wtype} is not a WType"
    return wtype


def build_function_op_mapping(
    op: Op,
    arg_map: list[str],
    signature_args: list[TypedName],
    any_as: StackType | None = None,
) -> FunctionOpMapping:
    if arg_map:
        arg_name_map = {n: signature_args[idx].name for idx, n in enumerate(arg_map)}
    else:
        arg_name_map = {n.name.upper(): n.name for n in signature_args}
    return FunctionOpMapping(
        op_code=op.name,
        immediates=[
            ArgMapping(
                arg_name=arg_name_map[arg.name],
                allowed_types=[immediate_kind_to_type(arg.immediate_type)],
            )
            for arg in op.immediate_args
        ],
        stack_inputs=[
            ArgMapping(
                arg_name=arg_name_map[arg.name],
                allowed_types=[
                    get_wtype_or_type(typ)
                    for typ in sub_types(
                        any_as if arg.stack_type == StackType.any and any_as else arg.stack_type,
                        covariant=True,
                    )
                ],
            )
            for arg in op.stack_inputs
        ],
        stack_outputs=[
            get_wtype(
                sub_type(
                    any_as if o.stack_type == StackType.any and any_as else o.stack_type,
                    covariant=False,
                )
            )
            for o in op.stack_outputs
        ],
    )


def build_operation_method(
    op: Op, op_function_name: str, aliases: list[AliasT], replace_any_with: StackType | None = None
) -> FunctionDef:
    doc = get_op_doc(op)
    doc.append("")
    proto_function = FunctionDef(name=op_function_name, doc=doc)
    proto_function.args.extend(get_op_args(op))
    proto_function.returns.extend(get_op_returns(op, replace_any_with=replace_any_with))
    proto_function.op_mappings = [
        build_function_op_mapping(*alias, proto_function.args, any_as=replace_any_with)
        for alias in [(op, list[str]()), *aliases]
    ]
    return proto_function


def build_operation_methods(
    op: Op, op_function_name: str, aliases: list[AliasT]
) -> Iterable[FunctionDef]:
    logger.info(f"Mapping {op.name} to {op_function_name}")

    def has_stack_any(stack: list[StackValue]) -> bool:
        return any(s.stack_type == StackType.any for s in stack)

    has_any_output = has_stack_any(op.stack_outputs)
    # has_any_input = has_stack_any(op.stack_inputs)
    if has_any_output:  # and not has_any_input:
        logger.info(f"Found any output for {op.name}")
        yield build_operation_method(
            op,
            op_function_name + f"_{CLS_BYTES}".lower(),
            aliases,
            replace_any_with=StackType.bytes,
        )
        yield build_operation_method(
            op,
            op_function_name + f"_{CLS_UINT64}".lower(),
            aliases,
            replace_any_with=StackType.uint64,
        )
    else:
        yield build_operation_method(op, op_function_name, aliases)


def build_aliased_ops(spec: LanguageSpec, group: RenamedOpCode) -> Iterable[FunctionDef]:
    op = spec.ops[group.op]
    aliases = [
        (spec.ops[stack_alias], arg_map) for stack_alias, arg_map in group.stack_aliases.items()
    ]
    methods = build_operation_methods(op, group.name, aliases)
    return methods


def build_merged_ops(spec: LanguageSpec, group: MergedOpCodes) -> ClassDef:
    merge_methods = dict[str, FunctionDef]()

    for other_op_name, alias_dict in group.ops.items():
        aliases = [(spec.ops[alias_op], arg_map) for alias_op, arg_map in alias_dict.items()]
        other_op = spec.ops[other_op_name]
        overriding_immediate = get_overriding_immediate(other_op)
        assert overriding_immediate
        other_class = build_class_from_overriding_immediate(
            spec, other_op, overriding_immediate, aliases
        )
        for method in other_class.methods:
            merge_methods[method.name] = method

    methods = list(merge_methods.values())
    return ClassDef(
        name=get_python_enum_class(group.name),
        methods=methods,
    )


def build_grouped_ops(spec: LanguageSpec, group: GroupedOpCodes) -> ClassDef:
    methods = list[FunctionDef]()
    for rename_op_name, python_name in group.ops.items():
        rename_op = spec.ops[rename_op_name]
        rename_immediate = get_overriding_immediate(rename_op)
        if rename_immediate:
            rename_class = build_class_from_overriding_immediate(
                spec, rename_op, rename_immediate, aliases=[]
            )
            # when grouping an op with immediate overrides, treat python_name as a prefix
            for method in rename_class.methods:
                method.name = f"{python_name}_{method.name}"
            methods.extend(rename_class.methods)
        else:
            methods.extend(build_operation_methods(rename_op, python_name, aliases=[]))

    class_def = ClassDef(
        name=get_python_enum_class(group.name),
        methods=methods,
    )
    return class_def


def build_wtype(wtype: wtypes.WType) -> str:
    match wtype:
        case wtypes.bool_wtype:
            return "wtypes.bool_wtype"
        case wtypes.uint64_wtype:
            return "wtypes.uint64_wtype"
        case wtypes.account_wtype:
            return "wtypes.account_wtype"
        case wtypes.bytes_wtype:
            return "wtypes.bytes_wtype"
        case wtypes.biguint_wtype:
            return "wtypes.biguint_wtype"
    raise ValueError("Unexpected wtype")


def build_arg_mapping(arg_mapping: ArgMapping) -> Iterable[str]:
    yield "ArgMapping("
    yield f'    arg_name="{arg_mapping.arg_name}",'
    yield "    allowed_types=["
    for allowed_type in arg_mapping.allowed_types:
        if isinstance(allowed_type, wtypes.WType):
            yield build_wtype(allowed_type)
        else:
            yield allowed_type.__name__
        yield ","
    yield "    ],"
    yield ")"


def build_op_specification_body(name_suffix: str, function: FunctionDef) -> Iterable[str]:
    yield f'    "puyapy._gen.{name_suffix}": ['
    for op_mapping in function.op_mappings:
        yield "FunctionOpMapping("
        yield f'    op_code="{op_mapping.op_code}",'
        yield "    immediates=["
        for immediate in op_mapping.immediates:
            if isinstance(immediate, str):
                yield f'        "{immediate}",'
            else:
                yield from build_arg_mapping(immediate)
                yield ","
        yield "    ],"
        yield "    stack_inputs=["
        for stack_input in op_mapping.stack_inputs:
            yield from build_arg_mapping(stack_input)
            yield ","
        yield "    ],"
        yield "    stack_outputs=["
        for stack_output in op_mapping.stack_outputs:
            yield build_wtype(stack_output)
            yield ","
        yield "    ],"
        yield "),"
    yield "    ],"


def build_ast_gen(
    lang_spec: LanguageSpec,
    enums: list[str],
    function_ops: list[FunctionDef],
    class_ops: list[ClassDef],
) -> Iterable[str]:
    yield "from puya.awst import wtypes"
    yield "from puya.awst_build.intrinsic_models import ArgMapping, FunctionOpMapping"
    yield ""
    yield "ENUM_CLASSES = {"
    for enum_name in enums:
        yield f'    "puyapy._gen.{get_python_enum_class(enum_name)}": {{'
        for enum_value in lang_spec.arg_enums[enum_name]:
            # enum names currently match enum immediate values
            yield f'    "{enum_value.name}": "{enum_value.name}",'
        yield "     },"
    yield "}"
    yield ""
    yield "STUB_TO_AST_MAPPER = {"
    for function_op in function_ops:
        yield from build_op_specification_body(function_op.name, function_op)

    for class_op in class_ops:
        for method in class_op.methods:
            yield from build_op_specification_body(f"{class_op.name}.{method.name}", method)

    yield "}"


def output_stub(
    lang_spec: LanguageSpec,
    enums: list[str],
    function_ops: list[FunctionDef],
    class_ops: list[ClassDef],
) -> None:
    stub: list[str] = [
        "import enum",
        "from typing import Never",
        "",
        f"from puyapy import {CLS_ACCOUNT}, {CLS_BIGINT}, {CLS_BYTES}, {CLS_UINT64}",
    ]

    for arg_enum in enums:
        stub.extend(build_enum(lang_spec, arg_enum))

    for function in function_ops:
        if function.has_any_return and function.has_any_arg:
            stub.extend(build_stub(function, any_input_as="_T", any_output_as="_T"))
        elif function.has_any_return:
            # functions with any returns should have already been transformed
            raise Exception(f"Unexpected function {function.name} with any return")
        else:
            stub.extend(build_stub(function))

    for class_op in class_ops:
        stub.extend(build_stub_class(class_op))

    stub_out_path = VCS_ROOT / "src" / "puyapy-stubs" / "_gen.pyi"
    stub_out_path.write_text("\n".join(stub), encoding="utf-8")
    subprocess.run(["black", str(stub_out_path)], check=True, cwd=VCS_ROOT)


def output_ast_gen(
    lang_spec: LanguageSpec,
    enums: list[str],
    function_ops: list[FunctionDef],
    class_ops: list[ClassDef],
) -> None:
    ast_gen = build_ast_gen(lang_spec, enums, function_ops, class_ops)

    ast_gen_path = VCS_ROOT / "src" / "puya" / "awst_build" / "intrinsic_data.py"
    ast_gen_path.write_text("\n".join(ast_gen), encoding="utf-8")
    subprocess.run(["black", str(ast_gen_path)], check=True, cwd=VCS_ROOT)


def snake_case(s: str) -> str:
    s = s.replace("-", " ")
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return re.sub(r"[-\s]", "_", s).lower()


if __name__ == "__main__":
    main()
