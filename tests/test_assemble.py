from collections.abc import Iterable, Mapping
from pathlib import Path

import algosdk.error
import pytest
from _pytest.mark import ParameterSet
from algokit_utils import Program
from algosdk.v2client.algod import AlgodClient
from puya.context import CompileContext
from puya.models import CompiledContract, CompiledLogicSig, CompiledProgram
from puya.options import PuyaOptions

from tests.utils import (
    PuyaExample,
    compile_src_from_options,
    get_all_examples,
)


def get_test_cases() -> Iterable[ParameterSet]:
    for example in get_all_examples():
        marks = []
        if example.name == "stress_tests":
            marks.append(pytest.mark.slow)
        yield ParameterSet.param(example, marks=marks, id=example.id)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    metafunc.parametrize("case", get_test_cases())


@pytest.mark.parametrize("optimization_level", [0, 1, 2])
@pytest.mark.localnet()
def test_assemble_matches_algod(
    algod_client: AlgodClient, case: PuyaExample, optimization_level: int
) -> None:
    compile_result = compile_src_from_options(
        PuyaOptions(
            paths=(case.path,),
            optimization_level=optimization_level,
            template_vars_path=case.template_vars_path,
            debug_level=0,
            output_teal=False,
            output_arc32=False,
            output_bytecode=True,
            match_algod_bytecode=True,
            out_dir=Path("out"),
        )
    )
    for artifacts in compile_result.teal.values():
        for artifact in artifacts:
            match artifact:
                case CompiledContract(approval_program=approval, clear_program=clear):
                    assemble_and_compare_program(
                        compile_result.context,
                        algod_client,
                        approval,
                        f"{artifact.metadata.name}-approval",
                    )
                    assemble_and_compare_program(
                        compile_result.context,
                        algod_client,
                        clear,
                        f"{artifact.metadata.name}-clear",
                    )
                case CompiledLogicSig(program=logic_sig):
                    assemble_and_compare_program(
                        compile_result.context,
                        algod_client,
                        logic_sig,
                        f"{artifact.metadata.name}-logicsig",
                    )


@pytest.mark.parametrize("optimization_level", [0, 1, 2])
def test_assemble(case: PuyaExample, optimization_level: int) -> None:
    compile_src_from_options(
        PuyaOptions(
            paths=(case.path,),
            optimization_level=optimization_level,
            template_vars_path=case.template_vars_path,
            debug_level=0,
            output_teal=False,
            output_arc32=False,
            output_bytecode=True,
            out_dir=Path("out"),
        )
    )


def _value_as_tmpl_str(value: int | bytes | str) -> str:
    match value:
        case int(int_value):
            return str(int_value)
        case bytes(bytes_value):
            return f"0x{bytes_value.hex()}"
        case str(str_value):
            return repr(str_value)


def assemble_and_compare_program(
    context: CompileContext,
    algod_client: AlgodClient,
    compiled_program: CompiledProgram,
    name: str,
) -> None:
    puya_program = compiled_program.bytecode
    assert puya_program is not None
    template_values = {
        k: _template_value_as_str(v) for k, v in context.options.template_variables.items()
    }
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
