import random
import typing
from collections.abc import Callable

import algokit_utils as au
import attrs
import pytest
from algokit_abi import abi

from tests import TEST_CASES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_TEST_CASE = TEST_CASES_DIR / "global_map"

IntToObject = Callable[[int], object]


@attrs.frozen
class GlobalMapClient:
    client: au.AppClient
    key: IntToObject
    value: IntToObject

    def call(self, method: str, *args: object) -> object:
        params = au.AppClientMethodCallParams(
            method=method,
            args=args,
            note=random.randbytes(8),
        )
        return self.client.send.call(params).abi_return

    def get(self, key: int) -> object:
        return self.call("get", self.key(key))

    def get_with_default(self, key: int, default: int) -> object:
        return self.call("get_with_default", self.key(key), self.value(default))

    def set(self, key: int, value: int) -> None:
        self.call("set", self.key(key), self.value(value))

    def delete(self, key: int) -> None:
        self.call("delete", self.key(key))

    def in_(self, key: int) -> object:
        return self.call("in_", self.key(key))

    def prefix(self) -> object:
        return self.call("prefix")

    def maybe(self, key: int) -> tuple[object, bool]:
        result = self.call("maybe", self.key(key))
        return typing.cast(tuple[object, bool], result)

    def get_via_state(self, key: int) -> object:
        return self.call("get_via_state", self.key(key))


def identity(value: int) -> object:
    return value


@attrs.frozen(repr=False)
class _TestCase:
    contract: str
    key: IntToObject = identity
    value: IntToObject = identity


def itoa(value: int) -> object:
    return str(value).encode("utf8")


def int_to_account(value: int) -> object:
    return value.to_bytes(length=32)


def int_to_struct(value: int) -> object:
    return {"foo": value, "bar": value.to_bytes(length=4)}


_TEST_CASES = [
    _TestCase("bytes", key=itoa, value=itoa),
    _TestCase("account_struct", key=int_to_account, value=int_to_struct),
    _TestCase("uint64"),
]


@pytest.fixture(params=_TEST_CASES, ids=lambda x: x.contract)
def global_map_test_case(request: pytest.FixtureRequest) -> _TestCase:
    assert isinstance(request.param, _TestCase)
    return request.param


@pytest.fixture
def arc_56(global_map_test_case: _TestCase) -> au.Arc56Contract:
    path = _TEST_CASE / f"{global_map_test_case.contract}.py"
    arc_56 = compile_arc56(path)

    # work around ARC-56 limitation that it can't describe structs in a tuple
    get_method = arc_56.get_abi_method("get")
    value_type = get_method.returns.type
    assert isinstance(value_type, abi.ABIType)

    maybe_method = arc_56.get_abi_method("maybe")
    maybe_method.returns.type = abi.TupleType(elements=(value_type, abi.BoolType()))
    return arc_56


@pytest.fixture
def client(
    deployer: Deployer,
    arc_56: au.Arc56Contract,
    global_map_test_case: _TestCase,
) -> GlobalMapClient:
    au_client = deployer.create(arc_56).client
    return GlobalMapClient(
        client=au_client,
        key=global_map_test_case.key,
        value=global_map_test_case.value,
    )


def test_get_without_set(client: GlobalMapClient) -> None:
    with pytest.raises(au.LogicError, match="check self.map entry exists\t\t<-- Error"):
        client.get(0)


def test_get_with_default(client: GlobalMapClient) -> None:
    assert client.get_with_default(0, 3) == client.value(3)
    client.set(0, 2)
    assert client.get_with_default(0, 3) == client.value(2)


def test_get_after_set(client: GlobalMapClient) -> None:
    for i in range(3):
        client.set(i, i)
        assert client.get(i) == client.value(i)
        assert client.get_via_state(i) == client.value(i)


def test_delete(client: GlobalMapClient) -> None:
    client.set(42, 3)
    assert client.get(42) == client.value(3)
    client.delete(42)
    with pytest.raises(au.LogicError, match="check self.map entry exists\t\t<-- Error"):
        client.get(42)


def test_in(client: GlobalMapClient) -> None:
    assert client.in_(0) is False
    client.set(0, 123)
    assert client.in_(0) is True


def test_maybe(client: GlobalMapClient) -> None:
    value, exists = client.maybe(0)
    assert exists is False

    client.set(0, 42)

    value, exists = client.maybe(0)
    assert exists is True
    assert value == client.value(42)


def test_prefix(client: GlobalMapClient) -> None:
    assert client.prefix() == b"map"
