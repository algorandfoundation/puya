import contextlib
import enum
import json
import logging
import typing
from pathlib import Path

import attrs
import cattrs

logger = logging.getLogger(__name__)


STACK_INPUT_NAMES = "ABCDE"
STACK_OUTPUT_NAMES_FEW = "XYZ"  # 1, 2, 3
STACK_OUTPUT_NAMES_MANY = "WXYZ"  # many
# TODO: lots?


VARIABLE_SIZE_OPCODES = {
    "intcblock",
    "bytecblock",
    "pushbytes",
    "pushbytess",
    "pushint",
    "pushints",
    "switch",
    "match",
}


class NamedType(typing.TypedDict):
    """
    {
      "Name": "uint64",
      "Abbreviation": "i",
      "Bound": [
        0,
        18446744073709551615
      ],
      "AVMType": "uint64"
    },
    """

    Name: str
    Abbreviation: str
    AVMType: str


class ImmediateNote(typing.TypedDict, total=False):
    """
    {
      "Comment": "transaction field index",
      "Encoding": "uint8",
      "Name": "F",
      "Reference": "txn"
    }
    """

    Comment: str
    Encoding: str
    Name: str
    Reference: str


class Operation(typing.TypedDict, total=False):
    """
    {
      "Opcode": 0,
      "Name": "err",
      "Size": 1,
      "Doc": "Fail immediately.",
      "IntroducedVersion": 1,
      "Groups": [
        "Flow Control"
      ]
    },
    {
      "Opcode": 1,
      "Name": "sha256",
      "Args": [
        "[]byte"
      ],
      "Returns": [
        "[32]byte"
      ],
      "Size": 1,
      "Doc": "SHA256 hash of value A, yields [32]byte",
      "IntroducedVersion": 1,
      "Groups": [
        "Arithmetic"
      ]
    }
    """

    Doc: str
    Opcode: int
    Size: int
    Name: str
    IntroducedVersion: int
    Groups: list[str]
    Args: list[str]
    Returns: list[str]
    DocExtra: str
    ArgEnum: list[str]
    ArgEnumTypes: list[str]
    ImmediateNote: list[ImmediateNote]

    # the following values are not in the original langspec.json
    # these values are manually patched in during transform
    ArgEnumIsInput: bool
    Halts: bool
    # these values are output by a modified opdoc.go from go-algorand repo
    Cost: str
    ArgEnumDoc: list[str]


class AlgorandLanguageSpec(typing.TypedDict):
    NamedTypes: list[NamedType]
    Ops: list[Operation]


class StackType(enum.StrEnum):
    uint64 = enum.auto()
    bytes = "[]byte"  # noqa: A003
    bytes_32 = "[32]byte"
    bool = enum.auto()  # noqa: A003
    address = enum.auto()
    address_or_index = enum.auto()
    any = enum.auto()  # noqa: A003
    bigint = enum.auto()
    box_name = "boxName"


@attrs.define
class StackValue:
    name: str
    """Name used to refer to this value in the Op.doc"""
    stack_type: StackType
    doc: str | None = None


@attrs.define
class ArgEnum:
    name: str
    doc: str | None
    stack_type: StackType | None


class ImmediateKind(enum.StrEnum):
    uint8 = enum.auto()
    int8 = enum.auto()
    label = enum.auto()
    uint64 = enum.auto()
    bytes = enum.auto()  # noqa: A003

    # array types
    label_array = enum.auto()
    uint64_array = enum.auto()
    bytes_array = enum.auto()

    # not in original lang spec
    arg_enum = enum.auto()


@attrs.define(kw_only=True)
class Immediate:
    name: str
    """Name used to refer to this value in the Op.doc"""
    immediate_type: ImmediateKind
    arg_enum: str | None = None
    modifies_stack_input: int | None = None
    """Index of stack input type that this immediate modifies"""
    modifies_stack_output: int | None = None
    """Index of stack output type that this immediate modifies"""
    """field_group reference if immediate_type is field_group"""
    doc: str | None = None


@attrs.define
class Cost:
    value: int | None
    """Static cost of op, or None if cost is not static"""
    doc: str
    """Documentation describing how cost is calculated"""


@attrs.define
class Op:
    name: str
    """Name of op in TEAL"""
    size: int
    """Size in bytes of compiled op, 0 indicate size is variable"""
    doc: list[str]
    cost: Cost
    min_avm_version: int
    """AVM version op was introduced"""
    halts: bool
    """True if this op halts the program"""
    groups: list[str] = attrs.field(factory=list)
    """Groups op belongs to"""
    stack_inputs: list[StackValue] = attrs.field(factory=list)
    """Inputs that come from the stack"""
    immediate_args: list[Immediate] = attrs.field(factory=list)
    """Arguments that are passed as immediate values in TEAL"""
    stack_outputs: list[StackValue] = attrs.field(factory=list)
    """Outputs left on the stack"""


