#!/usr/bin/env python3
import builtins
import copy
import json
import keyword
import subprocess
import textwrap
import typing
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.algo_constants import SUPPORTED_AVM_VERSIONS
from puyapy.awst_build import pytypes
from puyapy.awst_build.intrinsic_models import FunctionOpMapping, OpMappingWithOverloads
from puyapy.awst_build.utils import snake_case
from scripts.transform_lang_spec import (
    ArgEnum,
    Immediate,
    ImmediateKind,
    LanguageSpec,
    Op,
    StackType,
    StackValue,
)

logger = log.get_logger(__name__)
INDENT = " " * 4
VCS_ROOT = Path(__file__).parent.parent
MIN_SUPPORTED_VERSION = min(SUPPORTED_AVM_VERSIONS)

PYTHON_ENUM_CLASS = {
    "Mimc Configurations": "MiMCConfigurations",
}
PYTYPE_TO_LITERAL: dict[pytypes.PyType, pytypes.LiteralOnlyType | None] = {
    pytypes.BytesType: pytypes.BytesLiteralType,
    pytypes.UInt64Type: pytypes.IntLiteralType,
    pytypes.AccountType: None,  # pytypes.StrLiteralType, # TODO: should we enable this?
    pytypes.BigUIntType: pytypes.IntLiteralType,
    pytypes.BoolType: None,  # already a Python type
    pytypes.ApplicationType: pytypes.IntLiteralType,
    pytypes.AssetType: pytypes.IntLiteralType,
    pytypes.TransactionTypeType: None,
    pytypes.OnCompleteActionType: None,
}
PYTYPE_REPR = {
    value: f"pytypes.{key}"
    for key, value in pytypes.__dict__.items()
    if isinstance(value, pytypes.PyType)
}
STACK_TYPE_MAPPING: dict[StackType, Sequence[pytypes.PyType]] = {
    StackType.address_or_index: [pytypes.AccountType, pytypes.UInt64Type],
    StackType.application: [pytypes.ApplicationType, pytypes.UInt64Type],
    StackType.asset: [pytypes.AssetType, pytypes.UInt64Type],
    StackType.bytes: [pytypes.BytesType],
    StackType.bytes_8: [pytypes.BytesType],
    StackType.bytes_32: [pytypes.BytesType],
    StackType.bytes_33: [pytypes.BytesType],
    StackType.bytes_64: [pytypes.BytesType],
    StackType.bytes_80: [pytypes.BytesType],
    StackType.bytes_1232: [pytypes.BytesType],
    StackType.bytes_1793: [pytypes.BytesType],
    StackType.bool: [pytypes.BoolType, pytypes.UInt64Type],
    StackType.uint64: [pytypes.UInt64Type],
    StackType.any: [pytypes.BytesType, pytypes.UInt64Type],
    StackType.box_name: [pytypes.BytesType],  # TODO: should this be another type..?
    StackType.address: [pytypes.AccountType],
    StackType.bigint: [pytypes.BigUIntType],
    StackType.state_key: [pytypes.BytesType],  # TODO: should this be another type..?
}

BYTES_LITERAL = "bytes"
UINT64_LITERAL = "int"
STUB_NAMESPACE = "op"
ALGORAND_OP_URL = "https://dev.algorand.co/reference/algorand-teal/opcodes/"


class OpCodeGroup(typing.Protocol):
    def handled_ops(self) -> Iterator[str]: ...


@attrs.define(kw_only=True)
class RenamedOpCode(OpCodeGroup):
    name: str
    stack_aliases: dict[str, list[str]] = attrs.field(factory=dict)
    """ops that are aliases for other ops that take stack values instead of immediates"""
    op: str

    def handled_ops(self) -> Iterator[str]:
        yield self.op
        yield from self.stack_aliases.keys()


@attrs.define(kw_only=True)
class MergedOpCodes(OpCodeGroup):
    name: str
    doc: str
    ops: dict[str, dict[str, list[str]]]

    def handled_ops(self) -> Iterator[str]:
        for op, aliases in self.ops.items():
            yield op
            yield from aliases.keys()


