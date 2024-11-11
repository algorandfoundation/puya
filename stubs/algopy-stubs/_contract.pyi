import abc
import typing

from algopy import UInt64, urange

@typing.final
class StateTotals:
    """
    Options class to manually define the total amount of global and local state contract will use,
    used by [`Contract.__init_subclass__`](#algopy.Contract.__init_subclass__).

    This is not required when all state is assigned to `self.`, but is required if a
    contract dynamically interacts with state via `AppGlobal.get_bytes` etc, or if you want
    to reserve additional state storage for future contract updates, since the Algorand protocol
    doesn't allow increasing them after creation.
    """

    def __init__(
        self,
        *,
        global_uints: int = ...,
        global_bytes: int = ...,
        local_uints: int = ...,
        local_bytes: int = ...,
    ) -> None:
        """Specify the totals for both global and local, and for each type. Any arguments not
        specified default to their automatically calculated values.

        Values are validated against the known totals assigned through `self.`, a warning is
        produced if the total specified is insufficient to accommodate all `self.` state values
        at once.
        """

class Contract(abc.ABC):
    """Base class for an Algorand Smart Contract"""

    def __init_subclass__(
        cls,
        *,
        name: str = ...,
        scratch_slots: urange | tuple[int | urange, ...] | list[int | urange] = ...,
        state_totals: StateTotals = ...,
        avm_version: int = ...,
    ):
        """
        When declaring a Contract subclass, options and configuration are passed in
        the base class list:

        ```python
        class MyContract(algopy.Contract, name="CustomName"):
            ...
        ```

        :param name:
         Will affect the output TEAL file name if there are multiple non-abstract contracts
         in the same file.

         If the contract is a subclass of algopy.ARC4Contract, `name` will also be used as the
         contract name in the ARC-32 application.json, instead of the class name.

        :param scratch_slots:
         Allows you to mark a slot ID or range of slot IDs as "off limits" to Puya.
         These slot ID(s) will never be written to or otherwise manipulating by the compiler itself.
         This is particularly useful in combination with `algopy.op.gload_bytes` / `algopy.op.gload_uint64`
         which lets a contract in a group transaction read from the scratch slots of another contract
         that occurs earlier in the transaction group.

         In the case of inheritance, scratch slots reserved become cumulative. It is not an error
         to have overlapping ranges or values either, so if a base class contract reserves slots
         0-5 inclusive and the derived contract reserves 5-10 inclusive, then within the derived
         contract all slots 0-10 will be marked as reserved.

        :param state_totals:
         Allows defining what values should be used for global and local uint and bytes storage
         values when creating a contract. Used when outputting ARC-32 application.json schemas.

         If let unspecified, the totals will be determined by the compiler based on state
         variables assigned to `self`.

         This setting is not inherited, and only applies to the exact `Contract` it is specified
         on. If a base class does specify this setting, and a derived class does not, a warning
         will be emitted for the derived class. To resolve this warning, `state_totals` must be
         specified. Note that it is valid to not provide any arguments to the `StateTotals`
         constructor, like so `state_totals=StateTotals()`, in which case all values will be
         automatically calculated.
        :param avm_version:
         Determines which AVM version to use, this affects what operations are supported.
         Defaults to value provided supplied on command line (which defaults to current mainnet version)
        """

    @abc.abstractmethod
    def approval_program(self) -> UInt64 | bool:
        """Represents the program called for all transactions
        where `OnCompletion` != `ClearState`"""

    @abc.abstractmethod
    def clear_state_program(self) -> UInt64 | bool:
        """Represents the program called when `OnCompletion` == `ClearState`"""
