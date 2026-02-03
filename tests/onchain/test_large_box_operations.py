import base64
import random
import typing

import algokit_utils as au
import attrs
import pytest

from tests import TEST_CASES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_TEST_CASE = TEST_CASES_DIR / "large_box_operations"


@attrs.frozen
class AppClient:
    client: au.AppClient

    def call(self, method: str, *args: object) -> object:
        params = au.AppClientMethodCallParams(
            method=method,
            args=args,
            note=random.randbytes(8),
            max_fee=au.AlgoAmount.from_micro_algo(10_000),
        )
        return self.client.send.call(
            params, au.SendParams(cover_app_call_inner_transaction_fees=True)
        ).abi_return


class LargeBoxClient(AppClient):
    def append(self, item: object) -> None:
        self.call("append", item)

    def concat(self, arr: list[object]) -> None:
        self.call("concat", _unpack_dicts(arr))

    def pop(self) -> object:
        return self.call("pop")

    def get(self, idx: int) -> object:
        return self.call("get", idx)

    def set(self, idx: int, value: object) -> None:
        self.call("set", idx, value)

    def verify(self, arr: list[object]) -> None:
        self.call("verify", _unpack_dicts(arr))


def _unpack_dicts(value: object) -> object:
    if isinstance(value, dict):
        return [_unpack_dicts(item) for item in value.values()]
    elif isinstance(value, list | tuple):
        return [_unpack_dicts(item) for item in value]
    else:
        return value


class ItemFactory(typing.Protocol):
    def __call__(self, index: int, /) -> object: ...


_UNDERFLOW = "- would result negative"
_OUT_OF_BOUNDS = "index out of bounds"


@attrs.frozen(repr=False)
class _TestCase:
    contract: str
    item_factory: ItemFactory


def parent_from_idx(index: int) -> object:
    return {
        "baz": index + 1,
        "simple": {"foo": index + 2, "bar": index + 3},
        "buz": index + 4,
    }


_TEST_CASES = [
    _TestCase("array_uint64", int),
    _TestCase("struct_array_uint64", int),
    _TestCase("struct_multiple_array_uint64", int),
    _TestCase("dynamic_offset_first", int),
    _TestCase("dynamic_offset_middle", int),
    _TestCase("dynamic_offset_last", int),
    _TestCase("nested", parent_from_idx),
]


@pytest.fixture(params=_TEST_CASES, ids=lambda x: x.contract)
def box_test_case(request: pytest.FixtureRequest) -> _TestCase:
    assert isinstance(request.param, _TestCase)
    return request.param


@pytest.fixture
def item_factory(box_test_case: _TestCase) -> ItemFactory:
    return box_test_case.item_factory


@pytest.fixture
def contract(box_test_case: _TestCase) -> str:
    return box_test_case.contract


@pytest.fixture
def arc_56(contract: str) -> au.Arc56Contract:
    path = _TEST_CASE / f"{contract}.py"
    return compile_arc56(path)


@pytest.fixture
def client(
    deployer: Deployer, arc_56: au.Arc56Contract, account: au.AddressWithSigners
) -> LargeBoxClient:
    au_client = deployer.create(arc_56).client
    # Fund app to cover MBR
    au_client.algorand.account.ensure_funded(
        account_to_fund=au_client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_algo(10),
    )

    app_client = LargeBoxClient(au_client)
    app_client.call("bootstrap")
    return app_client


def test_no_unexpected_box_put_get(arc_56: au.Arc56Contract) -> None:
    assert arc_56.source is not None
    approval_b64 = arc_56.source.approval
    approval = base64.b64decode(approval_b64)
    puts = approval.count(b"box_put")
    gets = approval.count(b"box_get")
    # the single box_put is from box initialization in bootstrap()
    assert puts == 1, "expected a single box_put op"

    # all contracts should not load the entire box onto the stack
    assert gets == 0, "expected no box_get ops"


def test_pop_empty(client: LargeBoxClient) -> None:
    with pytest.raises(au.LogicError, match=_UNDERFLOW):
        client.pop()


