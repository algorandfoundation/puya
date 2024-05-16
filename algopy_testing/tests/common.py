import typing
from random import randbytes

from algokit_utils import ApplicationClient


class AVMInvoker(typing.Protocol):
    """Protocol used in global test fixtures to simplify invocation of AVM methods via an Algokit
    typed client."""

    def __call__(self, method: str, **kwargs: typing.Any) -> object: ...


def create_avm_invoker(client: ApplicationClient) -> AVMInvoker:
    def invoke(method: str, **kwargs: typing.Any) -> object:
        result = client.call(
            method,
            transaction_parameters={
                # random note avoids duplicate txn if tests are running concurrently
                "note": randbytes(8),  # noqa: S311
                "suggested_params": kwargs.pop("suggested_params", None),
            },
            **kwargs,
        ).return_value
        if isinstance(result, list) and all(isinstance(i, int) for i in result):
            result = bytes(result)
        return result

    return invoke
