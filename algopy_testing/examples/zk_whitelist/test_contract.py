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


@pytest.mark.usefixtures("context")
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

    # Act
    result = contract.add_address_to_whitelist(address, proof)

    # Assert
    assert result == algopy.arc4.String("")
    assert contract.whitelist[context.default_creator]


# @pytest.mark.usefixtures("context")
# def test_add_address_to_whitelist_invalid_proof(context: AlgopyTestContext) -> None:
#     # Arrange
#     contract = ZkWhitelistContract()
#     address = context.default_creator.bytes
#     proof = algopy.DynamicArray([Bytes32.from_bytes(b"\x00" * 32)])

#     # Mock the verify_proof subroutine to always return False
#     contract.verify_proof = lambda app_id, proof, public_inputs: algopy.Bool(False)

#     # Act
#     result = contract.add_address_to_whitelist(address, proof)

#     # Assert
#     assert result == algopy.String("Proof verification failed")
#     assert contract.whitelist.get(context.default_creator, algopy.Bool(False)) == algopy.Bool(
#         False
#     )


# @pytest.mark.usefixtures("context")
# def test_is_on_whitelist(context: AlgopyTestContext) -> None:
#     # Arrange
#     contract = ZkWhitelistContract()
#     address = context.default_creator
#     contract.whitelist[address] = algopy.Bool(True)

#     # Act
#     result = contract.is_on_whitelist(address)

#     # Assert
#     assert result == algopy.Bool(True)


# @pytest.mark.usefixtures("context")
# def test_is_not_on_whitelist(context: AlgopyTestContext) -> None:
#     # Arrange
#     contract = ZkWhitelistContract()
#     address = context.default_creator

#     # Act
#     result = contract.is_on_whitelist(address)

#     # Assert
#     assert result == algopy.Bool(False)
