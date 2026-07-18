import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils.compile import compile_arc56_from_closure
from tests.utils.deployer import Deployer

_ARC4_CLIENT = EXAMPLES_DIR / "devportal" / "arc4_client"

# call_hello / call_add each issue one inner ApplicationCall with fee=0,
# so the outer call must cover both transaction fees.
_INNER_FEE = au.AlgoAmount.from_micro_algo(2000)


def _target_contract() -> None:
    """An external ARC-4 contract matching the HelloWorldClient protocol:
    `hello(string)string` and `add(uint64,uint64)uint64`."""
    from algopy import String, UInt64, arc4

    class HelloWorld(arc4.ARC4Contract):
        @arc4.abimethod
        def hello(self, name: String) -> String:
            return "Hello, " + name

        @arc4.abimethod
        def add(self, a: UInt64, b: UInt64) -> UInt64:
            return a + b


def test_call_hello_routes_to_target(deployer: Deployer) -> None:
    target = deployer.create(compile_arc56_from_closure(_target_contract)).client
    consumer = deployer.create((_ARC4_CLIENT, "ClientConsumer")).client

    result = consumer.send.call(
        au.AppClientMethodCallParams(
            method="call_hello",
            args=[target.app_id, "Algorand"],
            static_fee=_INNER_FEE,
        )
    )
    assert result.abi_return == "Hello, Algorand"


def test_call_add_routes_to_target_and_checks_logs(deployer: Deployer) -> None:
    target = deployer.create(compile_arc56_from_closure(_target_contract)).client
    consumer = deployer.create((_ARC4_CLIENT, "ClientConsumer")).client

    result = consumer.send.call(
        au.AppClientMethodCallParams(
            method="call_add",
            args=[target.app_id, 7, 35],
            static_fee=_INNER_FEE,
        )
    )
    # add(7, 35) == 42; the contract also asserts the inner txn emitted
    # exactly one log (the ABI return log).
    assert result.abi_return == 42


def test_call_add_with_zero_operands(deployer: Deployer) -> None:
    target = deployer.create(compile_arc56_from_closure(_target_contract)).client
    consumer = deployer.create((_ARC4_CLIENT, "ClientConsumer")).client

    result = consumer.send.call(
        au.AppClientMethodCallParams(
            method="call_add",
            args=[target.app_id, 0, 0],
            static_fee=_INNER_FEE,
        )
    )
    assert result.abi_return == 0


def _chatty_target_contract() -> None:
    """A target whose `add` emits an extra log besides the ABI return log,
    violating ClientConsumer's `num_logs == 1` expectation."""
    from algopy import String, UInt64, arc4, log

    class HelloWorld(arc4.ARC4Contract):
        @arc4.abimethod
        def hello(self, name: String) -> String:
            return "Hello, " + name

        @arc4.abimethod
        def add(self, a: UInt64, b: UInt64) -> UInt64:
            log("extra log entry")
            return a + b


def test_call_add_rejects_target_with_extra_logs(deployer: Deployer) -> None:
    target = deployer.create(compile_arc56_from_closure(_chatty_target_contract)).client
    consumer = deployer.create((_ARC4_CLIENT, "ClientConsumer")).client

    # the target emits 2 logs, so the consumer's num_logs assertion fails
    with pytest.raises(au.LogicError, match="only the return log was emitted"):
        consumer.send.call(
            au.AppClientMethodCallParams(
                method="call_add",
                args=[target.app_id, 1, 2],
                static_fee=_INNER_FEE,
            )
        )


def test_call_hello_against_missing_app_fails(deployer: Deployer) -> None:
    consumer = deployer.create((_ARC4_CLIENT, "ClientConsumer")).client

    # An app id that does not exist on chain cannot be invoked.
    with pytest.raises(au.LogicError):
        consumer.send.call(
            au.AppClientMethodCallParams(
                method="call_hello",
                args=[99_999_999, "nobody"],
                static_fee=_INNER_FEE,
            )
        )
