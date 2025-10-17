import typing

class _Validatable(typing.Protocol):
    def validate(self) -> None:
        """Performs validation to ensure the value is well-formed, errors if it is not"""
