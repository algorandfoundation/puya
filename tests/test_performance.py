import gc
import gzip
from collections.abc import Mapping
from pathlib import Path

import attrs
import pytest

from puya.awst import nodes
from puya.awst.serialize import awst_from_json
from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.log import logging_context
from puya.options import PuyaOptions
from puya.program_refs import ContractReference, LogicSigReference
from tests import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT
from tests.utils import get_awst_cache


@attrs.frozen
class _Compilation:
    awst: nodes.AWST
    compilation_set: Mapping[LogicSigReference | ContractReference, Path]


_RETI_AWST = VCS_ROOT / "tests" / "analyse" / "reti.awst.json.zip"


@pytest.fixture(scope="session")
def reti_awst() -> nodes.AWST:
    reti_json = gzip.decompress(_RETI_AWST.read_bytes()).decode("utf-8")
    return awst_from_json(reti_json)


@pytest.fixture
def compilation(tmp_path: Path, reti_awst: nodes.AWST) -> _Compilation:
    examples_cache = get_awst_cache(EXAMPLES_DIR)
    test_cases_cache = get_awst_cache(TEST_CASES_DIR)
    awst = [
        *examples_cache.module_awst,
        *test_cases_cache.module_awst,
        *reti_awst,
    ]
    reti_compilation_ids = [
        n.id for n in reti_awst if isinstance(n, nodes.Contract | nodes.LogicSignature)
    ]
    compilation_set_ids = [
        *examples_cache.compilation_set,
        *test_cases_cache.compilation_set,
        *reti_compilation_ids,
    ]
    compilation_set = {str(key): tmp_path / key for key in compilation_set_ids}
    return _Compilation(
        awst=awst,
        compilation_set=compilation_set,  # type: ignore[arg-type]
    )


def test_pipeline(compilation: _Compilation) -> None:
    options = PuyaOptions(
        optimization_level=0,
        debug_level=0,
        optimizations_override={
            "perform_subroutine_inlining": False,
            "merge_chained_aggregate_reads": True,
            "replace_aggregate_box_ops": True,
        },
    )
    # options = PuyaOptions()
    # options = PuyaOptions(
    #    debug_level=0,
    #    optimizations_override={
    #        "perform_subroutine_inlining": False,
    #        "repeated_expression_elimination": False,
    #        "intrinsic_simplifier": False,
    #        "copy_propagation": False,
    #        "lstack.opt": False,
    #        "xstack": False,
    #        "xstack.opt": False,
    #        "fstack.opt": False,
    #    },
    # )
    warm_up = 2
    num_loops = 10
    all_timings = []
    for loop in range(num_loops + warm_up):
        gc.disable()
        try:
            with (
                logging_context() as log_ctx,
                log_exceptions(),
            ):
                # Process the compilation
                awst_to_teal(
                    log_ctx,
                    options,
                    compilation.compilation_set,
                    sources_by_path={},
                    awst=compilation.awst,
                )
                timings = log_ctx.stopwatch.stop()
        finally:
            gc.enable()
            gc.collect()
        if loop >= warm_up:
            all_timings.append(timings)
    _average_and_report_timings(all_timings)


def _average_timings(
    timings: list[dict[str, tuple[float, int]]],
) -> dict[str, dict[str, float | int]]:
    import statistics

    abs_stats = [s for s in timings[0] if s.startswith("*")]
    for timing in timings:
        analyse_start, _ = timing.pop("Start")
        analyse_end, _ = timing.pop("End")
        timing.update({stat: timing.pop(stat) for stat in abs_stats})
        timing["Total"] = (analyse_end - analyse_start, 1)

    summary = {}
    for stat in timings[0]:
        values = [v[stat][0] for v in timings]
        count = statistics.mean(v[stat][1] for v in timings)
        mean = statistics.mean(values)
        if len(values) > 1:
            stdev = statistics.stdev(values)
        else:
            stdev = 0.0
        summary[stat] = {
            "duration": mean,
            "stdev": stdev,
            "count": count,
        }
    return summary


def _average_and_report_timings(timings: list[dict[str, tuple[float, int]]]) -> None:
    average_timing = _average_timings(timings)
    report = _report_timings(average_timing, n=len(timings))
    print(report)  # noqa: T201


def _report_timings(timings: dict[str, dict[str, int | float]], n: int) -> str:
    import prettytable

    writer = prettytable.PrettyTable(
        field_names=["Lap", "Duration (s)", f"σ ({n=})", "count", "%"],  # noqa: RUF001
        float_format=".3",
        align="r",
    )
    writer.set_style(prettytable.TableStyle.MARKDOWN)
    writer.align["Lap"] = "l"
    total = timings["Total"]["duration"]
    for lap, stat in timings.items():
        duration = stat["duration"]
        stdev = stat["stdev"]
        count = stat["count"]
        percent = duration / total
        writer.add_row(row=[lap, duration, stdev, count, f"{percent:.1%}"])

    return writer.get_string()
