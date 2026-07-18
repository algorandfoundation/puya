import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_ARC4_TYPES = EXAMPLES_DIR / "devportal" / "arc4_types"


def _client(deployer: Deployer, class_name: str) -> au.AppClient:
    return deployer.create((_ARC4_TYPES, class_name)).client


def _call(client: au.AppClient, method: str, args: list[object] | None = None) -> object:
    return client.send.call(
        au.AppClientMethodCallParams(method=method, args=args or [])
    ).abi_return


# --- Arc4Types ---------------------------------------------------------------


def test_add_arc4_uint64(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Types")
    assert _call(client, "add_arc4_uint64", [10, 32]) == 42


def test_add_arc4_uint_n(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Types")
    # uint8 + uint16 + uint32 + uint64
    assert _call(client, "add_arc4_uint_n", [1, 2, 3, 4]) == 10


def test_add_arc4_biguint_n(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Types")
    assert _call(client, "add_arc4_biguint_n", [100, 200, 300]) == 600


def test_arc4_byte_increments(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Types")
    # arc4.Byte decodes to a single raw byte
    assert _call(client, "arc4_byte", [41]) == (42).to_bytes(1, "big")


def test_arc4_address_balance(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _client(deployer, "Arc4Types")
    balance = _call(client, "arc4_address_balance", [account.addr])
    assert isinstance(balance, int)
    assert balance > 0


def test_arc4_address_roundtrip(deployer: Deployer, account: au.AddressWithSigners) -> None:
    client = _client(deployer, "Arc4Types")
    result = _call(client, "arc4_address_roundtrip", [account.addr])
    assert result == account.addr


# --- Arc4StaticArray ---------------------------------------------------------


def test_arc4_static_array(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4StaticArray")
    # method asserts internally and returns None; success means assertions held
    assert _call(client, "arc4_static_array") is None


# --- Arc4DynamicArray --------------------------------------------------------


def test_goodbye(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4DynamicArray")
    goodbye = _call(client, "goodbye", ["Alice"])
    assert isinstance(goodbye, list)
    assert list(goodbye) == ["Good bye ", "Alice"]


def test_hello_concatenates(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4DynamicArray")
    # dynamic_string_array = ["Hello "] then extended with [name, "!"]
    assert _call(client, "hello", ["world"]) == "Hello world!"


def test_arc4_dynamic_bytes(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4DynamicArray")
    # start b"\xff\xff\xff" -> set [0]=0 -> b"\x00\xff\xff"
    # extend b"\xaa\xbb\xcc" -> b"\x00\xff\xff\xaa\xbb\xcc"
    # pop -> b"\x00\xff\xff\xaa\xbb" ; append 255 -> b"\x00\xff\xff\xaa\xbb\xff"
    result = _call(client, "arc4_dynamic_bytes")
    assert result == b"\x00\xff\xff\xaa\xbb\xff"


# --- Arc4Struct --------------------------------------------------------------


def test_add_and_complete_todo(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Struct")

    todos = _call(client, "add_todo", ["buy milk"])
    assert isinstance(todos, list)
    assert [tuple(t) for t in todos] == [("buy milk", False)]

    todos = _call(client, "add_todo", ["walk dog"])
    assert isinstance(todos, list)
    assert [tuple(t) for t in todos] == [("buy milk", False), ("walk dog", False)]

    assert _call(client, "complete_todo", ["buy milk"]) is None

    completed = _call(client, "return_todo", ["buy milk"])
    # a returned arc4.Struct decodes as a mapping of field name -> value
    assert isinstance(completed, dict)
    assert dict(completed) == {"task": "buy milk", "completed": True}

    # untouched todo stays incomplete
    walk_dog = _call(client, "return_todo", ["walk dog"])
    assert isinstance(walk_dog, dict)
    assert dict(walk_dog) == {
        "task": "walk dog",
        "completed": False,
    }


def test_return_todo_missing_errors(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Struct")
    with pytest.raises(au.LogicError, match="todo not found"):
        _call(client, "return_todo", ["nonexistent"])


def test_complete_todo_missing_is_noop(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Struct")
    _call(client, "add_todo", ["buy milk"])

    # completing a task that is not in the list succeeds without changes
    assert _call(client, "complete_todo", ["nonexistent"]) is None

    existing = _call(client, "return_todo", ["buy milk"])
    assert isinstance(existing, dict)
    assert dict(existing) == {"task": "buy milk", "completed": False}


# --- Arc4Tuple ---------------------------------------------------------------


def test_add_and_return_contact_info(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Tuple")

    contact = ("Alice", "alice@something.com", 555_555_555)
    phone = _call(client, "add_contact_info", [contact])
    assert phone == 555_555_555

    returned_contact = _call(client, "return_contact")
    assert isinstance(returned_contact, list | tuple)
    assert tuple(returned_contact) == contact


def test_add_contact_info_rejects_wrong_values(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Tuple")
    # method asserts name == "Alice"
    with pytest.raises(au.LogicError):
        _call(
            client,
            "add_contact_info",
            [("Bob", "alice@something.com", 555_555_555)],
        )


# --- Arc4Codec ---------------------------------------------------------------


def test_encode_decode_roundtrip(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Codec")
    assert _call(client, "encode_decode", [123456789]) == 123456789


def test_decode_unvalidated(deployer: Deployer) -> None:
    client = _client(deployer, "Arc4Codec")
    # arc4.UInt64 encodes as 8 big-endian bytes
    raw = (42).to_bytes(8, "big")
    assert _call(client, "decode_unvalidated", [raw]) == 42
