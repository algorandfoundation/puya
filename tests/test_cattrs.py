from puya.awst import nodes, serialize
from puya.awst.to_code_visitor import ToCodeVisitor

from tests.utils import PuyaTestCase, get_awst_cache


def test_cattrs(test_case: PuyaTestCase) -> None:
    cache = get_awst_cache(test_case.root)
    awst = [a for a in cache.module_awst if _is_case_awst(test_case, a)]
    json = serialize.awst_to_json(awst)
    cloned = serialize.awst_from_json(json)

    assert ToCodeVisitor().visit_module(cloned) == ToCodeVisitor().visit_module(awst)
    assert cloned == awst


def _is_case_awst(case: PuyaTestCase, awst: nodes.RootNode) -> bool:
    path = awst.source_location.file
    return bool(path and path.is_relative_to(case.path))
