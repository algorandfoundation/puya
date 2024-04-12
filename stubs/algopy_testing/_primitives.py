from typing import Self


class UInt64:
    """A simple class representing a 64-bit unsigned integer."""

    def __init__(self, value: int = 0) -> None:
        if not isinstance(value, int) or not (0 <= value < 2**64):
            raise ValueError("Value must be an unsigned 64-bit integer")
        self.value = value


class String:
    """A simplified version of the String class for testing purposes, mimicking basic
    string operations."""

    def __init__(self, value: str = "") -> None:
        self.value = value

    def __add__(self, other: "String | str") -> "String":
        """Concatenates this String with another String or a Python str."""
        new_value = self.value + (other.value if isinstance(other, String) else other)
        return String(new_value)

    def __radd__(self, other: str) -> "String":
        """Enables right-side addition with a Python str."""
        return String(other + self.value)

    def __iadd__(self, other: "String | str") -> Self:
        """In-place concatenation with another String or a Python str."""
        self.value += other.value if isinstance(other, String) else other
        return self

    def __repr__(self) -> str:
        """Returns a string representation of the String."""
        return self.value

    def __eq__(self, other: "String | str") -> bool:
        """Checks equality with another String or a Python str."""
        return self.value == (other.value if isinstance(other, String) else other)

    def __ne__(self, other: "String | str") -> bool:
        """Checks inequality with another String or a Python str."""
        return not self.__eq__(other)

    def __bool__(self) -> bool:
        """Returns True if the string is non-empty."""
        return bool(self.value)

    def __contains__(self, other: "String | str") -> bool:
        """Checks if the string contains another String or a Python str."""
        substring = other.value if isinstance(other, String) else other
        return substring in self.value

    def startswith(self, prefix: "String | str") -> bool:
        """Checks if the string starts with the specified prefix."""
        prefix_str = prefix.value if isinstance(prefix, String) else prefix
        return self.value.startswith(prefix_str)

    def endswith(self, suffix: "String | str") -> bool:
        """Checks if the string ends with the specified suffix."""
        suffix_str = suffix.value if isinstance(suffix, String) else suffix
        return self.value.endswith(suffix_str)

    def join(self, others: tuple["String", ...]) -> "String":
        """Joins a tuple of String objects into a single String with this String as the separator."""
        joined_string = self.value.join(o.value for o in others)
        return String(joined_string)
