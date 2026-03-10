import abc
import importlib
import sys
from pathlib import Path

import _algopy_testing.models.contract as _contract_mod
import pytest

# algorand-python-testing's _ContractMeta doesn't subclass ABCMeta,
# so combining ARC4Contract with abc.ABC causes a metaclass conflict.
# Patch the metaclass before any contract is imported.
_OrigMeta = type(_contract_mod.ARC4Contract)


class _PatchedMeta(abc.ABCMeta, _OrigMeta):
    pass


_abc_impl_donor = abc.ABCMeta.__new__(abc.ABCMeta, "_D", (), {})._abc_impl
for _cls in (_contract_mod.Contract, _contract_mod.ARC4Contract):
    _cls.__class__ = _PatchedMeta
    _cls._abc_impl = _abc_impl_donor
_contract_mod._ContractMeta = _PatchedMeta

# Modules that exist in multiple test directories and need per-directory isolation.
_SHARED_MODULE_NAMES = {"contract"}


@pytest.hookimpl(tryfirst=True)
def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> None:
    _ = parent
    if not file_path.name.startswith("test_"):
        return
    test_dir = str(file_path.parent)
    # Ensure the test's own directory is first on sys.path
    if test_dir in sys.path:
        sys.path.remove(test_dir)
    sys.path.insert(0, test_dir)
    # Evict same-named modules so they get re-imported from the new sys.path
    for name in _SHARED_MODULE_NAMES:
        sys.modules.pop(name, None)
        importlib.invalidate_caches()