@attrs.define(kw_only=True)
class GroupedOpCodes(OpCodeGroup):
    name: str
    """ops that are aliases for other ops that take stack values instead of immediates"""
    doc: str
    ops: dict[str, str] = attrs.field(factory=dict)
    """ops to include in group, mapped to their new name"""

    def handled_ops(self) -> Iterator[str]:
        yield from self.ops.keys()


GROUPED_OP_CODES = [
    GroupedOpCodes(
        name="AppGlobal",
        doc="Get or modify Global app state",
        ops={
            "app_global_get": "get",
            "app_global_get_ex": "get_ex",
            "app_global_del": "delete",
            "app_global_put": "put",
        },
    ),
    GroupedOpCodes(
        name="Scratch",
        doc="Load or store scratch values",
        ops={"loads": "load", "stores": "store"},
    ),
    GroupedOpCodes(
        name="AppLocal",
        doc="Get or modify Local app state",
        ops={
            "app_local_get": "get",
            "app_local_get_ex": "get_ex",
            "app_local_del": "delete",
            "app_local_put": "put",
        },
    ),
    GroupedOpCodes(
        name="Box",
        doc="Get or modify box state",
        ops={
            "box_create": "create",
            "box_del": "delete",
            "box_extract": "extract",
            "box_get": "get",
            "box_len": "length",
            "box_put": "put",
            "box_replace": "replace",
            "box_resize": "resize",
            "box_splice": "splice",
        },
    ),
    GroupedOpCodes(
        name="EllipticCurve",
        doc="Elliptic Curve functions",
        ops={
            "ec_add": "add",
            "ec_map_to": "map_to",
            "ec_multi_scalar_mul": "scalar_mul_multi",
            "ec_pairing_check": "pairing_check",
            "ec_scalar_mul": "scalar_mul",
            "ec_subgroup_check": "subgroup_check",
        },
    ),
    GroupedOpCodes(
        name="ITxnCreate",
        doc="Create inner transactions",
        ops={
            "itxn_begin": "begin",
            "itxn_next": "next",
            "itxn_submit": "submit",
            "itxn_field": "set",
        },
    ),
]
MERGED_OP_CODES = [
    MergedOpCodes(
        name="Txn",
        doc="Get values for the current executing transaction",
        ops={
            "txn": {},
            "txnas": {
                "txna": ["F", "I"],
            },
        },
    ),
    MergedOpCodes(
        name="GTxn",
        doc="Get values for transactions in the current group",
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
    MergedOpCodes(
        name="ITxn",
        doc="Get values for the last inner transaction",
        ops={
            "itxn": {},
            "itxnas": {
                "itxna": ["F", "I"],
            },
        },
    ),
    MergedOpCodes(
        name="GITxn",
        doc="Get values for inner transaction in the last group submitted",
        ops={
            "gitxn": {},
            "gitxnas": {
                "gitxna": ["T", "F", "I"],
            },
        },
    ),
    MergedOpCodes(
        name="Global",
        doc="Get Global values",
        ops={"global": {}},
    ),
]
RENAMED_OP_CODES = [
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
    # implicit immediates, covered by optimiser and/or assembler
    "arg_0",
    "arg_1",
    "arg_2",
    "arg_3",
    # have a higher level abstraction that supersedes it
    "log",
}


# which ops to treat as properties in the generated stubs
PROPERTY_OPS = {
    "global": {"exclude": ["opcode_budget"]},
    "txn": {"exclude": list[str]()},
}


@attrs.define
class TypedName:
    name: str
    type: StackType | ImmediateKind | str
    doc: str | None


@attrs.define(kw_only=True)
class FunctionDef:
    name: str
    doc: list[str]
    is_property: bool
    args: list[TypedName] = attrs.field(factory=list)
    return_docs: list[str] = attrs.field(factory=list)
    op_mapping: OpMappingWithOverloads
    min_avm_version: int


@attrs.define
class ClassDef:
    name: str
    doc: str
    methods: list[FunctionDef] = attrs.field()
    ops: list[str]


def main() -> None:
    spec_path = VCS_ROOT / "langspec.puya.json"

    lang_spec_json = json.loads(spec_path.read_text(encoding="utf-8"))
    lang_spec = LanguageSpec.from_json(lang_spec_json)

    non_simple_ops = {
        *EXCLUDED_OPCODES,
        *dir(builtins),
        *keyword.kwlist,  # TODO: maybe consider softkwlist too?
    }
    function_defs = list[FunctionDef]()
    class_defs = list[ClassDef]()
    enums_to_build = dict[str, bool]()

    for merged in MERGED_OP_CODES:
        non_simple_ops.update(merged.handled_ops())
        class_defs.append(build_merged_ops(lang_spec, merged))
    for grouped in GROUPED_OP_CODES:
        non_simple_ops.update(grouped.handled_ops())
        class_defs.append(build_grouped_ops(lang_spec, grouped, enums_to_build))
    for aliased in RENAMED_OP_CODES:
        function_defs.extend(build_aliased_ops(lang_spec, aliased))
        non_simple_ops.update(aliased.handled_ops())

    for op in lang_spec.ops.values():
        if op.name in non_simple_ops or not op.name.isidentifier():
            logger.info(f"Ignoring: {op.name}")
            continue
        overriding_immediate = get_overriding_immediate(op)
        if overriding_immediate:
            class_defs.append(
                build_class_from_overriding_immediate(
                    lang_spec,
                    op,
                    class_name=get_python_enum_class(op.name),
                    class_doc=" ".join(op.doc),
                    immediate=overriding_immediate,
                    aliases=[],
                )
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

    function_defs.sort(key=lambda x: x.name)
    class_defs.sort(key=lambda x: x.name)

    enum_names = list(enums_to_build.keys())
    output_stub(lang_spec, enum_names, function_defs, class_defs)
    output_awst_data(lang_spec, enum_names, function_defs, class_defs)


def sub_types(type_name: StackType, *, covariant: bool) -> Sequence[pytypes.PyType]:
    try:
        typs = STACK_TYPE_MAPPING[type_name]
    except KeyError as ex:
        raise NotImplementedError(
            f"Could not map stack type {type_name} to an algopy type"
        ) from ex
    else:
        last_index = None if covariant else 1
        return typs[:last_index]


def immediate_kind_to_type(kind: ImmediateKind) -> type[int | str]:
    match kind:
        case ImmediateKind.uint8 | ImmediateKind.int8 | ImmediateKind.varuint:
            return int
        case ImmediateKind.arg_enum:
            return str
        case _:
            raise ValueError(f"Unexpected ImmediateKind: {kind}")


def get_python_type(
    typ: StackType | ImmediateKind | str, *, covariant: bool, any_as: str | None
) -> str:
    match typ:
        case StackType() as stack_type:
            if any_as and stack_type == StackType.any:
                return any_as
            ptypes_ = sub_types(stack_type, covariant=covariant)
            names = [str(wt).removeprefix("algopy.") for wt in ptypes_]
            if covariant:
                for pt in ptypes_:
                    lit_t = PYTYPE_TO_LITERAL[pt]
                    if lit_t is not None:
                        lit_name = str(lit_t)
                        if lit_name not in names:
                            names.append(lit_name)
            return " | ".join(names)
        case ImmediateKind() as immediate_kind:
            return immediate_kind_to_type(immediate_kind).__name__
        case _:
            return typ


def build_method_stub(function: FunctionDef, prefix: str = "") -> Iterable[str]:
    signature = list[str]()
    doc = function.doc[:]
    signature.append(f"def {function.name}(")
    args = list[str]()
    for arg in function.args:
        python_type = get_python_type(arg.type, covariant=True, any_as=None)
        args.append(f"{arg.name}: {python_type}")
        if arg.doc:
            doc.append(f":param {python_type} {arg.name}: {arg.doc}")
    if function.args:
        args.append("/")  # TODO: remove once we support kwargs
    signature.append(", ".join(args))

    return_docs = function.return_docs
    returns = pytype_stub_repr(function.op_mapping.result)
    if return_docs:
        if doc:
            doc.append(f":returns {returns}: {return_docs[0]}")
            doc.extend(return_docs[1:])
        else:
            doc = return_docs
    signature.append(f") -> {returns}:")
    teal_ops = sorted({op.op_code for op in function.op_mapping.overloads})
    teal_op_desc = ", ".join(_get_algorand_doc(teal_op) for teal_op in teal_ops)
    doc.append("")
    doc.append(f"Native TEAL opcode: {teal_op_desc}")
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
    ops = [f"{_get_algorand_doc(op)}" for op in klass.ops]
    docstring = "\n".join(
        [
            INDENT + '"""',
            INDENT + klass.doc,
            INDENT + f"Native TEAL op{'s' if len(ops) > 1 else ''}: {', '.join(ops)}",
            INDENT + '"""',
        ]
    )
    method_preamble = f"{INDENT}@staticmethod"
    yield f"class {klass.name}:"
    yield docstring
    for method in klass.methods:
        if method.is_property:
            yield from build_class_var_stub(method, INDENT)
        else:
            yield method_preamble
            yield from build_method_stub(method, prefix=INDENT)
        yield ""


def build_class_var_stub(function: FunctionDef, indent: str) -> Iterable[str]:
    returns = pytype_stub_repr(function.op_mapping.result)
    return_docs = function.return_docs
    doc = return_docs if return_docs else function.doc[:]
    _maybe_add_min_version_doc(doc, function.min_avm_version)
    yield f"{indent}{function.name}: typing.Final[{returns}] = ..."
    yield f'{indent}"""'
    for doc_line in doc:
        yield f"{indent}{doc_line}"
    yield f'{indent}"""'


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
    class_name: str,
    class_doc: str,
    immediate: Immediate,
    aliases: list[AliasT],
) -> ClassDef:
    assert immediate.arg_enum
    logger.info(f"Using overriding immediate for {op.name}")

    arg_enum_values = spec.arg_enums[immediate.arg_enum]

    # copy inputs so they can be mutated safely
    op = copy.deepcopy(op)
    aliases = copy.deepcopy(aliases)

    # obtain a list of stack values that will be modified for each enum
    stacks_to_modify = [_get_modified_stack_value(o) for o, _ in [(op, None), *aliases]]

    # build a method for each arg enum value
    methods = list[FunctionDef]()
    class_ops = {op.name}
    for value in arg_enum_values:
        stack_type = value.stack_type
        assert stack_type

        for stack_to_modify in stacks_to_modify:
            stack_to_modify.stack_type = stack_type
            stack_to_modify.doc = value.doc

        method = build_operation_method(
            op, snake_case(value.name), aliases, const_immediate_value=(immediate, value)
        )
        # some enums are reused across ops, so need to take the max minimum of op and enum version
        method.min_avm_version = max(op.min_avm_version, value.min_avm_version)
        _maybe_add_min_version_doc(method.doc, method.min_avm_version)

        for op_mapping in method.op_mapping.overloads:
            class_ops.add(op_mapping.op_code)

        methods.append(method)

    return ClassDef(name=class_name, doc=class_doc, methods=methods, ops=sorted(class_ops))


def get_op_doc(op: Op) -> list[str]:
    doc = [d.replace("\\", "\\\\") for d in op.doc]
    _maybe_add_min_version_doc(doc, op.min_avm_version)
    return doc


def get_python_enum_class(arg_enum: str) -> str:
    try:
        return PYTHON_ENUM_CLASS[arg_enum]
    except KeyError:
        pass
    # don't change acronyms
    if arg_enum.isupper():
        return arg_enum
    return snake_case(arg_enum).replace("_", " ").title().replace(" ", "")


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
    yield f"class {enum_name}(str):"
    yield f'{INDENT}"""Available values for the `{arg_enum}` enum"""'
    for value in values:
        yield f"{INDENT}{value.name}: {enum_name} = ..."
        enum_doc = []
        if value.doc:
            enum_doc.append(value.doc)
        _maybe_add_min_version_doc(enum_doc, value.min_avm_version)
        if enum_doc:
            yield f'{INDENT}"""'
            for doc_line in enum_doc:
                yield f"{INDENT}{doc_line}"
            yield f'{INDENT}"""'
    yield ""


def _maybe_add_min_version_doc(doc: list[str], version: int) -> None:
    # only output min AVM version if it is greater than our min supported version
    if version > MIN_SUPPORTED_VERSION:
        doc.append(f"Min AVM version: {version}")


def build_operation_method(
    op: Op,
    op_function_name: str,
    aliases: list[AliasT],
    const_immediate_value: tuple[Immediate, ArgEnum] | None = None,
) -> FunctionDef:
    args = []
    # python stub args can be different to mapping args, due to immediate args
    # that are inferred based on the method/property used
    function_args = []
    doc = get_op_doc(op)
    for immediate in op.immediate_args:
        arg_type: ImmediateKind | str
        if immediate.immediate_type == ImmediateKind.arg_enum:
            assert immediate.arg_enum, "Arg enum expected"
            arg_type = get_python_enum_class(immediate.arg_enum)
        else:
            arg_type = immediate.immediate_type
        im_arg = TypedName(name=immediate.name.lower(), type=arg_type, doc=immediate.doc)
        args.append(im_arg)
        if const_immediate_value and const_immediate_value[0] == immediate:
            # omit immediate arg from signature
            doc = []
        else:
            function_args.append(im_arg)
    for si in op.stack_inputs:
        stack_arg = TypedName(name=si.name.lower(), type=si.stack_type, doc=si.doc)
        args.append(stack_arg)
        function_args.append(stack_arg)

    if op.halts:
        return_docs = ["Halts program"]
    else:
        return_docs = [so.doc for so in op.stack_outputs if so.doc]

    try:
        property_op = PROPERTY_OPS[op.name]
    except KeyError:
        is_property = False
    else:
        is_property = op_function_name not in property_op["exclude"]

    if op.halts:
        result_typ = pytypes.NeverType
    else:
        # replace immediate reference to arg enum with a constant enum value
        result_ptypes = [sub_types(o.stack_type, covariant=False)[0] for o in op.stack_outputs]
        if not result_ptypes:
            result_typ = pytypes.NoneType
        elif len(op.stack_outputs) == 1:
            (result_typ,) = result_ptypes
        else:
            result_typ = pytypes.GenericTupleType.parameterise(result_ptypes, source_location=None)
        if result_typ == pytypes.UInt64Type:
            if op_function_name == "on_completion":
                result_typ = pytypes.OnCompleteActionType
            elif op_function_name == "type_enum":
                result_typ = pytypes.TransactionTypeType
    op_mappings = []
    ops_with_aliases = [(op, list[str]()), *aliases]
    for map_op, alias_args in ops_with_aliases:
        assert map_op.stack_outputs == op.stack_outputs
        if alias_args:
            # map the stack or immediate input name to the function signature position
            name_to_sig_idx = {n: idx2 for idx2, n in enumerate(alias_args)}
        else:
            name_to_sig_idx = {tn.name.upper(): idx2 for idx2, tn in enumerate(args)}
        map_immediates = list[str | int | type[str | int]]()
        map_args_map = dict[int, Sequence[pytypes.PyType] | int]()
        for idx, i_arg in enumerate(map_op.immediate_args):
            if const_immediate_value and const_immediate_value[0] == i_arg:
                map_immediates.append(const_immediate_value[1].name)
            else:
                im_typ = immediate_kind_to_type(i_arg.immediate_type)
                map_immediates.append(im_typ)
                sig_idx = name_to_sig_idx[i_arg.name]
                map_args_map[sig_idx] = idx

        for s_arg in map_op.stack_inputs:
            allowed_types = tuple(sub_types(s_arg.stack_type, covariant=True))
            sig_idx = name_to_sig_idx[s_arg.name]
            map_args_map[sig_idx] = allowed_types

        op_mappings.append(
            FunctionOpMapping(
                op_code=map_op.name,
                immediates=map_immediates,
                args=[map_args_map[k] for k in sorted(map_args_map)],
            )
        )
    proto_function = FunctionDef(
        name=op_function_name,
        doc=doc,
        is_property=is_property,
        args=function_args,
        return_docs=return_docs,
        op_mapping=OpMappingWithOverloads(
            arity=len(function_args),
            result=result_typ,
            overloads=op_mappings,
        ),
        min_avm_version=op.min_avm_version,
    )

    return proto_function


def build_operation_methods(
    op: Op, op_function_name: str, aliases: list[AliasT]
) -> Iterable[FunctionDef]:
    logger.info(f"Mapping {op.name} to {op_function_name}")

    if StackType.any in (s.stack_type for s in op.stack_outputs):
        logger.info(f"Found any output for {op.name}")
        for replace_any_with in (StackType.bytes, StackType.uint64):
            new_op = op_any_replaced(op, replace_any_with)
            new_name = f"{op_function_name}_{replace_any_with.name}"
            new_aliases = [
                (op_any_replaced(alias_op, replace_any_with), names) for alias_op, names in aliases
            ]
            yield build_operation_method(new_op, new_name, new_aliases)
    else:
        yield build_operation_method(op, op_function_name, aliases)


def op_any_replaced(op: Op, replace_any_with: StackType) -> Op:
    stack_inputs = []
    input_replaced = 0
    for si in op.stack_inputs:
        if si.stack_type != StackType.any:
            stack_inputs.append(si)
        else:
            input_replaced += 1
            stack_inputs.append(attrs.evolve(si, stack_type=replace_any_with))

    stack_outputs = []
    outputs_replaced = 0
    for so in op.stack_outputs:
        if so.stack_type != StackType.any:
            stack_outputs.append(so)
        else:
            outputs_replaced += 1
            stack_outputs.append(attrs.evolve(so, stack_type=replace_any_with))
    assert outputs_replaced == 1
    return attrs.evolve(op, stack_inputs=stack_inputs, stack_outputs=stack_outputs)


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
            spec,
            other_op,
            class_name=group.name,
            class_doc=group.doc,
            immediate=overriding_immediate,
            aliases=aliases,
        )
        for method in other_class.methods:
            merge_methods[method.name] = method

    methods = list(merge_methods.values())
    return ClassDef(name=group.name, doc=group.doc, methods=methods, ops=sorted(group.ops))


