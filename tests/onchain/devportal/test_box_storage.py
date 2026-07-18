import random

import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_BOX_STORAGE = EXAMPLES_DIR / "devportal" / "box_storage"

_BoxRefs = list[au.BoxReference | au.BoxIdentifier]

# static box keys declared on the contract
_BOX_INT = b"box_int"
_BOX_DYNAMIC_BYTES = b"b"
_BOX_STRING = b"BOX_STRING"
_BOX_BYTES = b"BOX_BYTES"
_BOX_NESTED = b"box_nested"


def _int_key(value: int) -> bytes:
    """BoxMap[UInt64, ...] keys are 8-byte big-endian (key_prefix='')."""
    return value.to_bytes(8, "big")


def _struct_key(value: int) -> bytes:
    """BoxMap[arc4.UInt64, UserStruct] keys are 'users' + 8-byte big-endian."""
    return b"users" + value.to_bytes(8, "big")


def _empty(n: int) -> _BoxRefs:
    # padding box references let a single txn touch additional boxes
    return [au.BoxReference(0, b"")] * n


def _params(
    method: str,
    *args: object,
    box_refs: _BoxRefs | None = None,
    fee: au.AlgoAmount | None = None,
) -> au.AppClientMethodCallParams:
    return au.AppClientMethodCallParams(
        method=method,
        args=list(args),
        box_references=box_refs,
        static_fee=fee,
        note=random.randbytes(8),
    )


@pytest.fixture
def client(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> au.AppClient:
    client = deployer.create(_BOX_STORAGE).client
    # boxes raise the app's minimum balance, so the app account must be funded
    localnet.send.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_algo(2),
        )
    )
    return client


# --- Box[UInt64] ----------------------------------------------------------


def test_set_and_get_box(client: au.AppClient) -> None:
    refs: _BoxRefs = [_BOX_INT]
    client.send.call(_params("set_box", 99, box_refs=refs))
    result = client.send.call(_params("get_box", box_refs=refs))
    assert result.abi_return == 99


def test_get_box_missing_fails(client: au.AppClient) -> None:
    # reading `.value` of a box that was never created fails on-chain
    with pytest.raises(au.LogicError):
        client.send.call(_params("get_box", box_refs=[_BOX_INT]))


def test_maybe_box(client: au.AppClient) -> None:
    refs: _BoxRefs = [_BOX_INT]
    absent = client.send.call(_params("maybe_box", box_refs=refs))
    # (value, exists) -> value undefined, exists False
    assert absent.abi_return == (0, False)

    client.send.call(_params("set_box", 7, box_refs=refs))
    present = client.send.call(_params("maybe_box", box_refs=refs))
    assert present.abi_return == (7, True)


def test_box_int_length(client: au.AppClient) -> None:
    refs: _BoxRefs = [_BOX_INT]
    client.send.call(_params("set_box", 1, box_refs=refs))
    # a UInt64 is 8 bytes
    result = client.send.call(_params("box_int_length", box_refs=refs))
    assert result.abi_return == 8


def test_key_box(client: au.AppClient) -> None:
    result = client.send.call(_params("key_box", box_refs=[_BOX_INT]))
    assert result.abi_return == _BOX_INT


def test_exist_box(client: au.AppClient) -> None:
    refs: _BoxRefs = [_BOX_INT, _BOX_DYNAMIC_BYTES, _BOX_STRING, _BOX_BYTES]
    absent = client.send.call(_params("exist_box", box_refs=refs))
    assert absent.abi_return == (False, False, False, False)

    client.send.call(_params("set_box_example", 10, b"\x01\x02", "hi", box_refs=refs))
    present = client.send.call(_params("exist_box", box_refs=refs))
    assert present.abi_return == (True, True, True, True)


# --- explicit-key boxes ---------------------------------------------------


def test_set_and_get_box_example(client: au.AppClient) -> None:
    refs: _BoxRefs = [_BOX_INT, _BOX_DYNAMIC_BYTES, _BOX_STRING, _BOX_BYTES]
    client.send.call(_params("set_box_example", 40, b"\xaa\xbb", "World", box_refs=refs))
    result = client.send.call(_params("get_box_example", box_refs=refs))
    # set_box_example does `box_int += 3` after assigning 40 -> 43
    assert result.abi_return == (43, b"\xaa\xbb", "World")


