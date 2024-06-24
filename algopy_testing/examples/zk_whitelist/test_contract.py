import typing
from collections.abc import Generator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from .contract import ZkWhitelistContract


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


def test_add_address_to_whitelist(context: AlgopyTestContext) -> None:
    # Arrange
    contract = ZkWhitelistContract()
    address = algopy.arc4.Address(context.default_creator)
    proof = algopy.arc4.DynamicArray[
        algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]
    ](
        algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]](
            *[algopy.arc4.Byte(0) for _ in range(32)]
        )
    )
    dummy_verifier_app = context.any_application()
    context.set_template_var("VERIFIER_APP_ID", dummy_verifier_app.id)
    context.add_application_logs(
        app_id=dummy_verifier_app.id,
        logs=b"\x80",
        prepend_arc4_prefix=True,
    )

    # Act
    result = contract.add_address_to_whitelist(address, proof)

    # Assert
    assert result == algopy.arc4.String("")
    assert contract.whitelist[context.default_creator]


def test_add_address_to_whitelist_invalid_proof(context: AlgopyTestContext) -> None:
    # Arrange
    contract = ZkWhitelistContract()
    address = algopy.arc4.Address(context.default_creator)
    proof = algopy.arc4.DynamicArray[
        algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]
    ](
        algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]](
            *[algopy.arc4.Byte(0) for _ in range(32)]
        )
    )
    dummy_verifier_app = context.any_application()
    context.set_template_var("VERIFIER_APP_ID", dummy_verifier_app.id)
    context.add_application_logs(
        app_id=dummy_verifier_app.id,
        logs=b"",
        prepend_arc4_prefix=True,
    )

    # Act
    result = contract.add_address_to_whitelist(address, proof)

    # Assert
    assert result == algopy.arc4.String("Proof verification failed")


@pytest.mark.usefixtures("context")
def test_is_on_whitelist(context: AlgopyTestContext) -> None:
    # Arrange
    contract = ZkWhitelistContract()
    dummy_account = context.any_account(
        opted_apps={context.default_application.id: context.default_application}
    )
    contract.whitelist[dummy_account] = True

    # Act
    result = contract.is_on_whitelist(algopy.arc4.Address(dummy_account))

    # Assert
    assert result.native


@pytest.mark.usefixtures("context")
def test_is_not_on_whitelist(context: AlgopyTestContext) -> None:
    # Arrange
    contract = ZkWhitelistContract()
    dummy_account = context.any_account(
        opted_apps={context.default_application.id: context.default_application}
    )
    contract.whitelist[dummy_account] = False

    # Act
    result = contract.is_on_whitelist(algopy.arc4.Address(dummy_account))

    # Assert
    assert not result.native
