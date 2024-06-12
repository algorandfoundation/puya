from __future__ import annotations

import abc

from attr import dataclass

if TYPE_CHECKING:
    import algopy


@dataclass
class StateTotals:
    global_uints: int | None = None
    global_bytes: int | None = None
    local_uints: int | None = None
    local_bytes: int | None = None


class _ContractMeta(type):
    def __call__(cls, *args: Any, **kwargs: dict[str, Any]) -> Any:  # noqa: ANN401
        from algopy import Contract

        from algopy_testing.context import get_test_context

        context = get_test_context()
        instance = super().__call__(*args, **kwargs)

        if context and isinstance(instance, Contract):
            context.add_contract(instance)

        return instance


class Contract(metaclass=_ContractMeta):
    """Base class for an Algorand Smart Contract"""

    _name: str
    _scratch_slots: Any | None
    _state_totals: StateTotals | None

    def __init_subclass__(
        cls,
        *,
        name: str | None = None,
        scratch_slots: algopy.UInt64
        | tuple[int | algopy.UInt64, ...]
        | list[int | algopy.UInt64]
        | None = None,
        state_totals: StateTotals | None = None,
    ):
        cls._name = name or cls.__name__
        cls._scratch_slots = scratch_slots
        cls._state_totals = state_totals

    @abc.abstractmethod
    def approval_program(self) -> algopy.UInt64 | bool:
        """Represents the program called for all transactions where `OnCompletion` != `ClearState`"""

    @abc.abstractmethod
    def clear_state_program(self) -> algopy.UInt64 | bool:
        """Represents the program called when `OnCompletion` == `ClearState`"""
