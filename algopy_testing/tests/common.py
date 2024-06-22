import secrets
import typing
from pathlib import Path

from algokit_utils import ApplicationClient, get_localnet_default_account
from algosdk.v2client.algod import AlgodClient


class AVMInvoker:
    """Protocol used in global test fixtures to simplify invocation of AVM methods via an Algokit
    typed client."""

    def __init__(self, client: ApplicationClient):
        self.client = client

    def __call__(self, method: str, **kwargs: typing.Any) -> object:
        response = self.client.call(
            method,
            transaction_parameters={
                # random note avoids duplicate txn if tests are running concurrently
                "note": _random_note(),
                "suggested_params": kwargs.pop("suggested_params", None),
            },
            **kwargs,
        )
        if response.decode_error:
            raise ValueError(response.decode_error)
        result = response.return_value
        if result is None:
            return response.tx_info.get("logs", None)
        if isinstance(result, list) and all(
            isinstance(i, int) and i >= 0 and i <= 255 for i in result
        ):
            return bytes(result)
        return result


def _random_note() -> bytes:
    return secrets.token_bytes(8)


def create_avm_invoker(app_spec: Path, algod_client: AlgodClient) -> AVMInvoker:
    client = ApplicationClient(
        algod_client,
        app_spec,
        signer=get_localnet_default_account(algod_client),
    )

    client.create(
        transaction_parameters={
            # random note avoids duplicate txn if tests are running concurrently
            "note": _random_note(),
        }
    )

    return AVMInvoker(client)
