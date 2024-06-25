import typing
from collections.abc import Generator

import pytest
from algopy_testing import arc4
from algopy_testing.context import AlgopyTestContext, algopy_testing_context
from algopy_testing.itxn import ApplicationCallInnerTransaction
from algopy_testing.models.contract import ARC4Contract
from pytest_mock import MockerFixture


class Logger(ARC4Contract):
    @arc4.abimethod
    def echo(self, value: arc4.String) -> arc4.String:
        return "echo: " + value


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


def test_mocking_required_for_abi_call(context: AlgopyTestContext) -> None:
    dummy_app = context.any_application()

    with pytest.raises(NotImplementedError, match="abi_call is not implemented"):
        arc4.abi_call("echo(string)string", "untyped + ignore", app_id=dummy_app)

    with pytest.raises(NotImplementedError, match="abi_call is not implemented"):
        arc4.abi_call[arc4.String]("echo", "test3", app_id=dummy_app)

    with pytest.raises(NotImplementedError, match="abi_call is not implemented"):
        arc4.abi_call(Logger.echo, arc4.String("test1"), app_id=dummy_app)


def test_abi_call_can_be_mocked(context: AlgopyTestContext, mocker: MockerFixture) -> None:
    dummy_app = context.any_application()

    def run_mocked_echo(
        *args: typing.Any, **_kwargs: typing.Any
    ) -> tuple[arc4.String, ApplicationCallInnerTransaction]:
        value = args[-1]
        return (
            arc4.String(f"echo: {value.native if isinstance(value, arc4.String) else value}"),
            ApplicationCallInnerTransaction(),
        )

    mocker.patch("algopy_testing.arc4.abi_call.__class__.__call__", run_mocked_echo)
    mocker.patch(
        "algopy_testing.arc4.abi_call.__class__.__getitem__", return_value=run_mocked_echo
    )

    result = arc4.abi_call(Logger.echo, arc4.String("test1"), app_id=dummy_app)
    assert result[0].native == "echo: test1"

    result = arc4.abi_call[arc4.String]("echo(string)string", "untyped + ignore", app_id=dummy_app)
    assert result[0].native == "echo: untyped + ignore"

    result = arc4.abi_call[arc4.String]("echo", "test3", app_id=dummy_app)
    assert result[0].native == "echo: test3"
