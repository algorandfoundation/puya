from algopy import String
from algopy_testing import algopy_testing_context
from contract import Greeter


class TestGreeter:
    def test_init_sets_default_greeting(self) -> None:
        with algopy_testing_context():
            contract = Greeter()

            assert contract.greeting == "Hello"

    def test_hello_returns_greeting_with_name(self) -> None:
        with algopy_testing_context():
            contract = Greeter()

            result = contract.hello(String("Alice"))
            assert result == String("Hello, Alice!")

    def test_set_greeting_changes_prefix(self) -> None:
        with algopy_testing_context():
            contract = Greeter()

            contract.set_greeting(String("Howdy"))
            result = contract.hello(String("Bob"))
            assert result == String("Howdy, Bob!")
