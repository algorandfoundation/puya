from pathlib import Path

from puya.awst import nodes, serialize
from puya.awst.serialize import get_converter
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.log import Log, LogLevel
from puya.parse import SourceLocation
from tests.utils import PuyaTestCase, get_awst_cache


def test_cattrs(test_case: PuyaTestCase) -> None:
    cache = get_awst_cache(test_case.root)
    awst = [a for a in cache.module_awst if _is_case_awst(test_case, a)]
    json = serialize.awst_to_json(awst)
    cloned = serialize.awst_from_json(json)
    assert len(cloned) == len(awst)

    assert ToCodeVisitor().visit_module(cloned) == ToCodeVisitor().visit_module(awst)
    for cloned_, awst_ in zip(cloned, awst, strict=True):
        assert cloned_ == awst_


def _is_case_awst(case: PuyaTestCase, awst: nodes.RootNode) -> bool:
    path = awst.source_location.file
    return bool(path and path.is_relative_to(case.path))


def test_log() -> None:
    log = Log(
        level=LogLevel.info,
        message="msg",
        location=SourceLocation(
            file=Path("test").resolve(),
            line=1,
            end_line=2,
            column=3,
            end_column=4,
            comment_lines=5,
        ),
    )
    converter = get_converter()
    json = converter.dumps(log)
    clone = converter.loads(json, Log)
    assert log == clone
