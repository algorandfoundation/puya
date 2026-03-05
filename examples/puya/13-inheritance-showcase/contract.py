"""Example 13: Inheritance Showcase

This example demonstrates single and multi-level inheritance with abstract classes.

Features:
- Single inheritance (extending a base class)
- Multi-level inheritance (three levels deep)
- Abstract classes (abc.ABC prevents direct instantiation)
- Method overrides (replacing parent behaviour in subclasses)
- Super calls (super().method() in constructors and overrides)
- Constructor patterns (state initialization via __init__ and create)
- Final methods (typing.final prevents override in subclasses)

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

import abc
import typing

from algopy import ARC4Contract, GlobalState, String, UInt64, arc4, log


class Animal(ARC4Contract, abc.ABC):
    """Abstract base class — every animal must implement speak().

    Declares shared state (name, legs) and common methods.
    Cannot be deployed directly due to abc.ABC.
    """

    def __init__(self) -> None:
        self.name = GlobalState(String)
        self.legs = GlobalState(UInt64)
        super().__init__()

    @arc4.abimethod(create="require")
    def create(self, name: arc4.String, legs: arc4.UInt64) -> None:
        """Set the initial name and legs.

        Args:
            name: the animal's name
            legs: the number of legs
        """
        self.name.value = name.native
        self.legs.value = legs.as_uint64()

    @abc.abstractmethod
    @arc4.abimethod
    def speak(self) -> arc4.String:
        """Return the animal's sound — must be implemented by subclasses.

        Returns:
            the animal's sound as a string
        """
        ...

    @arc4.abimethod(readonly=True)
    def describe(self) -> arc4.String:
        """Return a description of the animal.

        Returns:
            a string describing the animal's name and legs
        """
        return arc4.String(self.name.value + " has " + self._legs_str() + " legs")

    @arc4.abimethod(readonly=True)
    def get_name(self) -> arc4.String:
        """Return the animal's name.

        Returns:
            the current name
        """
        return arc4.String(self.name.value)

    @arc4.abimethod(readonly=True)
    def get_legs(self) -> UInt64:
        """Return the number of legs.

        Returns:
            the current leg count
        """
        return self.legs.value

    @typing.final
    @arc4.abimethod(readonly=True)
    def species_type(self) -> arc4.String:
        """Final method — cannot be overridden by subclasses.

        Returns:
            the string "Animal"
        """
        return arc4.String("Animal")

    def _legs_str(self) -> String:
        legs = self.legs.value
        if legs == UInt64(0):
            return String("0")
        if legs == UInt64(2):
            return String("2")
        if legs == UInt64(4):
            return String("4")
        return String("?")


class Dog(Animal):
    """Single-level inheritance: Dog extends Animal.

    Overrides speak() and describe(), adds trick state and set_trick/get_trick methods.
    Constructor chains to Animal via super().
    """

    def __init__(self) -> None:
        self.trick = GlobalState(String)
        super().__init__()

    @typing.override
    @arc4.abimethod(create="require")
    def create(self, name: arc4.String, legs: arc4.UInt64) -> None:
        """Override create — super call chains to Animal.create, then sets default trick.

        Args:
            name: the dog's name
            legs: the number of legs
        """
        super().create(name, legs)
        self.trick.value = String("sit")

    @typing.override
    @arc4.abimethod
    def speak(self) -> arc4.String:
        """Override Animal.speak with dog-specific sound.

        Returns:
            "{name} says Woof!"
        """
        return arc4.String(self.name.value + " says Woof!")

    @arc4.abimethod
    def set_trick(self, trick: arc4.String) -> None:
        """Set the dog's trick.

        Args:
            trick: the new trick to store
        """
        self.trick.value = trick.native

    @arc4.abimethod(readonly=True)
    def get_trick(self) -> arc4.String:
        """Return the dog's current trick.

        Returns:
            the current trick
        """
        return arc4.String(self.trick.value)

    @typing.override
    @arc4.abimethod(readonly=True)
    def describe(self) -> arc4.String:
        """Override Animal.describe to include the trick.

        Returns:
            a string describing name, legs, and trick
        """
        base = self.name.value + " has " + self._legs_str() + " legs"
        return arc4.String(base + " and knows " + self.trick.value)


class ShowDog(Dog):
    """Multi-level inheritance: ShowDog -> Dog -> Animal (three levels deep).

    Overrides speak() and describe(), adds awards state and win_award/get_awards methods.
    Constructor chains through Dog to Animal via super().
    """

    def __init__(self) -> None:
        self.awards = GlobalState(UInt64)
        super().__init__()

    @typing.override
    @arc4.abimethod(create="require")
    def create(self, name: arc4.String, legs: arc4.UInt64) -> None:
        """Override create — super call chains through Dog to Animal, then initialises awards.

        Args:
            name: the show dog's name
            legs: the number of legs
        """
        super().create(name, legs)
        self.awards.value = UInt64(0)

    @typing.override
    @arc4.abimethod
    def speak(self) -> arc4.String:
        """Override Dog.speak with show-champion sound.

        Returns:
            "{name} says Woof! (Show champion)"
        """
        return arc4.String(self.name.value + " says Woof! (Show champion)")

    @typing.override
    @arc4.abimethod(readonly=True)
    def describe(self) -> arc4.String:
        """Override Dog.describe to include trick and awards.

        Returns:
            a string describing name, legs, trick, and awards
        """
        base = self.name.value + " has " + self._legs_str() + " legs"
        return arc4.String(base + ", knows " + self.trick.value + ", awards: " + self._awards_str())

    @arc4.abimethod
    def win_award(self) -> UInt64:
        """Increment and return the awards count.

        Returns:
            the new awards count after incrementing
        """
        self.awards.value += 1
        log("Award won!")
        return self.awards.value

    @arc4.abimethod(readonly=True)
    def get_awards(self) -> UInt64:
        """Return the current awards count.

        Returns:
            the number of awards won
        """
        return self.awards.value

    def _awards_str(self) -> String:
        a = self.awards.value
        if a == UInt64(0):
            return String("0")
        if a == UInt64(1):
            return String("1")
        if a == UInt64(2):
            return String("2")
        if a == UInt64(3):
            return String("3")
        return String("many")
