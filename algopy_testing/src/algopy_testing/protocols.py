from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import algopy


class BytesBacked(typing.Protocol):
    """Represents a type that is a single bytes value"""

    @classmethod
    def from_bytes(cls, value: algopy.Bytes | bytes, /) -> typing.Self:
        """Construct an instance from the underlying bytes (no validation)"""

    @property
    def bytes(self) -> algopy.Bytes:
        """Get the underlying Bytes"""