def build_grouped_ops(
    spec: LanguageSpec, group: GroupedOpCodes, enums_to_build: dict[str, bool]
) -> ClassDef:
    methods = list[FunctionDef]()
    for rename_op_name, python_name in group.ops.items():
        rename_op = spec.ops[rename_op_name]
        rename_immediate = get_overriding_immediate(rename_op)
        if rename_immediate:
            rename_class = build_class_from_overriding_immediate(
                spec,
                rename_op,
                class_name=group.name,
                class_doc=group.doc,
                immediate=rename_immediate,
                aliases=[],
            )
            # when grouping an op with immediate overrides, treat python_name as a prefix
            for method in rename_class.methods:
                method.name = f"{python_name}_{method.name}"
            methods.extend(rename_class.methods)

        else:
            methods.extend(build_operation_methods(rename_op, python_name, aliases=[]))
        for arg in rename_op.immediate_args:
            if arg.immediate_type == ImmediateKind.arg_enum and (
                arg.modifies_stack_input is None and arg.modifies_stack_output is None
            ):
                assert arg.arg_enum is not None
                enums_to_build[arg.arg_enum] = True

    class_def = ClassDef(
        name=group.name,
        doc=group.doc,
        methods=methods,
        ops=sorted(group.ops),
    )
    return class_def


