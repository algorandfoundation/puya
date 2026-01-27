import random
from collections.abc import Mapping, Sequence
from pathlib import Path

import algokit_utils as au
import attrs
from algokit_abi import arc56
from algokit_algod_client import models as algod

from tests.utils.compile import compile_arc56

_ALWAYS_APPROVE = "#pragma version 10\nint 1"

Contract = Path | tuple[Path, str] | au.Arc56Contract


@attrs.frozen
class CreateResult:
    client: au.AppClient
    txn: au.Transaction
    confirmation: algod.PendingTransactionResponse
    abi_return: object

    @property
    def logs(self) -> list[bytes]:
        return self.confirmation.logs or []


class _AutoSentinel(str):
    __slots__ = ()


_AUTO = _AutoSentinel()


@attrs.frozen
class Deployer:
    localnet: au.AlgorandClient
    account: au.AddressWithSigners
    optimization_level: int = 1
    debug_level: int = 2

    def create(
        self,
        contract: Contract,
        *,
        method: str = _AUTO,
        args: Sequence[object] | Mapping[str, object] = (),
        on_complete: au.CreateOnComplete = au.OnApplicationComplete.NoOp,
    ) -> CreateResult:
        factory = self._get_factory(contract)

        txn: au.SendSingleTransactionResult
        abi_return = None
        create_method = _find_create_method(factory.app_spec, method)
        if method is _AUTO and not create_method and not args:
            client, txn = factory.send.bare.create(
                au.AppFactoryCreateParams(
                    on_complete=on_complete,
                    note=random.randbytes(8),
                )
            )
        elif create_method:
            if isinstance(args, dict):
                create_args = [
                    args.pop(arg.name or "$MISSING_ARG_NAME") for arg in create_method.args
                ]
            else:
                create_args = list(args)
            client, abi_txn = factory.send.create(
                au.AppFactoryCreateMethodCallParams(
                    method=create_method.signature,
                    args=create_args,
                    on_complete=on_complete,
                    note=random.randbytes(8),
                )
            )
            txn = abi_txn
            abi_return = abi_txn.abi_return
        else:
            raise ValueError("could not find a suitable create method")

        return CreateResult(
            client=client,
            txn=txn.transaction,
            confirmation=txn.confirmation,
            abi_return=abi_return,
        )

    def create_bare(
        self,
        contract: Contract,
        *,
        args: Sequence[bytes | int] | None = None,
        on_complete: au.CreateOnComplete = au.OnApplicationComplete.NoOp,
        static_fee: au.AlgoAmount | None = None,
        account_references: list[str] | None = None,
    ) -> CreateResult:
        factory = self._get_factory(contract)

        client, txn = factory.send.bare.create(
            au.AppFactoryCreateParams(
                args=encode_bare_args(args),
                on_complete=on_complete,
                static_fee=static_fee,
                account_references=account_references,
                note=random.randbytes(8),
            )
        )

        return CreateResult(
            client=client,
            txn=txn.transaction,
            confirmation=txn.confirmation,
            abi_return=None,
        )

    def create_op_up(self, note: bytes | None = None) -> au.Transaction:
        return self.localnet.create_transaction.app_create(
            au.AppCreateParams(
                approval_program=_ALWAYS_APPROVE,
                clear_state_program=_ALWAYS_APPROVE,
                on_complete=au.OnApplicationComplete.DeleteApplication,
                sender=self.account.addr,
                note=note,
            )
        )

    def create_with_op_up(
        self,
        contract: Contract,
        *,
        num_op_ups: int,
        on_complete: au.CreateOnComplete = au.OnApplicationComplete.NoOp,
        args: Sequence[bytes | int] | None = None,
    ) -> CreateResult:
        factory = self._get_factory(contract)
        group = self.localnet.new_group()
        group.add_app_create(
            factory.params.bare.create(
                au.AppFactoryCreateParams(
                    on_complete=on_complete,
                    args=encode_bare_args(args),
                    note=random.randbytes(8),
                )
            )
        )
        for idx in range(num_op_ups):
            group.add_transaction(self.create_op_up(idx.to_bytes()))

        result = group.send()
        confirmation = result.confirmations[0]
        app_id = confirmation.app_id
        assert app_id is not None
        return CreateResult(
            client=factory.get_app_client_by_id(app_id),
            txn=result.transactions[0],
            confirmation=confirmation,
            abi_return=None,
        )

    def _get_factory(self, contract: Contract) -> au.AppFactory:
        if isinstance(contract, au.Arc56Contract):
            app_spec = contract
        elif isinstance(contract, Path):
            app_spec = compile_arc56(
                contract,
                optimization_level=self.optimization_level,
                debug_level=self.debug_level,
            )
        else:
            app_spec = compile_arc56(
                contract[0],
                contract_name=contract[1],
                optimization_level=self.optimization_level,
                debug_level=self.debug_level,
            )
        return au.AppFactory(
            au.AppFactoryParams(
                algorand=self.localnet,
                app_spec=app_spec,
                default_sender=self.account.addr,
            )
        )


def encode_bare_args(args: Sequence[bytes | int] | None) -> list[bytes]:
    return [a if isinstance(a, bytes) else a.to_bytes(8, "big") for a in args or []]


def _find_create_method(app_spec: au.Arc56Contract, method: str) -> arc56.Method | None:
    create_methods = [m for m in app_spec.methods if m.actions.create]
    if method is _AUTO:
        try:
            (create_method,) = create_methods
        except ValueError:
            return None
        else:
            return create_method
    else:
        return app_spec.get_abi_method(method)
