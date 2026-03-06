from algopy import Bytes, String, UInt64
from algopy_testing import algopy_testing_context
from contract import KeyValueStore


def _create_contract() -> KeyValueStore:
    contract = KeyValueStore()
    contract.create()
    return contract


class TestBoxCounter:
    def test_set_and_get_counter(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.set_counter(UInt64(42))
            assert contract.get_counter() == 42

    def test_increment_counter(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.set_counter(UInt64(10))
            result = contract.increment_counter()
            assert result == 11

    def test_counter_exists(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            assert contract.counter_exists() is False
            contract.set_counter(UInt64(1))
            assert contract.counter_exists() is True

    def test_delete_counter(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.set_counter(UInt64(5))
            contract.delete_counter()
            assert contract.counter_exists() is False


class TestBoxLabel:
    def test_set_and_get_label(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.set_label(String("Hello Boxes!"))
            assert contract.get_label() == String("Hello Boxes!")

    def test_get_label_or_default_missing(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            result = contract.get_label_or_default(String("(empty)"))
            assert result == String("(empty)")

    def test_get_label_or_default_existing(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.set_label(String("exists"))
            result = contract.get_label_or_default(String("(empty)"))
            assert result == String("exists")


class TestBoxMap:
    def test_map_set_and_get(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.map_set(UInt64(1), String("Alice"))
            assert contract.map_get(UInt64(1)) == String("Alice")

    def test_map_exists(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            assert contract.map_exists(UInt64(1)) is False
            contract.map_set(UInt64(1), String("Alice"))
            assert contract.map_exists(UInt64(1)) is True

    def test_map_delete(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.map_set(UInt64(1), String("Alice"))
            contract.map_delete(UInt64(1))
            assert contract.map_exists(UInt64(1)) is False

    def test_map_get_default(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            result = contract.map_get_default(UInt64(99), String("unknown"))
            assert result == String("unknown")


class TestBlob:
    def test_blob_create_and_length(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.blob_create(UInt64(32))
            assert contract.blob_length() == 32

    def test_blob_set_and_extract(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.blob_set(Bytes(b"Hello, World!"))
            result = contract.blob_extract(UInt64(0), UInt64(5))
            assert result == Bytes(b"Hello")

    def test_blob_replace(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.blob_set(Bytes(b"Hello, World!"))
            contract.blob_replace(UInt64(7), Bytes(b"Boxes"))
            result = contract.blob_extract(UInt64(0), UInt64(13))
            assert result == Bytes(b"Hello, Boxes!")

    def test_blob_slice(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.blob_set(Bytes(b"Hello, World!"))
            result = contract.blob_slice(UInt64(7), UInt64(12))
            assert result == Bytes(b"World")

    def test_blob_length(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.blob_set(Bytes(b"Hello, World!"))
            assert contract.blob_length() == 13

    def test_blob_delete(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.blob_set(Bytes(b"data"))
            contract.blob_delete()
            contract.blob_create(UInt64(10))
            assert contract.blob_length() == 10


class TestTotalOps:
    def test_total_ops_increments_on_set_counter(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.set_counter(UInt64(1))
            assert contract.get_total_ops() == 1

    def test_total_ops_increments_on_map_set(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.map_set(UInt64(1), String("Alice"))
            assert contract.get_total_ops() == 1

    def test_total_ops_accumulates(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.set_counter(UInt64(1))
            contract.increment_counter()
            contract.map_set(UInt64(1), String("Alice"))
            contract.map_set(UInt64(2), String("Bob"))
            assert contract.get_total_ops() == 4