def pytype_repr(typ: pytypes.PyType) -> str:
    try:
        return PYTYPE_REPR[typ]
    except KeyError:
        pass
    match typ:
        case pytypes.TupleType(items=tuple_items) if len(tuple_items) > 1:
            item_strs = [pytype_repr(item) for item in tuple_items]
            return (
                f"pytypes.GenericTupleType.parameterise("
                f"({', '.join(item_strs)}), source_location=None)"
            )
    raise ValueError(f"Unexpected pytype: {typ}")


def build_op_specification_body(function: FunctionDef) -> Iterable[str]:
    if function.is_property:
        (op_mapping,) = function.op_mapping.overloads
        (immediate,) = op_mapping.immediates
        yield (
            f"{function.name}=PropertyOpMapping("
            f"{op_mapping.op_code!r}, {immediate!r}, {pytype_repr(function.op_mapping.result)},"
            f"),"
        )
    else:
        yield f"{function.name}=OpMappingWithOverloads("
        if function.op_mapping.result is not pytypes.NoneType:
            yield f" result={pytype_repr(function.op_mapping.result)},"
        yield f" arity={function.op_mapping.arity}, "
        yield " overloads=["
        for op_mapping in function.op_mapping.overloads:
            yield f"FunctionOpMapping({op_mapping.op_code!r},"
            if op_mapping.immediates:
                yield " immediates=["
                for idx, item in enumerate(op_mapping.immediates):
                    if idx:
                        yield ", "
                    if not isinstance(item, type):
                        yield repr(item)
                    else:
                        yield item.__name__
                yield "],"
            if op_mapping.args:
                yield " args=["
                for idx, allowed_types_or_idx in enumerate(op_mapping.args):
                    if idx:
                        yield ", "
                    if isinstance(allowed_types_or_idx, int):
                        yield repr(allowed_types_or_idx)
                    else:  # noqa: PLR5501
                        if len(allowed_types_or_idx) == 1:
                            yield f"({pytype_repr(*allowed_types_or_idx)},)"
                        else:
                            yield "("
                            for idx2, allowed_type in enumerate(allowed_types_or_idx):
                                if idx2:
                                    yield ","
                                yield pytype_repr(allowed_type)
                            yield ")"
                yield "],"

            yield "),"
        yield "]"
        yield "),"


