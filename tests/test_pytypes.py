from collections.abc import Mapping

import pytest

from puyapy.awst_build import pytypes
from tests.utils.stubs_ast import build_stubs_classes

KNOWN_SYMBOLS_WITHOUT_PYTYPES = [
    "algopy.arc4._ABIEncoded",
    "algopy.arc4._ABICallProtocolType",
    "algopy.arc4._StructMeta",
    "algopy.arc4._UIntN",
    "algopy.gtxn._GroupTransaction",
    "algopy.itxn._InnerTransaction",
    "algopy._template_variables._TemplateVarGeneric",
    "algopy._transaction._ApplicationProtocol",
    "algopy._transaction._AssetConfigProtocol",
    "algopy._transaction._AssetFreezeProtocol",
    "algopy._transaction._AssetTransferProtocol",
    "algopy._transaction._KeyRegistrationProtocol",
    "algopy._transaction._PaymentProtocol",
    "algopy._transaction._TransactionBaseProtocol",
]


def _stub_class_names_and_predefined_aliases() -> list[str]:
    class_nodes = build_stubs_classes()
    return [c for c in class_nodes if c not in KNOWN_SYMBOLS_WITHOUT_PYTYPES]


@pytest.fixture(scope="session")
def builtins_registry() -> Mapping[str, pytypes.PyType]:
    return pytypes.builtins_registry()


@pytest.mark.parametrize("fullname", _stub_class_names_and_predefined_aliases(), ids=str)
def test_stub_class_names_lookup(
    builtins_registry: Mapping[str, pytypes.PyType], fullname: str
) -> None:
    assert fullname in builtins_registry, f"{fullname} is missing from pytypes"