def test_key_box_example(client: au.AppClient) -> None:
    # asserts the explicit keys b, BOX_STRING, BOX_BYTES internally
    refs: _BoxRefs = [_BOX_DYNAMIC_BYTES, _BOX_STRING, _BOX_BYTES]
    client.send.call(_params("key_box_example", box_refs=refs))


def test_delete_box(client: au.AppClient) -> None:
    refs: _BoxRefs = [_BOX_INT, _BOX_DYNAMIC_BYTES, _BOX_STRING, _BOX_BYTES]
    client.send.call(_params("set_box_example", 5, b"\x09", "x", box_refs=refs))
    # delete_box removes box_int / box_dynamic_bytes / box_string and asserts
    # the .get defaults internally
    client.send.call(_params("delete_box", box_refs=refs))
    exists = client.send.call(_params("exist_box", box_refs=refs))
    assert exists.abi_return == (False, False, False, True)


# --- BoxMap[UInt64, String] -----------------------------------------------


def test_set_and_get_item_box_map(client: au.AppClient) -> None:
    refs: _BoxRefs = [_int_key(5)]
    client.send.call(_params("set_box_map", 5, "five", box_refs=refs))
    result = client.send.call(_params("get_item_box_map", 5, box_refs=refs))
    assert result.abi_return == "five"


def test_get_box_map_default(client: au.AppClient) -> None:
    # get_box_map reads key 1 with default "default"
    refs: _BoxRefs = [_int_key(1)]
    absent = client.send.call(_params("get_box_map", box_refs=refs))
    assert absent.abi_return == "default"

    client.send.call(_params("set_box_map", 1, "one", box_refs=refs))
    present = client.send.call(_params("get_box_map", box_refs=refs))
    assert present.abi_return == "one"


def test_maybe_box_map(client: au.AppClient) -> None:
    refs: _BoxRefs = [_int_key(1)]
    absent = client.send.call(_params("maybe_box_map", box_refs=refs))
    assert absent.abi_return == ("", False)

    client.send.call(_params("set_box_map", 1, "hello", box_refs=refs))
    present = client.send.call(_params("maybe_box_map", box_refs=refs))
    assert present.abi_return == ("hello", True)


def test_box_map_exists(client: au.AppClient) -> None:
    refs: _BoxRefs = [_int_key(3)]
    absent = client.send.call(_params("box_map_exists", 3, box_refs=refs))
    assert absent.abi_return is False

    client.send.call(_params("set_box_map", 3, "v", box_refs=refs))
    present = client.send.call(_params("box_map_exists", 3, box_refs=refs))
    assert present.abi_return is True


def test_box_map_length(client: au.AppClient) -> None:
    refs: _BoxRefs = [_int_key(8)]
    # length is 0 for a missing key
    absent = client.send.call(_params("box_map_length", 8, box_refs=refs))
    assert absent.abi_return == 0

    client.send.call(_params("set_box_map", 8, "abcd", box_refs=refs))
    # box_map values are the native algopy String, stored as raw UTF-8 bytes
    # with no length prefix -> "abcd" is 4 bytes
    present = client.send.call(_params("box_map_length", 8, box_refs=refs))
    assert present.abi_return == 4


def test_delete_box_map(client: au.AppClient) -> None:
    refs: _BoxRefs = [_int_key(2)]
    client.send.call(_params("set_box_map", 2, "two", box_refs=refs))
    client.send.call(_params("delete_box_map", 2, box_refs=refs))
    result = client.send.call(_params("box_map_exists", 2, box_refs=refs))
    assert result.abi_return is False


def test_get_item_box_map_missing_fails(client: au.AppClient) -> None:
    # indexing a missing BoxMap key fails on-chain
    with pytest.raises(au.LogicError):
        client.send.call(_params("get_item_box_map", 404, box_refs=[_int_key(404)]))


def test_key_prefix_box_map(client: au.AppClient) -> None:
    # box_map was declared with key_prefix=""
    result = client.send.call(_params("key_prefix_box_map"))
    assert result.abi_return == b""


