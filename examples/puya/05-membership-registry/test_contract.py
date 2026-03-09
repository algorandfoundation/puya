import _algopy_testing.decorators.arc4 as _arc4_mod
import pytest
from algopy import OnCompleteAction, String, UInt64
from algopy_testing import algopy_testing_context
from contract import MembershipRegistry


@pytest.fixture(autouse=True)
def _patch_routing_check():
    """Work around algorand-python-testing 1.1.0 bug where baremethod stores
    on_completion as a string instead of OnCompleteAction, causing
    ``check_routing_conditions`` to fail with ``AttributeError: 'str' has no 'name'``."""
    original = _arc4_mod.check_routing_conditions

    def _patched(app_id: int, metadata: object) -> None:
        from _algopy_testing.context_helpers import lazy_context

        oc = lazy_context.active_group.active_txn.fields.get("on_completion")
        if isinstance(oc, str):
            lazy_context.active_group.active_txn.fields["on_completion"] = getattr(
                OnCompleteAction, oc
            )
        original(app_id, metadata)

    _arc4_mod.check_routing_conditions = _patched
    yield
    _arc4_mod.check_routing_conditions = original


class TestMembershipRegistry:
    def test_init_sets_member_count_to_zero(self) -> None:
        with algopy_testing_context():
            contract = MembershipRegistry()

            assert contract.member_count.value == UInt64(0)

    def test_opt_in_increments_member_count_and_sets_local_state(self) -> None:
        with algopy_testing_context() as ctx:
            contract = MembershipRegistry()

            alice = ctx.any.account()
            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.opt_in()

            assert contract.member_count.value == UInt64(1)
            assert contract.nickname[alice] == String("")
            assert contract.joined_round[alice] >= UInt64(0)

    def test_set_nickname_updates_local_state(self) -> None:
        with algopy_testing_context() as ctx:
            contract = MembershipRegistry()

            alice = ctx.any.account()
            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.opt_in()
            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.set_nickname(String("Alice"))

            assert contract.nickname[alice] == String("Alice")

    def test_get_nickname_reads_local_state(self) -> None:
        with algopy_testing_context() as ctx:
            contract = MembershipRegistry()

            alice = ctx.any.account()
            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.opt_in()
            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.set_nickname(String("Alice"))

            result = contract.get_nickname(alice)
            assert result == String("Alice")

    def test_close_out_decrements_member_count(self) -> None:
        with algopy_testing_context() as ctx:
            contract = MembershipRegistry()

            alice = ctx.any.account()
            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.opt_in()
            assert contract.member_count.value == UInt64(1)

            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.close_out()
            assert contract.member_count.value == UInt64(0)

    def test_get_member_count_after_multiple_opt_in_and_close_out(self) -> None:
        with algopy_testing_context() as ctx:
            contract = MembershipRegistry()

            alice = ctx.any.account()
            bob = ctx.any.account()

            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.opt_in()
            with ctx.txn.create_group(active_txn_overrides={"sender": bob}):
                contract.opt_in()
            assert contract.member_count.value == UInt64(2)

            with ctx.txn.create_group(active_txn_overrides={"sender": bob}):
                contract.close_out()
            assert contract.member_count.value == UInt64(1)

            result = contract.get_member_count()
            assert result == UInt64(1)

    def test_double_opt_in_rejected(self) -> None:
        with algopy_testing_context() as ctx:
            contract = MembershipRegistry()

            alice = ctx.any.account()
            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.opt_in()

            with (
                ctx.txn.create_group(active_txn_overrides={"sender": alice}),
                pytest.raises(AssertionError, match="already a member"),
            ):
                contract.opt_in()
