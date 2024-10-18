from collections.abc import Iterable, Mapping
from pathlib import Path

import algosdk.error
import pytest
from _pytest.mark import ParameterSet
from algokit_utils import Program
from algosdk.v2client.algod import AlgodClient
from puya.context import CompileContext
from puya.mir.models import Signature
from puya.models import CompiledContract, CompiledLogicSig, CompiledProgram
from puya.options import PuyaOptions
from puya.teal import models as teal
from puya.ussemble.main import assemble_program
from puyapy.options import PuyaPyOptions

from tests.utils import (
    PuyaExample,
    compile_src_from_options,
    get_all_examples,
    load_template_vars,
)


def get_test_cases() -> Iterable[ParameterSet]:
    for example in get_all_examples():
        marks = []
        if example.name == "stress_tests":
            marks.append(pytest.mark.slow)
        yield ParameterSet.param(example, marks=marks, id=example.id)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if metafunc.definition.name == "test_assemble_last_op_jump":
        pass
    else:
        metafunc.parametrize("case", get_test_cases())


@pytest.mark.parametrize("optimization_level", [0, 1, 2])
@pytest.mark.localnet()
def test_assemble_matches_algod(
    algod_client: AlgodClient, case: PuyaExample, optimization_level: int
) -> None:
    prefix, template_vars = load_template_vars(case.template_vars_path)
    options = PuyaPyOptions(
        paths=(case.path,),
        optimization_level=optimization_level,
        debug_level=0,
        output_bytecode=True,
        out_dir=Path("out"),
        template_vars_prefix=prefix,
        cli_template_definitions=template_vars,
    )
    compile_result = compile_src_from_options(options)
    for artifact in compile_result.teal:
        match artifact:
            case CompiledContract(approval_program=approval, clear_program=clear):
                assemble_and_compare_program(
                    options, algod_client, approval, f"{artifact.metadata.ref}-approval"
                )
                assemble_and_compare_program(
                    options, algod_client, clear, f"{artifact.metadata.ref}-clear"
                )
            case CompiledLogicSig(program=logic_sig):
                assemble_and_compare_program(
                    options, algod_client, logic_sig, f"{artifact.metadata.ref}-logicsig"
                )


def assemble_and_compare_program(
    options: PuyaOptions,
    algod_client: AlgodClient,
    compiled_program: CompiledProgram,
    name: str,
) -> None:
    puya_program = compiled_program.bytecode
    assert puya_program is not None
    template_values = {k: _template_value_as_str(v) for k, v in options.template_variables.items()}
    teal_src = "\n".join(
        _replace_template_variables(line, template_values)
        for line in compiled_program.teal_src.splitlines()
    )
    algod_program_ = Program(teal_src, algod_client)
    algod_program = algod_program_.raw_binary

    expected = algod_program.hex()
    actual = puya_program.hex()
    if expected != actual:
        # attempt to decompile both to compare, but revert to byte code if puya can't
        # even be disassembled
        try:
            puya_dis = algod_client.disassemble(puya_program)["result"]
        except algosdk.error.AlgodHTTPError:
            pass
        else:
            expected = algod_client.disassemble(algod_program)["result"]
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


def test_assemble_last_op_jump() -> None:
    """Verifies edge case where final op of a program is a branch op"""

    # construct a block that is terminated with a branch, by jumping to the block's label
    looping_block = teal.TealBlock(
        label="start",
        ops=[
            teal.Intrinsic(
                op_code="b",
                immediates=["start"],
                consumes=0,
                produces=0,
                source_location=None,
            )
        ],
        x_stack=(),
        entry_stack_height=0,
        exit_stack_height=0,
    )

    # verify program assembles correctly
    bytecode = assemble_program(
        CompileContext(
            options=PuyaOptions(),
            compilation_set={},
            sources_by_path={},
        ),
        program=teal.TealProgram(
            id="",
            target_avm_version=10,
            main=teal.TealSubroutine(
                is_main=True,
                signature=Signature(name="", parameters=(), returns=()),
                blocks=[looping_block],
            ),
            subroutines=[],
        ),
        template_variables={},
    ).bytecode

    assert bytecode == b"".join(
        (
            b"\x0A",  # version 10
            b"B",  # branch
            (-3).to_bytes(length=2, signed=True),  # offset
        )
    )