@attrs.define
class LanguageSpec:
    ops: dict[str, Op] = attrs.field(factory=dict)
    arg_enums: dict[str, list[ArgEnum]] = attrs.field(factory=dict)

    @staticmethod
    def from_json(json: dict[str, typing.Any]) -> "LanguageSpec":
        return cattrs.structure(json, LanguageSpec)

    def to_json(self) -> dict[str, typing.Any]:
        return attrs.asdict(self)


def _patch_lang_spec(lang_spec: dict[str, typing.Any]) -> None:
    ops = {op["Name"]: op for op in lang_spec["Ops"]}

    # patch ops that use a stack type of any
    # for arguments that should be an Address or Address index
    for op_name in (
        "acct_params_get",
        "app_local_get",
        "app_local_put",
        "app_local_del",
        "app_local_get_ex",
        "app_opted_in",
        "asset_holding_get",
        "balance",
        "min_balance",
    ):
        op = ops[op_name]
        assert op["Args"][0] == "any"
        op["Args"][0] = "address_or_index"

    # patch ops that should be bigint but use []byte
    for op_name in ("bsqrt",):
        op = ops[op_name]
        assert op["Args"][0] == "[]byte"
        op["Args"][0] = "bigint"
        assert op["Returns"][0] == "[]byte"
        op["Returns"][0] = "bigint"

    # base64_decode has an ArgEnumTypes array when it probably shouldn't
    # as all stack outputs are bytes
    del ops["base64_decode"]["ArgEnumTypes"]

    # itxn_field reuses the same field group as txn, however it only uses a subset of fields
    # additionally ArgEnumTypes refers to the stack input types not the output types
    itxn_field = ops["itxn_field"]
    itxn_field["ImmediateNote"][0]["Reference"] = "itxn_field"
    itxn_field["ArgEnumIsInput"] = True
    # ops that never return encode this with a single return type of none
    # however currently this information is stripped when generating langspec.json
    ops["err"]["Halts"] = True
    ops["return"]["Halts"] = True


def create_indexed_enum(op: Operation) -> list[ArgEnum]:
    enum_names = op["ArgEnum"]
    enum_types: list[str] | list[None] = op.get("ArgEnumTypes", [])
    enum_docs = op["ArgEnumDoc"]

    if not enum_types:
        enum_types = [None] * len(enum_names)

    result = list[ArgEnum]()
    for enum_name, enum_type, enum_doc in zip(enum_names, enum_types, enum_docs, strict=True):
        stack_type = None if enum_type is None else StackType(enum_type)
        enum_value = ArgEnum(
            name=enum_name,
            doc=enum_doc if enum_doc else None,
            stack_type=stack_type,
        )
        result.append(enum_value)
    return result


def transform_encoding(value: str) -> ImmediateKind:
    match value:
        case "uint8":
            result = ImmediateKind.uint8
        case "int8":
            result = ImmediateKind.int8
        case "int16 (big-endian)":
            result = ImmediateKind.label
        case "varuint":
            result = ImmediateKind.uint64
        case "varuint length, bytes":
            result = ImmediateKind.bytes
        case "varuint count, [varuint ...]":
            result = ImmediateKind.uint64_array
        case "varuint count, [varuint length, bytes ...]":
            result = ImmediateKind.bytes_array
        case "varuint count, [int16 (big-endian) ...]":
            result = ImmediateKind.label_array
        case _:
            raise ValueError(f"Unknown Encoding: {value}")
    return result


def transform_stack_args(op: Operation) -> list[StackValue]:
    result = list[StackValue]()
    args = op.get("Args", [])
    assert len(args) <= len(STACK_INPUT_NAMES), f"More args than expected for {op['Name']}"
    for index, arg_type in enumerate(op.get("Args", [])):
        name = STACK_INPUT_NAMES[index]
        stack_type = StackType(arg_type)
        result.append(StackValue(name=name, stack_type=stack_type))
    return result


def transform_immediates(
    spec: LanguageSpec,
    op: Operation,
) -> list[Immediate]:
    arg_enums = spec.arg_enums
    op_name = op["Name"]
    result = list[Immediate]()
    for immediate in op.get("ImmediateNote", []):
        arg_enum_reference = immediate.get("Reference")
        if arg_enum_reference is not None:
            arg_enum = op.get("ArgEnum")
            if arg_enum_reference not in arg_enums:
                assert arg_enum, f"Expected enum for {op_name}"
                arg_enums[arg_enum_reference] = create_indexed_enum(op)

            if arg_enum is not None:
                assert len(arg_enum) == len(
                    arg_enums[arg_enum_reference]
                ), f"Arg Enum lengths don't match for {op_name}"

        modifies_stack_input: int | None = None
        modifies_stack_output: int | None = None

        if arg_enum_reference and any(a.stack_type for a in arg_enums[arg_enum_reference]):
            assert all(a.stack_type for a in arg_enums[arg_enum_reference])
            if op.get("ArgEnumIsInput"):
                modifies_stack_input = 0
            else:
                modifies_stack_output = 0

        result.append(
            Immediate(
                name=immediate["Name"],
                immediate_type=transform_encoding(immediate["Encoding"])
                if arg_enum_reference is None
                else ImmediateKind.arg_enum,
                modifies_stack_input=modifies_stack_input,
                modifies_stack_output=modifies_stack_output,
                arg_enum=arg_enum_reference,
                doc=immediate["Comment"],
            )
        )
    return result


