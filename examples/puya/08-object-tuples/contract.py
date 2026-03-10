"""Example 08: Object Tuples

This example demonstrates Structs as method params, return values, and state.

Features:
- Struct definitions for typed object shapes (Point, UserProfile)
- Structs as method params and return values
- Structs in GlobalState
- Returning Structs from readonly methods
- _replace() for immutable updates (like spread operator)
- copy() for cloning

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import GlobalState, String, Struct, UInt64, arc4


class Point(Struct, frozen=True):
    x: UInt64
    y: UInt64


class UserProfile(Struct, frozen=True):
    name: String
    age: UInt64
    score: UInt64


# example: OBJECT_TUPLES
class ObjectTuples(arc4.ARC4Contract):
    """Contract demonstrating Structs as object tuples: type definitions,
    params/returns, GlobalState, _replace, and copy."""

    def __init__(self) -> None:
        self.saved_point = GlobalState(Point(x=UInt64(0), y=UInt64(0)))
        self.profile = GlobalState(
            UserProfile(name=String("anon"), age=UInt64(0), score=UInt64(0))
        )

    # --- Struct as params and returns ---

    @arc4.abimethod
    def add_points(self, a: Point, b: Point) -> Point:
        """Accepts two Points and returns their sum.

        Args:
            a: first point
            b: second point

        Returns:
            the component-wise sum of a and b
        """
        return Point(x=a.x + b.x, y=a.y + b.y)

    # --- GlobalState with Struct ---

    @arc4.abimethod
    def set_point(self, x: UInt64, y: UInt64) -> None:
        """Store a Point in GlobalState.

        Args:
            x: x coordinate
            y: y coordinate
        """
        self.saved_point.value = Point(x=x, y=y)

    @arc4.abimethod(readonly=True)
    def get_point(self) -> Point:
        """Return Point from state without mutating.

        Returns:
            the saved point from GlobalState
        """
        return self.saved_point.value

    # --- _replace() for immutable updates ---

    @arc4.abimethod
    def translate_point(self, dx: UInt64, dy: UInt64) -> Point:
        """_replace() for immutable updates — translates saved point by dx, dy.

        Args:
            dx: x offset to add
            dy: y offset to add

        Returns:
            the updated point
        """
        p = self.saved_point.value
        updated = p._replace(x=p.x + dx, y=p.y + dy)
        self.saved_point.value = updated
        return updated

    # --- copy() for cloning ---

    @arc4.abimethod
    def copy_and_scale(self, factor: UInt64) -> Point:
        """copy() for deep copies — clones saved point and scales by factor.

        Args:
            factor: scale multiplier

        Returns:
            the scaled copy
        """
        cloned = self.saved_point.value.copy()
        scaled = cloned._replace(x=cloned.x * factor, y=cloned.y * factor)
        self.saved_point.value = scaled
        return scaled

    # --- Struct with String field ---

    @arc4.abimethod
    def set_profile(self, name: String, age: UInt64, score: UInt64) -> None:
        """Store a UserProfile in GlobalState.

        Args:
            name: user name
            age: user age
            score: user score
        """
        self.profile.value = UserProfile(name=name, age=age, score=score)

    @arc4.abimethod(readonly=True)
    def get_profile(self) -> UserProfile:
        """Return UserProfile from state without mutating.

        Returns:
            the saved profile from GlobalState
        """
        return self.profile.value

    @arc4.abimethod
    def update_score(self, new_score: UInt64) -> UserProfile:
        """_replace() preserves unchanged fields — updates only score.

        Args:
            new_score: new score value

        Returns:
            the updated profile with name and age preserved
        """
        p = self.profile.value
        updated = p._replace(score=new_score)
        self.profile.value = updated
        return updated


# example: OBJECT_TUPLES
