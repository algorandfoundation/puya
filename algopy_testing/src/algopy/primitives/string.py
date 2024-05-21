from __future__ import annotations

from algopy.utils import as_string


class String:
    """
    Represents a UTF-8 encoded string backed by Bytes, accessible via .bytes.

    Works with str literals instead of bytes literals. Due to lack of AVM support for unicode,
    indexing and length operations are not supported. Use .bytes.length for byte length.
    """

    value: str

    def __init__(self, value: str = "") -> None:
        self.value = as_string(value)

    def __repr__(self) -> str:
        return repr(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: object) -> bool:
        return self.value == as_string(other)

    def __contains__(self, item: object) -> bool:
        return as_string(item) in self.value

    def __add__(self, other: String | str) -> String:
        return String(self.value + as_string(other))

    def __radd__(self, other: String | str) -> String:
        return String(as_string(other) + self.value)

    def startswith(self, prefix: String | str) -> bool:
        return self.value.startswith(as_string(prefix))

    def endswith(self, suffix: String | str) -> bool:
        return self.value.endswith(as_string(suffix))

    def join(self, others: tuple[String, ...], /) -> String:
        return String(self.value.join(map(as_string, others)))

    @property
    def bytes(self) -> bytes:
        return self.value.encode("utf-8")
