import base64
from collections.abc import Mapping, Sequence

import algokit_utils as au
import pytest

from puya.compilation_artifacts import CompiledContract, CompiledLogicSig, CompiledProgram
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir.types_ import AVMBytesEncoding
from puya.mir.models import Signature
from puya.options import PuyaOptions
from puya.program_refs import LogicSigReference, ProgramKind
from puya.teal import models as teal
from puya.ussemble.main import assemble_program
from tests.utils import PuyaTestCase
from tests.utils.compile import compile_from_test_case


# TODO: add v13 coverage to compare varint branch encoding against algod (go-algorand#6600)
@pytest.mark.parametrize("optimization_level", [0, 1, 2])
@pytest.mark.localnet
def test_assemble_matches_algod(
    algod_client: au.AlgodClient, test_case: PuyaTestCase, optimization_level: int
) -> None:
    compile_result = compile_from_test_case(
        test_case, optimization_level=optimization_level, debug_level=0, output_bytecode=True
    )
    template_vars = compile_result.options.template_variables
    for artifact in compile_result.teal:
        match artifact:
            case CompiledContract(approval_program=approval, clear_program=clear):
                assemble_and_compare_program(
                    algod_client, approval, template_vars, f"{artifact.metadata.ref}-approval"
                )
                assemble_and_compare_program(
                    algod_client, clear, template_vars, f"{artifact.metadata.ref}-clear"
                )
            case CompiledLogicSig(program=logic_sig):
                assemble_and_compare_program(
                    algod_client, logic_sig, template_vars, f"{artifact.metadata.ref}-logicsig"
                )


def assemble_and_compare_program(
    algod_client: au.AlgodClient,
    compiled_program: CompiledProgram,
    template_variables: Mapping[str, int | bytes],
    name: str,
) -> None:
    puya_program = compiled_program.bytecode
    assert puya_program is not None
    template_values = {k: _template_value_as_str(v) for k, v in template_variables.items()}
    teal_src = "\n".join(
        _replace_template_variables(line, template_values)
        for line in compiled_program.teal_src.splitlines()
    )
    algod_program_64 = algod_client.teal_compile(teal_src.encode("utf-8")).result
    algod_program = base64.b64decode(algod_program_64)

    expected = algod_program.hex()
    actual = puya_program.hex()
    if expected != actual:
        # attempt to decompile both to compare, but revert to byte code if puya can't
        # even be disassembled
        try:
            puya_dis = algod_client.teal_disassemble(puya_program).result
        except au.UnexpectedStatusError:
            pass
        else:
            expected = algod_client.teal_disassemble(algod_program).result
            actual = puya_dis
    assert actual == expected, f"{name} bytecode does not match algod bytecode"


def _template_value_as_str(value: int | bytes) -> str:
    if isinstance(value, int):
        return repr(value)
    return "0x" + value.hex()


def _replace_template_variables(line: str, template_values: Mapping[str, str]) -> str:
    for var, value in template_values.items():
        line = line.replace(var, value, 1)
    return line


def test_assemble_last_op_self_jump() -> None:
    """Verifies edge case where final op of a program is a branch op
    and said op branches to itself"""
    # construct a block that is terminated with a branch, by jumping to the block's label
    bytecode = _assemble_blocks(
        avm_version=10, blocks=[_block("start", [_intrinsic("b", "start")])]
    )
    assert bytecode == b"".join(
        (
            b"\x0a",  # version 10
            b"B",  # branch
            (-3).to_bytes(length=2, signed=True),  # offset
        )
    )

    with pytest.raises(
        InternalError, match="jump 'b' to start of same instruction cannot be encoded"
    ):
        _assemble_blocks(
            avm_version=13,
            blocks=[_block("start", [_intrinsic("b", "start")])],
        )


def _intrinsic(op_code: str, *immediates: str) -> teal.Intrinsic:
    return teal.Intrinsic(
        op_code=op_code,
        immediates=list(immediates),
        consumes=0,
        produces=0,
        source_location=None,
        error_message=None,
    )