def build_awst_data(
    lang_spec: LanguageSpec,
    enums: list[str],
    function_ops: list[FunctionDef],
    class_ops: list[ClassDef],
) -> Iterable[str]:
    yield "import typing"
    yield "from collections.abc import Mapping, Sequence"
    yield "from puyapy.awst_build import pytypes"
    yield (
        "from puyapy.awst_build.intrinsic_models"
        " import FunctionOpMapping, OpMappingWithOverloads, PropertyOpMapping"
    )
    yield "ENUM_CLASSES: typing.Final[Mapping[str, Mapping[str, str]]] = dict("
    for enum_name in enums:
        yield f"{get_python_enum_class(enum_name)}=dict("
        for enum_value in lang_spec.arg_enums[enum_name]:
            # enum names currently match enum immediate values
            yield f'{enum_value.name}="{enum_value.name}",'
        yield "),"
    yield ")"
    yield ""
    yield "FUNC_TO_AST_MAPPER: typing.Final[Mapping[str, OpMappingWithOverloads]] = dict("
    for function_op in function_ops:
        yield "".join(build_op_specification_body(function_op))
    yield ")"

    yield (
        "NAMESPACE_CLASSES: "
        "typing.Final[Mapping[str, Mapping[str, PropertyOpMapping | OpMappingWithOverloads]]]"
        " = dict("
    )
    for class_op in class_ops:
        yield f"{class_op.name}=dict("
        for method in class_op.methods:
            yield "".join(build_op_specification_body(method))
        yield "),"
    yield ")"


