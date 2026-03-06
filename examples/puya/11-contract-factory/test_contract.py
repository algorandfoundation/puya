import pytest
from algopy import String
from algopy_testing import algopy_testing_context
from contract import ChildContract, TemplatedChild


class TestChildContract:
    def test_create_stores_greeting(self) -> None:
        with algopy_testing_context():
            contract = ChildContract()
            contract.create(String("Hello"))
            assert contract.greeting == String("Hello")

    def test_greet_returns_combined_string(self) -> None:
        with algopy_testing_context():
            contract = ChildContract()
            contract.create(String("Hello"))
            result = contract.greet(String("World"))
            assert result == String("Hello World")

    def test_greet_with_different_greeting(self) -> None:
        with algopy_testing_context():
            contract = ChildContract()
            contract.create(String("Howdy"))
            result = contract.greet(String("Partner"))
            assert result == String("Howdy Partner")

    def test_delete(self) -> None:
        with algopy_testing_context():
            contract = ChildContract()
            contract.create(String("Hello"))
            contract.delete()


class TestTemplatedChild:
    def test_create_and_greet(self) -> None:
        with algopy_testing_context() as ctx:
            ctx.set_template_var("GREETING", String("Howdy"))
            contract = TemplatedChild()
            contract.create()
            result = contract.greet(String("Friend"))
            assert result == String("Howdy Friend")


class TestContractFactory:
    @pytest.mark.skip(
        reason="compile_contract/arc4_create/abi_call not supported in algorand-python-testing"
    )
    def test_deploy_child(self) -> None:
        pass

    @pytest.mark.skip(
        reason="compile_contract/arc4_create not supported in algorand-python-testing"
    )
    def test_deploy_templated(self) -> None:
        pass

    @pytest.mark.skip(reason="arc4.abi_call not supported in algorand-python-testing")
    def test_call_child_greet(self) -> None:
        pass

    @pytest.mark.skip(
        reason="compile_contract/arc4_create/abi_call not supported in algorand-python-testing"
    )
    def test_deploy_and_greet(self) -> None:
        pass

    @pytest.mark.skip(reason="arc4.abi_call not supported in algorand-python-testing")
    def test_delete_child(self) -> None:
        pass