def test_get_out_of_bounds_empty(client: LargeBoxClient) -> None:
    with pytest.raises(au.LogicError, match=_OUT_OF_BOUNDS):
        client.get(1)


def test_get_out_of_bounds(client: LargeBoxClient, item_factory: ItemFactory) -> None:
    arr = [item_factory(idx) for idx in range(1, 6)]
    client.concat(arr)

    with pytest.raises(au.LogicError, match=_OUT_OF_BOUNDS):
        client.get(5)


def test_set_out_of_bounds(client: LargeBoxClient, item_factory: ItemFactory) -> None:
    arr = [item_factory(idx) for idx in range(1, 6)]
    client.concat(arr)

    with pytest.raises(au.LogicError, match=_OUT_OF_BOUNDS):
        client.set(5, arr[0])


def test_concat(client: LargeBoxClient, item_factory: ItemFactory) -> None:
    arr = [item_factory(idx) for idx in range(1, 6)]
    client.concat(arr)

    client.verify(arr)

    arr_extend = [item_factory(idx) for idx in range(6, 11)]
    client.concat(arr_extend)

    client.verify(arr + arr_extend)


def test_append(client: LargeBoxClient, item_factory: ItemFactory) -> None:
    arr = [item_factory(idx) for idx in range(1, 11)]
    for i in arr:
        client.append(i)

    client.verify(arr)


def test_concat_and_pop(client: LargeBoxClient, item_factory: ItemFactory) -> None:
    arr = [item_factory(idx) for idx in range(1, 6)]

    client.concat(arr)
    client.verify(arr)

    for _ in range(3):
        popped = arr.pop()
        assert client.pop() == popped
        client.verify(arr)


def test_concat_and_append(client: LargeBoxClient, item_factory: ItemFactory) -> None:
    arr = [item_factory(idx) for idx in range(1, 6)]

    client.concat(arr)
    client.verify(arr)

    for i in [4, 5, 6]:
        item = item_factory(i)
        arr.append(item)
        client.append(item)

    client.verify(arr)


@pytest.fixture
def nested_item_client(deployer: Deployer, account: au.AddressWithSigners) -> AppClient:
    au_client = deployer.create(_TEST_CASE / "nested_item.py").client
    # Fund app to cover MBR
    au_client.algorand.account.ensure_funded(
        account_to_fund=au_client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_algo(10),
    )

    app_client = AppClient(au_client)
    app_client.call("bootstrap")
    return app_client


def test_nested_array_item(nested_item_client: AppClient) -> None:
    nested_item_client.call("bootstrap")

    appended = []
    for i in [1, 2, 3]:
        new = {"child": {"uint": 40 + i, "bool_": i % 2 == 0}, "bar": i}
        appended.append(new)
        nested_item_client.call("append", new)

    # act / assert
    assert nested_item_client.call("nested_uint", 2) == 42
    assert nested_item_client.call("nested_bool", 1) is False
    assert nested_item_client.call("nested_bool", 2) is True
    assert nested_item_client.call("pop") == appended.pop()
    assert nested_item_client.call("pop") == appended.pop()


def test_unsupported_large_box_operations(nested_item_client: AppClient) -> None:
    # test nested array operations with large box (>4096 bytes)
    # these operations go through an array index path which is not optimised
    # so they fall back to box_get/box_put which fails for large boxes
    with pytest.raises(au.LogicError):
        nested_item_client.call("nested_arr_append", 0, 42)

    with pytest.raises(au.LogicError):
        nested_item_client.call("nested_arr_pop", 0)

    # clear padding to get box under 4096 bytes
    nested_item_client.call("clear_padding")

    # now nested array operations should work
    nested_item_client.call("nested_arr_append", 0, 100)
    nested_item_client.call("nested_arr_append", 0, 200)
    nested_item_client.call("nested_arr_append", 0, 300)

    assert nested_item_client.call("nested_arr_pop", 0) == 300
    assert nested_item_client.call("nested_arr_pop", 0) == 200
    assert nested_item_client.call("nested_arr_pop", 0) == 100
