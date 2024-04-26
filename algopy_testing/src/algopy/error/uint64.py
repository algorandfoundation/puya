class UInt64UnderflowError(ValueError):
    """Raised when an invalid value is provided for a UInt64 instance."""

    def __init__(self, value):
        super().__init__(self.message)
        self.value = value
        self.message = f"{value} can't be negative"


class UInt64OverflowError(OverflowError):
    """Raised when an operation on UInt64 instances results in an overflow."""

    def __init__(self, value):
        super().__init__(self.message)
        self.value = value
        self.message = f"{value} is too big to fit in size 64"
        

class UInt64BitShiftOverflowError(UInt64OverflowError):
    """Raised when a bit shift operation on a UInt64 instance results in an overflow."""
    def __init__(self, value, shift_amount):
        super().__init__(value=value)
        self.message = f"{value} << {shift_amount} is too big to fit in size 64"
        

class UInt64ZeroDivisionError(ZeroDivisionError):
    """Raised when attempting to divide a UInt64 instance by zero."""

    def __init__(self, value):
        super().__init__(f"UInt64 division by zero: {value}")
        self.value = value
        