def test_read_box_passed_to_subroutine(client: au.AppClient) -> None:
    # subroutine reads box_map[key + 1]
    refs: _BoxRefs = [_int_key(10), _int_key(11)]
    client.send.call(_params("set_box_map", 11, "eleven", box_refs=[_int_key(11)]))
    result = client.send.call(_params("read_box_passed_to_subroutine", 10, box_refs=refs))
    assert result.abi_return == "eleven"


def test_read_box_passed_to_subroutine_missing_fails(client: au.AppClient) -> None:
    # the subroutine indexes box_map[key + 1], which was never written
    with pytest.raises(au.LogicError):
        client.send.call(
            _params(
                "read_box_passed_to_subroutine",
                500,
                box_refs=[_int_key(500), _int_key(501)],
            )
        )


# --- BoxMap[arc4.UInt64, UserStruct] --------------------------------------


def test_set_and_get_box_map_struct(client: au.AppClient) -> None:
    refs: _BoxRefs = [_struct_key(1)]
    user = ("alice", 1, 2)  # UserStruct(name, id, asset)
    set_result = client.send.call(_params("set_box_map_struct", 1, user, box_refs=refs))
    assert set_result.abi_return is True

    get_result = client.send.call(_params("get_box_map_struct", 1, box_refs=refs))
    # UserStruct is an arc4.Struct, so the return decodes to a field dict
    assert get_result.abi_return == {"name": "alice", "id": 1, "asset": 2}


def test_get_box_map_struct_missing_fails(client: au.AppClient) -> None:
    # indexing a missing BoxMap struct key fails on-chain
    with pytest.raises(au.LogicError):
        client.send.call(_params("get_box_map_struct", 404, box_refs=[_struct_key(404)]))


def test_box_map_struct_exists(client: au.AppClient) -> None:
    refs: _BoxRefs = [_struct_key(2)]
    absent = client.send.call(_params("box_map_struct_exists", 2, box_refs=refs))
    assert absent.abi_return is False

    client.send.call(_params("set_box_map_struct", 2, ("bob", 9, 3), box_refs=refs))
    present = client.send.call(_params("box_map_struct_exists", 2, box_refs=refs))
    assert present.abi_return is True


def test_box_map_struct_length(client: au.AppClient) -> None:
    # method writes key 0 internally and asserts the on-chain length
    result = client.send.call(_params("box_map_struct_length", box_refs=[_struct_key(0)]))
    assert result.abi_return is True


# --- ad-hoc boxes ---------------------------------------------------------


def test_extract_box(client: au.AppClient) -> None:
    # uses an ad-hoc Box[Bytes] keyed "blob"; splice grows the box so add fee
    client.send.call(
        _params(
            "extract_box",
            box_refs=[b"blob", *_empty(1)],
            fee=au.AlgoAmount.from_micro_algo(4_000),
        )
    )


def test_slice_box(client: au.AppClient) -> None:
    # ad-hoc Box[Bytes] keyed "scratch" plus the BOX_STRING box
    client.send.call(_params("slice_box", box_refs=[b"scratch", _BOX_STRING]))


def test_arc4_box(client: au.AppClient) -> None:
    # ad-hoc Box[StaticArray] keyed "d"
    client.send.call(_params("arc4_box", box_refs=[b"d"]))


# --- nested struct box ----------------------------------------------------


def test_nested_struct_write_and_sum(client: au.AppClient) -> None:
    refs: _BoxRefs = [_BOX_NESTED, *_empty(2)]
    fee = au.AlgoAmount.from_micro_algo(4_000)
    # nested_struct_write(value): a=value, inner.c=value+1, inner.d=value+2,
    # b=value+3, and appends 0,1,2 to inner.arr
    client.send.call(_params("nested_struct_write", 10, box_refs=refs, fee=fee))

    result = client.send.call(_params("nested_struct_sum", box_refs=refs, fee=fee))
    # a + b + inner.c + inner.d + sum(arr)
    #   = 10 + 13 + 11 + 12 + (0 + 1 + 2) = 49
    assert result.abi_return == 49


def test_nested_struct_sum_missing_fails(client: au.AppClient) -> None:
    # reading box_nested.value before any write fails on-chain
    with pytest.raises(au.LogicError):
        client.send.call(_params("nested_struct_sum", box_refs=[_BOX_NESTED]))
