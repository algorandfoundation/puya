class UInt64Error(Exception):
    """Base class for all UInt64-related errors."""

    @staticmethod
    def default_message(message: str | None, default: str) -> str:
        """Return the message if not None, otherwise return the default message."""
        return message if message is not None else default

class UInt64InvalidValueError(UInt64Error):
    """Exception for invalid operations on UInt64."""

    def __init__(self, message: str | None = None):
        super().__init__(self.default_message(message, "Invalid value, must be an `int` or `UInt64` instance."))
class UInt64UnderflowError(ValueError, UInt64Error):
    """Raised when a negative value is provided for a UInt64 instance."""

    def __init__(self, value: int, message: str | None = None):
        formatted_message = self.default_message(message, f"{value} can't be negative")
        super().__init__(formatted_message)
        self.value = value


class UInt64OverflowError(OverflowError, UInt64Error):
    """Raised when an operation on UInt64 instances results in an overflow."""

    def __init__(self, value: int, message: str | None = None):
        formatted_message = self.default_message(message, f"{value} is too big to fit in size 64")
        super().__init__(formatted_message)
        self.value = value


class UInt64BitShiftOverflowError(UInt64OverflowError):
    """Raised when a bit shift operation on a UInt64 instance results in an overflow."""

    def __init__(self, value: int, shift_amount: int, message: str | None = None):
        formatted_message = self.default_message(message, f"{value} << {shift_amount} is too big to fit in size 64")
        super().__init__(value, formatted_message)


class UInt64ZeroDivisionError(ZeroDivisionError, UInt64Error):
    """Raised when attempting to divide a UInt64 instance by zero."""

    def __init__(self, value: int, message: str | None = None):
        formatted_message = self.default_message(message, f"UInt64 division by zero: {value}")
        super().__init__(formatted_message)
        self.value = value
