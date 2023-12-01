import argparse
import contextlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk.kmd import KMDClient
from algosdk.transaction import ApplicationCallTxn, OnComplete, create_dryrun
from algosdk.v2client.algod import AlgodClient

DEFAULT_ALGOD_ADDRESS = "http://localhost:4001"
DEFAULT_KMD_ADDRESS = "http://localhost:4002"
DEFAULT_TOKEN = "a" * 64
DEFAULT_KMD_WALLET_NAME = "unencrypted-default-wallet"
DEFAULT_KMD_WALLET_PASSWORD = ""


def main(approval_path: Path, clear_path: Path) -> None:
    response = dryrun_create(approval_path.read_bytes(), clear_path.read_bytes())
    print(json.dumps(response, indent=4))


def dryrun_create(
    approval_binary: bytes,
    clear_binary: bytes,
) -> dict[str, Any]:
    algod = AlgodClient(algod_token=DEFAULT_TOKEN, algod_address=DEFAULT_ALGOD_ADDRESS)
    account, *_ = get_accounts()
    atc = AtomicTransactionComposer()
    atc.add_transaction(
        TransactionWithSigner(
            txn=ApplicationCallTxn(  # type: ignore[no-untyped-call]
                sender=account.address,
                sp=algod.suggested_params(),
                index=0,
                on_complete=OnComplete.NoOpOC,
                approval_program=approval_binary,
                clear_program=clear_binary,
                # app_args=app_args,
            ),
            signer=account.signer,
        )
    )

    atc.execute(algod, 4)
    signed = atc.gather_signatures()
    dryrun_request = create_dryrun(algod, signed)

    return algod.dryrun(dryrun_request.dictify())  # type: ignore[no-untyped-call]


@dataclass(kw_only=True)
class LocalAccount:
    """LocalAccount is a simple dataclass to hold a localnet account details"""

    #: The address of a localnet account
    address: str
    #: The base64 encoded private key of the account
    private_key: str

    #: An AccountTransactionSigner that can be used as a TransactionSigner
    @cached_property
    def signer(self) -> AccountTransactionSigner:
        return AccountTransactionSigner(self.private_key)


def get_accounts(
    kmd_address: str = DEFAULT_KMD_ADDRESS,
    kmd_token: str = DEFAULT_TOKEN,
    wallet_name: str = DEFAULT_KMD_WALLET_NAME,
    wallet_password: str = DEFAULT_KMD_WALLET_PASSWORD,
) -> list[LocalAccount]:
    """gets all the accounts in the localnet kmd, defaults
    to the `unencrypted-default-wallet` created on private networks automatically"""
    kmd = KMDClient(kmd_token, kmd_address)  # type: ignore[no-untyped-call]
    with wallet_handle_by_name(kmd, wallet_name, wallet_password) as wallet_handle:
        return [
            LocalAccount(
                address=address,
                private_key=kmd.export_key(
                    wallet_handle,
                    wallet_password,
                    address,
                ),  # type: ignore[no-untyped-call]
            )
            for address in kmd.list_keys(wallet_handle)  # type: ignore[no-untyped-call]
        ]


@contextlib.contextmanager
def wallet_handle_by_name(kmd: KMDClient, wallet_name: str, wallet_password: str) -> Iterator[str]:
    wallets = kmd.list_wallets()  # type: ignore[no-untyped-call]

    try:
        wallet_id = next(iter(w["id"] for w in wallets if w["name"] == wallet_name))
    except StopIteration:
        raise Exception(f"Wallet not found: {wallet_name}") from None

    wallet_handle = kmd.init_wallet_handle(
        wallet_id,
        wallet_password,
    )  # type: ignore[no-untyped-call]
    try:
        yield wallet_handle
    finally:
        kmd.release_wallet_handle(wallet_handle)  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="dry_run_create")
    parser.add_argument("approval_file", type=Path, metavar="FILE")
    parser.add_argument("clear_file", type=Path, metavar="FILE")
    args = parser.parse_args()
    main(args.approval_file, args.clear_file)