def _block(label: str, ops: Sequence[teal.TealOp]) -> teal.TealBlock:
    return teal.TealBlock(
        label=label,
        ops=list(ops),
        x_stack_in=(),
        entry_stack_height=0,
        exit_stack_height=0,
    )


def _assemble_blocks(avm_version: int, blocks: Sequence[teal.TealBlock]) -> bytes:
    return assemble_program(
        CompileContext(options=PuyaOptions(), compilation_set={}, sources_by_path={}),
        LogicSigReference(),
        program=teal.TealProgram(
            kind=ProgramKind.logic_signature,
            avm_version=avm_version,
            main=teal.TealSubroutine(
                is_main=True,
                signature=Signature(name="", parameters=(), returns=()),
                blocks=list(blocks),
                source_location=None,
            ),
            subroutines=[],
        ),
    ).bytecode


# TODO: once available, we can refactor these tests to just use algod
# then we fold them into assemble_and_compare_program(.)
def test_assemble_jump_to_the_end() -> None:
    """From v13 on, a zero-offset branch (target is the next instruction) encodes
    the offset as a single 0x00 byte rather than 0x00 0x00"""
    bytecode = _assemble_blocks(
        avm_version=13,
        blocks=[
            _block(
                "main",
                [
                    teal.IntBlock(constants={1: None}, source_location=None),
                    _intrinsic("intc_0"),
                    _intrinsic("intc_0"),
                    _intrinsic("bnz", "done"),
                ],
            ),
            _block("done", []),
        ],
    )
    assert bytecode == b"".join(
        (
            b"\x0d",  # version 13
            b"\x20",  # intcblock
            b"\x01",  # 1 constant
            b"\x01",  # constant value 1
            b"\x22",  # intc_0
            b"\x22",  # intc_0
            b"\x40",  # bnz -> "done"
            b"\x00",  # zig-zag varint of 0 ("done" is the next instruction)
        )
    )


def test_assemble_v12_to_v13_branches() -> None:
    """Check the difference in encoding between AVM v12 and v13 in the same program"""
    blocks = [
        _block("start", [_intrinsic("b", "end")]),  # forward jump
        _block("filler", [_intrinsic("len"), _intrinsic("len"), _intrinsic("len")]),
        _block("end", [_intrinsic("len"), _intrinsic("b", "start")]),  # backwards jump
    ]

    # v12: each branch offset is a fixed 2-byte big-endian signed int16
    assert _assemble_blocks(avm_version=12, blocks=blocks) == b"".join(
        (
            b"\x0c",  # version 12
            b"\x42",  # b -> "end" (forward)
            (3).to_bytes(length=2, signed=True),  # +3, from end of op to target "end"
            b"\x15\x15\x15",  # len; len; len;
            b"\x15",  # len (start of "end" block)
            b"\x42",  # b -> start (backwards)
            (-10).to_bytes(length=2, signed=True),  # -10, from end of op @11 to target @1
        )
    )

    # v13: each offset shrinks to a 1-byte signed (zig-zag) varint
    assert _assemble_blocks(avm_version=13, blocks=blocks) == b"".join(
        (
            b"\x0d",  # version 13
            b"\x42",  # b -> "end" (forward)
            b"\x06",  # zig-zag varint of +3, from end of op @3 to target @6
            b"\x15\x15\x15",  # len; len; len;
            b"\x15",  # len (start of "end" block @6)
            b"\x42",  # b -> "start" (backwards)
            b"\x0b",  # zig-zag varint of -6, from start of op @7 to target @1
        )
    )


def test_assemble_branch_too_far() -> None:
    """A varint branch whose target is beyond
    the 3-byte placeholder range (~1 MB) is rejected
    """
    padding: list[teal.TealOp] = [
        teal.PushBytes(
            comment=None,
            value=b"\x00" * 4096,
            encoding=AVMBytesEncoding.base16,
            source_location=None,
        )
        for _ in range(2**20 // 4096 + 1)
    ]
    with pytest.raises(InternalError, match="branch target for b is too far away"):
        _assemble_blocks(
            avm_version=13,
            blocks=[
                _block("start", [_intrinsic("b", "done")]),  # forward jump over the padding
                _block("pad", padding),
                _block("done", [_intrinsic("len")]),
            ],
        )
