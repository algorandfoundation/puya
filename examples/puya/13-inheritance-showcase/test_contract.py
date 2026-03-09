from algopy import String, UInt64
from algopy_testing import algopy_testing_context
from contract import Dog, MultiInheritanceShowcase, ShowDog


class TestDog:
    def test_create_sets_name_legs_trick(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(String("Rex"), UInt64(4))
            assert dog.name.value == "Rex"
            assert dog.legs.value == UInt64(4)
            assert dog.trick.value == "sit"

    def test_speak_returns_woof(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(String("Rex"), UInt64(4))
            result = dog.speak()
            assert result == String("Rex says Woof!")

    def test_describe_includes_trick(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(String("Rex"), UInt64(4))
            result = dog.describe()
            assert result == String("Rex has 4 legs and knows sit")

    def test_set_trick_and_get_trick(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(String("Rex"), UInt64(4))
            dog.set_trick(String("roll over"))
            assert dog.get_trick() == String("roll over")

    def test_species_type_returns_animal(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(String("Rex"), UInt64(4))
            assert dog.species_type() == String("Animal")


class TestShowDog:
    def test_create_chains_through_dog_to_animal(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(String("Bella"), UInt64(4))
            assert sd.name.value == "Bella"
            assert sd.legs.value == UInt64(4)
            assert sd.trick.value == "sit"
            assert sd.awards.value == UInt64(0)

    def test_speak_returns_champion_string(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(String("Bella"), UInt64(4))
            result = sd.speak()
            assert result == String("Bella says Woof! (Show champion)")

    def test_win_award_increments_awards(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(String("Bella"), UInt64(4))
            result = sd.win_award()
            assert result == UInt64(1)
            result = sd.win_award()
            assert result == UInt64(2)

    def test_get_awards_returns_count(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(String("Bella"), UInt64(4))
            assert sd.get_awards() == UInt64(0)
            sd.win_award()
            assert sd.get_awards() == UInt64(1)


class TestMultiInheritanceShowcase:
    def test_create_inits_both_bases(self) -> None:
        with algopy_testing_context():
            contract = MultiInheritanceShowcase()
            contract.create()
            assert contract.paused.value is False
            assert contract.description.value == String("")

    def test_pause_and_unpause(self) -> None:
        with algopy_testing_context():
            contract = MultiInheritanceShowcase()
            contract.create()
            assert contract.is_paused() is False
            contract.pause()
            assert contract.is_paused() is True
            contract.unpause()
            assert contract.is_paused() is False

    def test_set_and_get_description(self) -> None:
        with algopy_testing_context():
            contract = MultiInheritanceShowcase()
            contract.create()
            contract.set_description(String("Hello"))
            assert contract.get_description() == String("Hello")

    def test_get_status_when_paused(self) -> None:
        with algopy_testing_context():
            contract = MultiInheritanceShowcase()
            contract.create()
            contract.set_description(String("Active"))
            contract.pause()
            assert contract.get_status() == String("paused")

    def test_get_status_when_not_paused(self) -> None:
        with algopy_testing_context():
            contract = MultiInheritanceShowcase()
            contract.create()
            contract.set_description(String("Running"))
            assert contract.get_status() == String("Running")
