import pytest
from algopy import String, UInt64
from algopy_testing import algopy_testing_context
from contract import ObjectTuples, Point


class TestObjectTuples:
    def test_create_sets_default_point(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            p = contract.get_point()
            assert p.x == 0
            assert p.y == 0

    def test_create_sets_default_profile(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            profile = contract.get_profile()
            assert profile.name == String("anon")
            assert profile.age == 0
            assert profile.score == 0

    def test_add_points_returns_component_wise_sum(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            a = Point(x=UInt64(10), y=UInt64(20))
            b = Point(x=UInt64(30), y=UInt64(40))
            result = contract.add_points(a, b)
            assert result.x == 40
            assert result.y == 60

    def test_set_point_and_get_point_round_trip(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            contract.set_point(UInt64(5), UInt64(15))
            p = contract.get_point()
            assert p.x == 5
            assert p.y == 15

    @pytest.mark.xfail(reason="Struct._replace() passes _on_mutate to __init__")
    def test_translate_point_updates_saved_point(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            contract.set_point(UInt64(5), UInt64(15))
            result = contract.translate_point(UInt64(10), UInt64(20))
            assert result.x == 15
            assert result.y == 35
            p = contract.get_point()
            assert p.x == 15
            assert p.y == 35

    @pytest.mark.xfail(reason="Struct._replace() passes _on_mutate to __init__")
    def test_copy_and_scale_clones_and_scales(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            contract.set_point(UInt64(5), UInt64(10))
            result = contract.copy_and_scale(UInt64(3))
            assert result.x == 15
            assert result.y == 30
            p = contract.get_point()
            assert p.x == 15
            assert p.y == 30

    def test_set_profile_and_get_profile_round_trip(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            contract.set_profile(String("Alice"), UInt64(30), UInt64(100))
            profile = contract.get_profile()
            assert profile.name == String("Alice")
            assert profile.age == 30
            assert profile.score == 100

    @pytest.mark.xfail(reason="Struct._replace() passes _on_mutate to __init__")
    def test_update_score_preserves_name_and_age(self) -> None:
        with algopy_testing_context():
            contract = ObjectTuples()
            contract.create()
            contract.set_profile(String("Alice"), UInt64(30), UInt64(100))
            result = contract.update_score(UInt64(500))
            assert result.name == String("Alice")
            assert result.age == 30
            assert result.score == 500
            profile = contract.get_profile()
            assert profile.name == String("Alice")
            assert profile.age == 30
            assert profile.score == 500
