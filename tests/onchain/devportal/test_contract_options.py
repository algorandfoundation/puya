import random

import algokit_transact as at
import algokit_utils as au

from puya.utils import sha512_256_hash
from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_CONTRACT_OPTIONS = EXAMPLES_DIR / "devportal" / "contract_options"


def test_contract_with_custom_name_hello(deployer: Deployer) -> None:
    # the contract compiles (and deploys) under its overridden name,
    # not the python class name ContractWithCustomName
    client = deployer.create((_CONTRACT_OPTIONS, "OnChainName")).client
    assert client.app_spec.name == "OnChainName"
    result = client.send.call(au.AppClientMethodCallParams(method="hello"))
    assert result.abi_return == "hello"


def test_contract_with_state_reservation_increment(deployer: Deployer) -> None:
    client = deployer.create((_CONTRACT_OPTIONS, "ContractWithStateReservation")).client
    # a random note keeps the two otherwise-identical increment txns unique
    assert (
        client.send.call(
            au.AppClientMethodCallParams(method="increment", note=random.randbytes(8))
        ).abi_return
        == 1
    )
    assert (
        client.send.call(
            au.AppClientMethodCallParams(method="increment", note=random.randbytes(8))
        ).abi_return
        == 2
    )


def test_contract_with_state_reservation_schema(
    deployer: Deployer, localnet: au.AlgorandClient
) -> None:
    client = deployer.create((_CONTRACT_OPTIONS, "ContractWithStateReservation")).client
    # the created app reserves the explicit state_totals, not the two slots
    # that would be auto-computed from the `self.` assignments in __init__
    params = localnet.client.algod.application_by_id(client.app_id).params
    assert params.global_state_schema is not None
    assert params.global_state_schema.num_uints == 16
    assert params.global_state_schema.num_byte_slices == 8
    assert params.local_state_schema is not None
    assert params.local_state_schema.num_uints == 4
    assert params.local_state_schema.num_byte_slices == 0


def test_contract_with_scratch_reservation_echo(deployer: Deployer) -> None:
    client = deployer.create((_CONTRACT_OPTIONS, "ContractWithScratchReservation")).client
    assert client.send.call(au.AppClientMethodCallParams(method="echo", args=[7])).abi_return == 7


def test_caller_pin_reads_reject_version_field(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = deployer.create((_CONTRACT_OPTIONS, "ContractWithAvmVersion")).client

    # an unpinned call reads reject_version == 0
    result = client.send.call(au.AppClientMethodCallParams(method="caller_pin"))
    assert result.abi_return == 0

    # algokit_utils does not expose reject_version on outer app-call params
    # yet, so a pinned call is built at the raw algokit_transact layer
    sp = localnet.get_suggested_params()
    txn = at.Transaction(
        transaction_type=at.TransactionType.AppCall,
        sender=account.addr,
        first_valid=sp.first_valid,
        last_valid=sp.last_valid,
        fee=1000,
        genesis_hash=sp.genesis_hash,
        note=random.randbytes(8),
        application_call=at.AppCallTransactionFields(
            app_id=client.app_id,
            reject_version=3,
            args=[sha512_256_hash(b"caller_pin()uint64")[:4]],
        ),
    )
    sent = localnet.new_group().add_transaction(txn).send()
    # decode the ARC-4 return log: 4-byte return prefix + uint64
    (log,) = sent.confirmations[0].logs or []
    assert log[:4] == b"\x15\x1f\x7c\x75"
    assert int.from_bytes(log[4:], "big") == 3


def test_contract_with_avm_version_bytecode_declares_v12(
    deployer: Deployer, localnet: au.AlgorandClient
) -> None:
    client = deployer.create((_CONTRACT_OPTIONS, "ContractWithAvmVersion")).client
    params = localnet.client.algod.application_by_id(client.app_id).params
    # the first byte of compiled AVM bytecode is the version declaration
    assert params.approval_program[0] == 12