def transform_returns(op: Operation) -> list[StackValue]:
    try:
        returns = op["Returns"]
    except KeyError:
        return []
    num_returns = len(returns)
    if num_returns <= len(STACK_OUTPUT_NAMES_FEW):
        return_argument_names = STACK_OUTPUT_NAMES_FEW
    elif num_returns <= len(STACK_OUTPUT_NAMES_MANY):
        return_argument_names = STACK_OUTPUT_NAMES_MANY
    else:
        raise AssertionError(f"More returns than expected for {op['Name']}")
    return [
        StackValue(
            name=name,
            stack_type=StackType(return_type),
        )
        for name, return_type in zip(return_argument_names, returns, strict=False)
    ]


def transform_doc(op: Operation) -> list[str]:
    doc = op["Doc"].splitlines()

    doc_extra = op.get("DocExtra")
    if doc_extra:
        doc.extend(doc_extra.splitlines())
    return doc


def get_immediate_encoded_size(immediate: Immediate) -> int:
    match immediate.immediate_type:
        case ImmediateKind.uint8 | ImmediateKind.int8 | ImmediateKind.arg_enum:
            return 1
        case ImmediateKind.label:
            return 2
        case ImmediateKind():
            return 0
        case _:
            raise ValueError(f"Cannot determine size of {immediate.immediate_type}")


def transform_cost(op: Operation) -> Cost:
    algorand_cost = op["Cost"]
    cost = Cost(value=None, doc=algorand_cost)
    with contextlib.suppress(ValueError):
        cost.value = int(algorand_cost)

    return cost


def transform_spec(lang_spec: AlgorandLanguageSpec) -> LanguageSpec:
    result = LanguageSpec()
    for algorand_op in sorted(lang_spec["Ops"], key=lambda x: x["Name"]):
        op_name = algorand_op["Name"]

        op = Op(
            name=op_name,
            size=algorand_op["Size"],
            doc=transform_doc(algorand_op),
            cost=transform_cost(algorand_op),
            min_avm_version=algorand_op["IntroducedVersion"],
            groups=algorand_op["Groups"],
            immediate_args=transform_immediates(result, algorand_op),
            stack_inputs=transform_stack_args(algorand_op),
            stack_outputs=transform_returns(algorand_op),
            halts=algorand_op.get("Halts", False),
        )
        validate_op(result, op)
        result.ops[op.name] = op
    return result


def validate_op(lang_spec: LanguageSpec, op: Op) -> None:
    # validate op size
    instruction_size = 0 if op.name in VARIABLE_SIZE_OPCODES else 1
    expected_size = (
        sum([get_immediate_encoded_size(a) for a in op.immediate_args]) + instruction_size
    )
    assert op.size == expected_size, f"Unexpected size for specified immediate args for {op.name}"

    # validate immediate modifiers
    for immediate in op.immediate_args:
        if immediate.immediate_type == ImmediateKind.arg_enum:
            assert immediate.arg_enum in lang_spec.arg_enums
            if immediate.modifies_stack_input is not None:
                assert immediate.modifies_stack_input < len(op.stack_inputs), (
                    f"Immediate for {op.name} references stack input "
                    f"that does not exist {immediate.modifies_stack_input}"
                )
            if immediate.modifies_stack_output is not None:
                assert immediate.modifies_stack_output < len(op.stack_outputs), (
                    f"Immediate for {op.name} references stack output "
                    f"that does not exist {immediate.modifies_stack_output}"
                )
        else:
            assert not immediate.arg_enum
            assert not immediate.modifies_stack_input
            assert not immediate.modifies_stack_output


def main() -> None:
    vcs_root = Path(__file__).parent.parent
    spec_path = vcs_root / "langspec.json"

    output_path = vcs_root / "langspec.wyvern.json"
    logger.info(f"Transforming {spec_path} to {output_path}")

    lang_spec_json = json.loads(spec_path.read_text(encoding="utf-8"))
    _patch_lang_spec(lang_spec_json)
    lang_spec = typing.cast(AlgorandLanguageSpec, lang_spec_json)

    wyvern_spec = transform_spec(lang_spec)
    wyvern_json = json.dumps(wyvern_spec.to_json(), indent=4)
    output_path.write_text(wyvern_json, encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
