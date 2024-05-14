import typing


class AVMInvoker(typing.Protocol):
    """Protocol used in global test fixtures to simplify invocation of AVM methods via an Algokit
    typed client."""

    def __call__(self, method: str, **kwargs: typing.Any) -> object: ...
