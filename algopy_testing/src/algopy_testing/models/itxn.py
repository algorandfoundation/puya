from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    # from algopy_testing.models.asset import Asset
    import algopy

T = TypeVar("T")


class ITxn:
    @staticmethod
    def _get_attr(
        name: str,
    ) -> algopy.Account | algopy.UInt64 | algopy.Bytes | algopy.Asset | algopy.Application | bool:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )
        if not context.inner_transactions:
            raise ValueError(
                "No inner transaction found in the context! Use `with algopy_testing_context()` "
                "to access the context manager."
            )
        itxn = context.inner_transactions[-1]

        if name not in itxn.__dict__:
            raise AttributeError(
                f"'Txn' object has no value set for attribute named '{name}'. "
                f"Use `context.patch_itxn_fields({name}=your_value)` to set the value "
                "in your test setup."
            )

        return itxn.__dict__[name]  # type: ignore[no-any-return]

    @staticmethod
    def _cast_attr(name: str, _expected_type: type[T]) -> T:
        return cast(T, ITxn._get_attr(name))

    @staticmethod
    def sender() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("sender", Account)

    @staticmethod
    def fee() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("fee", UInt64)

    @staticmethod
    def first_valid() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("first_valid", UInt64)

    @staticmethod
    def last_valid() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("last_valid", UInt64)

    @staticmethod
    def note() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("note", Bytes)

    @staticmethod
    def lease() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("lease", Bytes)

    @staticmethod
    def receiver() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("receiver", Account)

    @staticmethod
    def amount() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("amount", UInt64)

    @staticmethod
    def close_remainder_to() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("close_remainder_to", Account)

    @staticmethod
    def vote_pk() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("vote_pk", Bytes)

    @staticmethod
    def selection_pk() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("selection_pk", Bytes)

    @staticmethod
    def vote_first() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("vote_first", UInt64)

    @staticmethod
    def vote_last() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("vote_last", UInt64)

    @staticmethod
    def vote_key_dilution() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("vote_key_dilution", UInt64)

    @staticmethod
    def type() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("type", Bytes)

    @staticmethod
    def type_enum() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("type_enum", UInt64)

    @staticmethod
    def xfer_asset() -> algopy.Asset:
        from algopy import Asset

        return ITxn._cast_attr("xfer_asset", Asset)

    @staticmethod
    def asset_amount() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("asset_amount", UInt64)

    @staticmethod
    def asset_sender() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("asset_sender", Account)

    @staticmethod
    def asset_receiver() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("asset_receiver", Account)

    @staticmethod
    def asset_close_to() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("asset_close_to", Account)

    @staticmethod
    def group_index() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("group_index", UInt64)

    @staticmethod
    def tx_id() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("tx_id", Bytes)

    @staticmethod
    def application_id() -> algopy.Application:
        from algopy import Application

        return ITxn._cast_attr("application_id", Application)

    @staticmethod
    def on_completion() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("on_completion", UInt64)

    @staticmethod
    def approval_program() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("approval_program", Bytes)

    @staticmethod
    def clear_state_program() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("clear_state_program", Bytes)

    @staticmethod
    def rekey_to() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("rekey_to", Account)

    @staticmethod
    def config_asset() -> algopy.Asset:
        from algopy import Asset

        return ITxn._cast_attr("config_asset", Asset)

    @staticmethod
    def config_asset_total() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("config_asset_total", UInt64)

    @staticmethod
    def config_asset_decimals() -> algopy.UInt64:
        from algopy import UInt64

        return ITxn._cast_attr("config_asset_decimals", UInt64)

    @staticmethod
    def config_asset_default_frozen() -> bool:
        return ITxn._cast_attr("config_asset_default_frozen", bool)

    @staticmethod
    def config_asset_unit_name() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("config_asset_unit_name", Bytes)

    @staticmethod
    def config_asset_name() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("config_asset_name", Bytes)

    @staticmethod
    def config_asset_url() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("config_asset_url", Bytes)

    @staticmethod
    def config_asset_metadata_hash() -> algopy.Bytes:
        from algopy import Bytes

        return ITxn._cast_attr("config_asset_metadata_hash", Bytes)

    @staticmethod
    def config_asset_manager() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("config_asset_manager", Account)

    @staticmethod
    def config_asset_reserve() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("config_asset_reserve", Account)

    @staticmethod
    def config_asset_freeze() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("config_asset_freeze", Account)

    @staticmethod
    def config_asset_clawback() -> algopy.Account:
        from algopy import Account

        return ITxn._cast_attr("config_asset_clawback", Account)

    @staticmethod
    def freeze_asset() -> algopy.Asset:
        from algopy import Asset

        return ITxn._cast_attr("freeze_asset", Asset)
