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

_TEST_CASE = TEST_CASES_DIR / "local_map"

IntToObject = Callable[[int], object]


@attrs.frozen
class LocalMapClient:
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

    def get(self, account: str, key: int) -> object:
        return self.call("get", account, self.key(key))

    def get_with_default(self, account: str, key: int, default: int) -> object:
        return self.call("get_with_default", account, self.key(key), self.value(default))

    def set(self, account: str, key: int, value: int) -> None:
        self.call("set", account, self.key(key), self.value(value))

    def delete(self, account: str, key: int) -> None:
        self.call("delete", account, self.key(key))

    def in_(self, account: str, key: int) -> object:
        return self.call("in_", account, self.key(key))

    def prefix(self) -> object:
        return self.call("prefix")

    def maybe(self, account: str, key: int) -> tuple[object, bool]:
        result = self.call("maybe", account, self.key(key))
        return typing.cast(tuple[object, bool], result)

    def get_via_state(self, account: str, key: int) -> object:
        return self.call("get_via_state", account, self.key(key))


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
def local_map_test_case(request: pytest.FixtureRequest) -> _TestCase:
    assert isinstance(request.param, _TestCase)
    return request.param


@pytest.fixture
def arc_56(local_map_test_case: _TestCase) -> au.Arc56Contract:
    path = _TEST_CASE / f"{local_map_test_case.contract}.py"
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
    local_map_test_case: _TestCase,
) -> LocalMapClient:
    au_client = deployer.create(
        arc_56, method="create", on_complete=au.OnApplicationComplete.OptIn
    ).client
    return LocalMapClient(
        client=au_client,
        key=local_map_test_case.key,
        value=local_map_test_case.value,
    )


@pytest.fixture
def sender(deployer: Deployer) -> str:
    return deployer.account.addr


def test_get_without_set(client: LocalMapClient, sender: str) -> None:
    with pytest.raises(
        au.LogicError, match="check self.map entry exists for account\t\t<-- Error"
    ):
        client.get(sender, 0)


def test_get_with_default(client: LocalMapClient, sender: str) -> None:
    assert client.get_with_default(sender, 0, 3) == client.value(3)
    client.set(sender, 0, 2)
    assert client.get_with_default(sender, 0, 3) == client.value(2)


def test_get_after_set(client: LocalMapClient, sender: str) -> None:
    for i in range(3):
        client.set(sender, i, i)
        assert client.get(sender, i) == client.value(i)
        assert client.get_via_state(sender, i) == client.value(i)


def test_delete(client: LocalMapClient, sender: str) -> None:
    client.set(sender, 42, 3)
    assert client.get(sender, 42) == client.value(3)
    client.delete(sender, 42)
    with pytest.raises(
        au.LogicError, match="check self.map entry exists for account\t\t<-- Error"
    ):
        client.get(sender, 42)


def test_in(client: LocalMapClient, sender: str) -> None:
    assert client.in_(sender, 0) is False
    client.set(sender, 0, 123)
    assert client.in_(sender, 0) is True


def test_maybe(client: LocalMapClient, sender: str) -> None:
    value, exists = client.maybe(sender, 0)
    assert exists is False

    client.set(sender, 0, 42)

    value, exists = client.maybe(sender, 0)
    assert exists is True
    assert value == client.value(42)


def test_prefix(client: LocalMapClient) -> None:
    assert client.prefix() == b"map"
