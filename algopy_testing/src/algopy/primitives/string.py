from __future__ import annotations

from algopy import Bytes
from algopy.utils import as_string


class String:
    _bytes: Bytes

    def __init__(self, value: str = "") -> None:
        self._bytes = Bytes(value.encode("utf-8"))

    def __repr__(self) -> str:
        return repr(self._bytes)

    def __str__(self) -> str:
        return str(self._bytes)

    def __bool__(self) -> bool:
        return bool(self._bytes)

    def __eq__(self, other: object) -> bool:
        return self._bytes == Bytes(as_string(other).encode("utf-8"))

    def __contains__(self, item: object) -> bool:
        return as_string(item) in str(self._bytes)

    def __len__(self) -> int:
        raise NotImplementedError("Length operation is not supported for UTF-8 strings.")

    def starts_with(self, prefix: String | str) -> bool:
        return str(self._bytes).startswith(as_string(prefix))

    def ends_with(self, suffix: String | str) -> bool:
        return str(self._bytes).endswith(as_string(suffix))

    def join(self, others: tuple[String, ...], /) -> String:
        byte_values = [as_string(s) for s in others]
        return String(f"{self._bytes}".join(byte_values))

    @property
    def bytes(self) -> bytes:
        return str(self._bytes).encode("utf-8")

    def __add__(self, other: String | str) -> String:
        return String((self._bytes + Bytes(as_string(other).encode("utf-8"))).decode("utf-8"))
