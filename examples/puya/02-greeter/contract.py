"""
Example 02: Greeter

This example demonstrates string handling and readonly methods.

Features:
- string params & returns
- readonly decorator
- docstrings on methods
- string concatenation

Prerequisites: LocalNet

Note: Educational only - not audited for production use.
"""

from algopy import ARC4Contract, String, arc4


# example: GREETER
class Greeter(ARC4Contract):
    """Simple greeter contract demonstrating string handling and readonly methods."""

    def __init__(self) -> None:
        """Initialise greeting to 'Hello'."""
        self.greeting = String("Hello")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        """Called once when the app is first deployed."""

    @arc4.abimethod(readonly=True)
    def hello(self, name: arc4.String) -> arc4.String:
        """Greet a person by name.

        Args:
            name: The name of the person to greet.

        Returns:
            A personalised greeting string.
        """
        return arc4.String(self.greeting + ", " + name.native + "!")

    @arc4.abimethod
    def set_greeting(self, greeting: arc4.String) -> None:
        """Update the greeting prefix.

        Args:
            greeting: The new greeting to use.
        """
        self.greeting = greeting.native


# example: GREETER
