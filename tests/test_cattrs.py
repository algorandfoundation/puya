import pytest
from _pytest.mark import ParameterSet
from puya.awst import nodes, serialize
from puya.awst.to_code_visitor import ToCodeVisitor

from tests import EXAMPLES_DIR, TEST_CASES_DIR
from tests.utils import get_awst_cache


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    modules = [
        *get_awst_cache(EXAMPLES_DIR).module_awst,
        *get_awst_cache(TEST_CASES_DIR).module_awst,
    ]
    params = [ParameterSet.param(module, id=module.id) for module in modules]
    metafunc.parametrize("node", params)


def test_cattrs(node: nodes.RootNode) -> None:
    awst = [node]
    json = serialize.awst_to_json(awst)
    cloned = serialize.awst_from_json(json)

    assert ToCodeVisitor().visit_module(cloned) == ToCodeVisitor().visit_module(awst)
    assert cloned == awst
