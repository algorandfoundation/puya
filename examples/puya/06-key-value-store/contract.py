"""Example 06: Key-Value Store

This example demonstrates Box and BoxMap storage with CRUD operations.

Features:
- Box — single named box for typed storage (UInt64, String, Bytes)
- BoxMap — key-prefixed map of boxes
- Box CRUD — .value setter/getter, bool() existence check, del
- Box slicing — .extract(), .replace(), value[start:end]
- Box utilities — .length, .get() with default, .create()
- StateTotals — explicit state allocation
- GlobalState with dynamic key access

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import Box, BoxMap, Bytes, GlobalState, StateTotals, String, Txn, UInt64, arc4, op


# example: KEY_VALUE_STORE
class KeyValueStore(
    arc4.ARC4Contract,
    state_totals=StateTotals(global_uints=1),
):
    """ARC4 contract demonstrating Box, BoxMap, and GlobalState storage."""

    def __init__(self) -> None:
        self.total_ops = GlobalState(UInt64(0))
        self.counter = Box(UInt64)
        self.label = Box(String, key="label")
        self.profiles = BoxMap(UInt64, String, key_prefix="p_")
        self.blob = Box(Bytes, key="blob")

    def _assert_creator(self) -> None:
        """Guard — only the contract creator may call mutation methods."""
        assert Txn.sender == op.Global.creator_address, "creator only"

    # --- Box CRUD ---

    @arc4.abimethod
    def set_counter(self, value: UInt64) -> None:
        """Demonstrate Box .value setter — write a value to the box.

        Args:
            value: the UInt64 value to store
        """
        self._assert_creator()
        self.counter.value = value
        self.total_ops.value += 1

    @arc4.abimethod
    def get_counter(self) -> UInt64:
        """Demonstrate Box .value getter — read the box contents.

        Returns:
            the stored UInt64 value
        """
        return self.counter.value

    @arc4.abimethod
    def increment_counter(self) -> UInt64:
        """Demonstrate Box read-modify-write — increment and return.

        Returns:
            the new counter value after incrementing
        """
        self._assert_creator()
        self.counter.value += 1
        self.total_ops.value += 1
        return self.counter.value

    @arc4.abimethod
    def counter_exists(self) -> bool:
        """Demonstrate Box existence check — bool(box).

        Returns:
            True if the counter box exists
        """
        return bool(self.counter)

    @arc4.abimethod
    def delete_counter(self) -> None:
        """Demonstrate Box deletion — del box.value."""
        self._assert_creator()
        del self.counter.value

    # --- Box with get/default ---

    @arc4.abimethod
    def set_label(self, value: String) -> None:
        """Demonstrate Box .value setter for String type.

        Args:
            value: the string to store
        """
        self._assert_creator()
        self.label.value = value

    @arc4.abimethod
    def get_label(self) -> String:
        """Demonstrate Box .value getter for String type.

        Returns:
            the stored string value
        """
        return self.label.value

    @arc4.abimethod
    def get_label_or_default(self, default: String) -> String:
        """Demonstrate Box .get() with default — return value or fallback.

        Args:
            default: fallback value if box doesn't exist

        Returns:
            the stored string, or default if box doesn't exist
        """
        return self.label.get(default=default)

    @arc4.abimethod
    def delete_label(self) -> None:
        """Demonstrate Box deletion for String type."""
        self._assert_creator()
        del self.label.value

    # --- BoxMap CRUD ---

    @arc4.abimethod
    def map_set(self, key: UInt64, value: String) -> None:
        """Demonstrate BoxMap write — set a key-value pair.

        Args:
            key: the map key
            value: the string to store
        """
        self._assert_creator()
        self.profiles[key] = value
        self.total_ops.value += 1

    @arc4.abimethod
    def map_get(self, key: UInt64) -> String:
        """Demonstrate BoxMap read — get a value by key.

        Args:
            key: the map key to look up

        Returns:
            the stored string value
        """
        return self.profiles[key]

    @arc4.abimethod
    def map_exists(self, key: UInt64) -> bool:
        """Demonstrate BoxMap existence check.

        Args:
            key: the map key to check

        Returns:
            True if the key exists in the map
        """
        return key in self.profiles

    @arc4.abimethod
    def map_delete(self, key: UInt64) -> None:
        """Demonstrate BoxMap deletion.

        Args:
            key: the map key to delete
        """
        self._assert_creator()
        del self.profiles[key]

    @arc4.abimethod
    def map_get_default(self, key: UInt64, default: String) -> String:
        """Demonstrate BoxMap .get() with default — return value or fallback.

        Args:
            key: the map key to look up
            default: fallback value if key doesn't exist

        Returns:
            the stored string, or default if key doesn't exist
        """
        return self.profiles.get(key, default=default)

    # --- BoxRef (Box[Bytes]) CRUD ---

    @arc4.abimethod
    def blob_create(self, size: UInt64) -> None:
        """Demonstrate Box.create() — allocate storage for the box.

        Args:
            size: byte length for the new box
        """
        self._assert_creator()
        assert self.blob.create(size=size)

    @arc4.abimethod
    def blob_set(self, value: Bytes) -> None:
        """Demonstrate Box .value setter for raw bytes.

        Args:
            value: raw bytes to store in the box
        """
        self._assert_creator()
        self.blob.value = value

    @arc4.abimethod
    def blob_extract(self, offset: UInt64, length: UInt64) -> Bytes:
        """Demonstrate .extract() — read a slice of bytes from a box.

        Args:
            offset: byte offset to begin reading
            length: number of bytes to read

        Returns:
            the extracted byte slice
        """
        return self.blob.extract(offset, length)

    @arc4.abimethod
    def blob_replace(self, offset: UInt64, value: Bytes) -> None:
        """Demonstrate .replace() — overwrite bytes at a given offset.

        Args:
            offset: byte offset to begin overwriting
            value: replacement bytes
        """
        self._assert_creator()
        self.blob.replace(offset, value)

    @arc4.abimethod
    def blob_slice(self, start: UInt64, end: UInt64) -> Bytes:
        """Demonstrate box slicing — value[start:end].

        Args:
            start: start index (inclusive)
            end: end index (exclusive)

        Returns:
            the sliced byte range
        """
        return self.blob.value[start:end]

    @arc4.abimethod
    def blob_length(self) -> UInt64:
        """Demonstrate .length — get the byte length of a box.

        Returns:
            the current byte length of the box
        """
        return self.blob.length

    @arc4.abimethod
    def blob_delete(self) -> None:
        """Demonstrate Box deletion for raw bytes."""
        self._assert_creator()
        del self.blob.value

    # --- Global state ---

    @arc4.abimethod
    def get_total_ops(self) -> UInt64:
        """Read the total operations counter from GlobalState.

        Returns:
            the total number of write operations performed
        """
        return self.total_ops.value


# example: KEY_VALUE_STORE
