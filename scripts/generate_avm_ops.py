import builtins
import json
import keyword
import subprocess
import textwrap
from collections.abc import Iterable, Iterator
from pathlib import Path

import structlog
from puya.ir.avm_ops_models import (
    AVMOpData,
    DynamicSignatures,
    ImmediateKind,
    OpSignature,
    StackType,
)
from puya.utils import normalise_path_to_str

from scripts import transform_lang_spec as langspec

logger = structlog.get_logger(__name__)
VCS_ROOT = Path(__file__).parent.parent

SUPPORTED_IMMEDIATE_KINDS = (langspec.ImmediateKind.uint8, langspec.ImmediateKind.arg_enum)

operator_names = {
    # bool
    "&&": "and",
    "||": "or",
    "!": "not",
    # compare
    "==": "eq",
    "!=": "neq",
    "<": "lt",
    "<=": "lte",
    ">": "gt",
    ">=": "gte",
    # bitwise
    "&": "bitwise_and",
    "^": "bitwise_xor",
    "|": "bitwise_or",
    "~": "bitwise_not",
    # math
    "+": "add",
    "-": "sub",
    "*": "mul",
    "/": "div_floor",
    "%": "mod",
}

EXCLUDED_OPCODES = {
    # flow control
    "bnz",
    "bz",
    "b",
    "callsub",
    "retsub",
    "proto",
    "switch",
    "match",
    # pure stack manipulation
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
    # modifies what other op codes with immediates point to
    "intcblock",
    "bytecblock",
    # halting
    "err",
    "return",
}


def as_list_str(values: Iterable[str]) -> str | None:
    inner = ", ".join(values)
    if not inner:
        return None
    else:
        return f"[{inner}]"


BUILTIN_NAMES = frozenset(dir(builtins))


def get_op_name(op: langspec.Op) -> str:
    op_code = op.name
    if op_code.isidentifier():
        op_name = op_code
    elif op_code[0] == "b":
        op_name = operator_names[op_code[1:]] + "_bytes"
    else:
        op_name = operator_names[op_code]
    if keyword.iskeyword(op_name) or keyword.issoftkeyword(op_name) or op_name in BUILTIN_NAMES:
        op_name += "_"
    return op_name


def generate_op_node(
    enums: dict[str, list[langspec.ArgEnum]], op_name: str, op: langspec.Op
) -> Iterator[str]:
    assert not op.halts, "op halts"
    dynamic_im_index: int | None = None
    for idx, im in enumerate(op.immediate_args):
        if im.modifies_stack_input is not None:
            assert im.modifies_stack_output is None, "💀"
            assert dynamic_im_index is None, "🪦"

            dynamic_im_index = idx
        elif im.modifies_stack_output is not None:
            assert dynamic_im_index is None, "🪦"
            dynamic_im_index = idx

    immediate_types = tuple(get_immediate_type(im) for im in op.immediate_args)
    op_code = op.name
    cost = op.cost.value
    signature: DynamicSignatures | OpSignature

    stack_args = [get_stack_type(arg.stack_type) for arg in op.stack_inputs]
    stack_returns = [get_stack_type(out.stack_type) for out in op.stack_outputs]
    if dynamic_im_index is None:
        signature = OpSignature(
            args=stack_args,
            returns=stack_returns,
        )
    else:
        im = op.immediate_args[dynamic_im_index]
        assert im.arg_enum is not None, "💥"
        signature = DynamicSignatures(
            immediate_index=dynamic_im_index,
            signatures={},
        )
        if im.modifies_stack_input is not None:
            list_index = im.modifies_stack_input
            to_mod = stack_args
        else:
            assert im.modifies_stack_output is not None
            list_index = im.modifies_stack_output
            to_mod = stack_returns
        for arg_enum in enums[im.arg_enum]:
            assert arg_enum.stack_type is not None, "🤕"
            to_mod[list_index] = get_stack_type(arg_enum.stack_type)
            signature.signatures[arg_enum.name] = OpSignature(
                args=list(stack_args),
                returns=list(stack_returns),
            )

    data = AVMOpData(
        op_code=op_code,
        immediate_types=immediate_types,
        signature=signature,
        cost=cost,
        min_avm_version=op.min_avm_version,
    )
    yield f"{op_name} = {data!r}"
    if op.doc:
        yield '"""'
        for idx, doc_ln in enumerate(op.doc):
            if idx > 0:
                yield ""
            yield from textwrap.wrap(doc_ln, width=99 - 4)
        yield '"""'
    yield ""


