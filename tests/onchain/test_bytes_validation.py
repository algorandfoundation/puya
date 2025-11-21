import algokit_utils as au
import pytest

from tests.utils.compile import compile_arc56_from_closure
from tests.utils.deployer import Deployer


def test_account_from_bytes_validation(deployer: Deployer, optimization_level: int) -> None:
    def contract() -> None:
        from algopy import Account, BaseContract, Txn

        class Baddie(BaseContract):
            def approval_program(self) -> bool:
                b = Txn.sender.bytes + b"!"
                x = Account(b)
                assert x.bytes.length > 0, "shouldn't get here"
                return True

            def clear_state_program(self) -> bool:
                return True

    app_spec = compile_arc56_from_closure(contract, optimization_level=optimization_level)
    with pytest.raises(au.LogicError, match="// Address length is 32 bytes\t\t<-- Error"):
        deployer.create_bare(app_spec)


def test_arc4_address_from_bytes_validation(deployer: Deployer, optimization_level: int) -> None:
    def contract() -> None:
        from algopy import BaseContract, Txn, arc4

        class Baddie(BaseContract):
            def approval_program(self) -> bool:
                b = Txn.sender.bytes + b"!"
                x = arc4.Address(b)
                assert x.bytes.length > 0, "shouldn't get here"
                return True

            def clear_state_program(self) -> bool:
                return True

    app_spec = compile_arc56_from_closure(contract, optimization_level=optimization_level)
    with pytest.raises(au.LogicError, match="// Address length is 32 bytes\t\t<-- Error"):
        deployer.create_bare(app_spec)
