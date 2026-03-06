from algopy import arc4
from algopy_testing import algopy_testing_context
from contract import Greeter


class TestGreeter:
    def test_create_sets_default_greeting(self) -> None:
        with algopy_testing_context():
            contract = Greeter()
            contract.create()
            assert contract.greeting == "Hello"

    def test_hello_returns_greeting_with_name(self) -> None:
        with algopy_testing_context():
            contract = Greeter()
            contract.create()
            result = contract.hello(arc4.String("Alice"))
            assert result == arc4.String("Hello, Alice!")

    def test_set_greeting_changes_prefix(self) -> None:
        with algopy_testing_context():
            contract = Greeter()
            contract.create()
            contract.set_greeting(arc4.String("Howdy"))
            result = contract.hello(arc4.String("Bob"))
            assert result == arc4.String("Howdy, Bob!")
