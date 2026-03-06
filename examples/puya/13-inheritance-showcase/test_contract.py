from algopy import String, UInt64, arc4
from algopy_testing import algopy_testing_context
from contract import Dog, MultiInheritanceShowcase, ShowDog


class TestDog:
    def test_create_sets_name_legs_trick(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(arc4.String("Rex"), arc4.UInt64(4))
            assert dog.name.value == "Rex"
            assert dog.legs.value == UInt64(4)
            assert dog.trick.value == "sit"

    def test_speak_returns_woof(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(arc4.String("Rex"), arc4.UInt64(4))
            result = dog.speak()
            assert result == arc4.String("Rex says Woof!")

    def test_describe_includes_trick(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(arc4.String("Rex"), arc4.UInt64(4))
            result = dog.describe()
            assert result == arc4.String("Rex has 4 legs and knows sit")

    def test_set_trick_and_get_trick(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(arc4.String("Rex"), arc4.UInt64(4))
            dog.set_trick(arc4.String("roll over"))
            assert dog.get_trick() == arc4.String("roll over")

    def test_species_type_returns_animal(self) -> None:
        with algopy_testing_context():
            dog = Dog()
            dog.create(arc4.String("Rex"), arc4.UInt64(4))
            assert dog.species_type() == arc4.String("Animal")


class TestShowDog:
    def test_create_chains_through_dog_to_animal(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(arc4.String("Bella"), arc4.UInt64(4))
            assert sd.name.value == "Bella"
            assert sd.legs.value == UInt64(4)
            assert sd.trick.value == "sit"
            assert sd.awards.value == UInt64(0)

    def test_speak_returns_champion_string(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(arc4.String("Bella"), arc4.UInt64(4))
            result = sd.speak()
            assert result == arc4.String("Bella says Woof! (Show champion)")

    def test_win_award_increments_awards(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(arc4.String("Bella"), arc4.UInt64(4))
            result = sd.win_award()
            assert result == UInt64(1)
            result = sd.win_award()
            assert result == UInt64(2)

    def test_get_awards_returns_count(self) -> None:
        with algopy_testing_context():
            sd = ShowDog()
            sd.create(arc4.String("Bella"), arc4.UInt64(4))
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
            contract.set_description(arc4.String("Hello"))
            assert contract.get_description() == arc4.String("Hello")

    def test_get_status_when_paused(self) -> None:
        with algopy_testing_context():
            contract = MultiInheritanceShowcase()
            contract.create()
            contract.set_description(arc4.String("Active"))
            contract.pause()
            assert contract.get_status() == arc4.String("paused")

    def test_get_status_when_not_paused(self) -> None:
        with algopy_testing_context():
            contract = MultiInheritanceShowcase()
            contract.create()
            contract.set_description(arc4.String("Running"))
            assert contract.get_status() == arc4.String("Running")