def output_stub(
    lang_spec: LanguageSpec,
    enums: list[str],
    function_ops: list[FunctionDef],
    class_ops: list[ClassDef],
) -> None:
    references = ", ".join(
        sorted(
            str(pt).removeprefix("algopy.")
            for pt, lit_t in PYTYPE_TO_LITERAL.items()
            if str(pt).startswith("algopy.")
        )
    )
    stub: list[str] = [
        "import typing",
        "",
        f"from algopy import {references}",
    ]

    for arg_enum in enums:
        stub.extend(build_enum(lang_spec, arg_enum))

    for function in function_ops:
        stub.extend(build_method_stub(function))

    for class_op in class_ops:
        stub.extend(build_stub_class(class_op))

    stub_out_path = VCS_ROOT / "stubs" / "algopy-stubs" / f"{STUB_NAMESPACE}.pyi"
    stub_out_path.write_text("\n".join(stub), encoding="utf-8")
    subprocess.run(["ruff", "format", str(stub_out_path)], check=True, cwd=VCS_ROOT)


def pytype_stub_repr(pytype: pytypes.PyType) -> str:
    return str(pytype).replace("algopy.", "")


def output_awst_data(
    lang_spec: LanguageSpec,
    enums: list[str],
    function_ops: list[FunctionDef],
    class_ops: list[ClassDef],
) -> None:
    awst_data = build_awst_data(lang_spec, enums, function_ops, class_ops)

    awst_data_path = VCS_ROOT / "src" / "puyapy" / "awst_build" / "intrinsic_data.py"
    awst_data_path.write_text("\n".join(awst_data), encoding="utf-8")
    subprocess.run(["ruff", "format", str(awst_data_path)], check=True, cwd=VCS_ROOT)
    subprocess.run(["ruff", "check", "--fix", str(awst_data_path)], check=False, cwd=VCS_ROOT)


def _get_algorand_doc(op: str) -> str:
    return f"[`{op}`]({ALGORAND_OP_URL}#{op})"


if __name__ == "__main__":
    main()
