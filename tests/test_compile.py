import json
import os
import shutil
import typing
from pathlib import Path

import attrs

from puya import log
from puyapy.options import PuyaPyOptions
from tests import VCS_ROOT
from tests.utils import (
    SUFFIX_O0,
    SUFFIX_O1,
    SUFFIX_O2,
    PuyaTestCase,
    compile_src_from_options,
    load_template_vars,
    log_to_str,
)
from tests.utils.git import check_for_diff

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
}


def test_compile(test_case: PuyaTestCase) -> None:
    _remove_output(test_case.path)
    _compile_no_optimization(test_case)
    _compile_with_level1_optimizations(test_case)
    _compile_with_level2_optimizations(test_case)
    diff = check_for_diff(test_case.path, VCS_ROOT)
    # bool conversion here results in a nicer assertion display if there is a diff
    has_diff = bool(diff)
    assert not has_diff, f"Uncommitted changes were found:\n{diff}"


def _compile_test_case(
    test_case: PuyaTestCase, suffix: str, log_path: Path | None = None, **options: typing.Any
) -> None:
    path = test_case.path
    assert path.is_dir()
    dst_out_dir = path / ("out" + suffix)

    prefix, template_vars = load_template_vars(test_case.template_vars_path)
    puya_options = PuyaPyOptions(
        paths=(test_case.path,),
        out_dir=dst_out_dir,
        log_level=log.LogLevel.debug,
        template_vars_prefix=prefix,
        cli_template_definitions=template_vars,
        output_op_statistics=True,
        **options,
    )
    compile_result = compile_src_from_options(puya_options)

    if log_path:
        root_dir = compile_result.root_dir
        log_options = attrs.evolve(puya_options, paths=(Path(test_case.name),))
        logs = [log_to_str(log_, root_dir) for log_ in compile_result.logs]
        logs.insert(0, f"debug: {log_options}")
        log_path.write_text(
            "\n".join(map(_normalize_log, logs)),
            encoding="utf8",
        )

    # normalize ARC-56 output
    for arc56_file in dst_out_dir.rglob("*.arc56.json"):
        _normalize_arc56(arc56_file)


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


_NORMALIZED_VCS = _normalize_path(VCS_ROOT)


def _normalize_log(log: str) -> str:
    return log.replace("\\", "/").replace(_NORMALIZED_VCS, "<git root>")


def _compile_no_optimization(test_case: PuyaTestCase) -> None:
    _compile_test_case(
        test_case,
        SUFFIX_O0,
        log_path=test_case.path / f"puya{SUFFIX_O0}.log",
        optimization_level=0,
        output_teal=True,
        output_bytecode=True,
        output_source_map=True,
        output_destructured_ir=True,
    )


def _compile_with_level1_optimizations(test_case: PuyaTestCase) -> None:
    _compile_test_case(
        test_case,
        SUFFIX_O1,
        log_path=test_case.path / f"puya{SUFFIX_O1}.log",
        optimization_level=1,
        output_teal=True,
        output_bytecode=True,
        output_source_map=True,
        output_arc32=False,
        output_arc56=True,
        output_awst=True,
        output_ssa_ir=True,
        output_optimization_ir=True,
        output_destructured_ir=True,
        output_memory_ir=True,
        output_client=True,
    )


def _compile_with_level2_optimizations(test_case: PuyaTestCase) -> None:
    _compile_test_case(
        test_case,
        SUFFIX_O2,
        log_path=test_case.path / f"puya{SUFFIX_O2}.log",
        optimization_level=2,
        debug_level=0,
        output_teal=True,
        output_bytecode=True,
        output_source_map=True,
        output_destructured_ir=True,
    )


def _remove_output(path: Path) -> None:
    for out_suffix in (SUFFIX_O0, SUFFIX_O1, SUFFIX_O2):
        (path / f"puya{out_suffix}.log").unlink(missing_ok=True)
        out_dir = path / f"out{out_suffix}"
        if not out_dir.exists():
            continue
        for prev_out_file in out_dir.iterdir():
            if prev_out_file.is_dir():
                shutil.rmtree(prev_out_file)
            elif prev_out_file.suffix != ".log":  # execution log
                prev_out_file.unlink()


def _normalize_arc56(path: Path) -> None:
    arc56 = json.loads(path.read_text(encoding="utf8"))
    compiler_version = arc56.get("compilerInfo", {}).get("compilerVersion", {})
    compiler_version["major"] = 99
    compiler_version["minor"] = 99
    compiler_version["patch"] = 99
    path.write_text(json.dumps(arc56, indent=4), encoding="utf8")