def get_stack_type(stack_type: langspec.StackType) -> StackType:
    if stack_type in (
        langspec.StackType.bytes_8,
        langspec.StackType.bytes_32,
        langspec.StackType.bytes_33,
        langspec.StackType.bytes_64,
        langspec.StackType.bytes_80,
    ):
        return StackType.bytes
    else:
        return StackType[stack_type.name]


def get_immediate_type(immediate: langspec.Immediate) -> ImmediateKind:
    assert immediate.immediate_type in SUPPORTED_IMMEDIATE_KINDS, (
        "bad immediate kind",
        immediate.immediate_type,
    )
    return ImmediateKind[immediate.immediate_type.name]


def generate_file(lang_spec: langspec.LanguageSpec) -> Iterator[str]:
    script_path = normalise_path_to_str(Path(__file__).relative_to(VCS_ROOT))
    preamble = f"""
# AUTO GENERATED BY {script_path}, DO NOT EDIT
import enum
from collections.abc import Sequence

from puya.errors import InternalError
from puya.ir.avm_ops_models import (
    AVMOpData,
    DynamicSignatures,
    ImmediateKind,
    OpSignature,
    StackType,
)


class AVMOp(enum.StrEnum):
    code: str
    immediate_types: Sequence[ImmediateKind]
    _signature: OpSignature | DynamicSignatures
    cost: int | None
    min_avm_version: int

    def __new__(cls, data: AVMOpData | str) -> "AVMOp":
        # the weird union type on data && then assert,
        # is to shut mypy up when it wrongly infers the arg type of
        # e.g. AVMOp("+") to be invalid
        assert isinstance(data, AVMOpData)
        op_code = data.op_code
        obj = str.__new__(cls, op_code)
        obj._value_ = op_code
        obj.code = op_code
        obj.immediate_types = tuple(data.immediate_types)
        obj._signature = data.signature  # noqa: SLF001
        obj.cost = data.cost
        obj.min_avm_version = data.min_avm_version
        return obj

    def get_signature(self, immediates: Sequence[str | int]) -> OpSignature:
        if isinstance(self._signature, OpSignature):
            return self._signature
        im = immediates[self._signature.immediate_index]
        assert isinstance(im, str)
        try:
            return self._signature.signatures[im]
        except KeyError as ex:
            raise InternalError(f"Unknown immediate for {{self.code}}: {{im}}") from ex
    """
    yield from preamble.strip().splitlines()
    yield ""
    ops_by_name = {}
    for op in lang_spec.ops.values():
        if op.name in EXCLUDED_OPCODES:
            logger.info(f"Skipping {op.name} due to specific exclusion")
        else:
            ops_by_name[get_op_name(op)] = op
    for op_name, op in sorted(ops_by_name.items()):
        yield textwrap.indent(
            "\n".join(generate_op_node(lang_spec.arg_enums, op_name, op)), " " * 4
        )


def main() -> None:
    spec_path = VCS_ROOT / "langspec.puya.json"

    lang_spec_json = json.loads(spec_path.read_text(encoding="utf-8"))
    lang_spec = langspec.LanguageSpec.from_json(lang_spec_json)

    output = "\n".join(generate_file(lang_spec))

    ast_gen_path = VCS_ROOT / "src" / "puya" / "ir" / "avm_ops.py"
    ast_gen_path.write_text(output, encoding="utf-8")
    subprocess.run(["black", str(ast_gen_path)], check=True, cwd=VCS_ROOT)


if __name__ == "__main__":
    main()
