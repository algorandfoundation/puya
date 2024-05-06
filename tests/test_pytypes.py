import pytest
from puya.awst_build import pytypes

from tests import VCS_ROOT

_STUB_SUFFIX = ".pyi"


def stub_class_names_and_predefined_aliases() -> list[str]:
    from mypy import build, find_sources, fscache, nodes
    from puya.compile import get_mypy_options

    stubs_dir = (VCS_ROOT / "stubs" / "algopy-stubs").resolve()
    mypy_options = get_mypy_options()
    fs_cache = fscache.FileSystemCache()
    mypy_build_sources = find_sources.create_source_list(
        paths=[str(stubs_dir)], options=mypy_options, fscache=fs_cache
    )
    build_result = build.build(sources=mypy_build_sources, options=mypy_options, fscache=fs_cache)
    result = set()

    algopy_module = build_result.files["algopy"]
    modules_to_visit = [algopy_module]
    seen_modules = set()
    while modules_to_visit:
        module = modules_to_visit.pop()
        if module in seen_modules:
            continue
        seen_modules.add(module)
        for name, symbol in module.names.items():
            if name.startswith("_") or symbol.module_hidden or symbol.kind != nodes.GDEF:
                continue
            match symbol.node:
                case nodes.MypyFile() as new_module:
                    modules_to_visit.append(new_module)
                case nodes.TypeAlias(fullname=alias_name):
                    result.add(alias_name)
                case nodes.TypeInfo(fullname=class_name):
                    result.add(class_name)
    return sorted(result)


@pytest.mark.parametrize(
    "fullname",
    stub_class_names_and_predefined_aliases(),
    ids=str,
)
def test_stub_class_names_lookup(fullname: str) -> None:
    assert pytypes.lookup(fullname) is not None, f"{fullname} is missing from pytypes"
