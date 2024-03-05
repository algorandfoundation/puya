import abc
import typing

from puyapy import UInt64, urange

class Contract(abc.ABC):
    """Base class for an Algorand Smart Contract"""

    def __init_subclass__(
        cls,
        *,
        name: typing.LiteralString = ...,
        scratch_slots: urange | tuple[int | urange, ...] | list[int | urange] = ...,
        **kwargs: object,
    ):
        """
        When declaring a Contract subclass, options and configuration are passed in
        the base class list:

        ```python
        class MyContract(puyapy.Contract, name="CustomName"):
            ...
        ```

        :param name: will affect the output TEAL file name if there are multiple non-abstract contracts
        in the same file.
        If the contract is a subclass of puyapy.ARC4Contract, `name` will also be used as the
        contract name in the ARC-32 application.json, instead of the class name.

        :param scratch_slots: allows you to mark a slot ID or range of slot IDs as "off limits" to Puya.
        These slot ID(s) will never be written to or otherwise manipulating by the compiler itself.
        This is particularly useful in combination with `puyapy.op.gload_bytes` / `puyapy.op.gload_uint64`
        which lets a contract in a group transaction read from the scratch slots of another contract
        that occurs earlier in the transaction group.

        In the case of inheritance, scratch slots reserved become cumulative. It is not an error
        to have overlapping ranges or values either, so if a base class contract reserves slots
        0-5 inclusive and the derived contract reserves 5-10 inclusive, then within the derived
        contract all slots 0-10 will be marked as reserved.
        """
    @abc.abstractmethod
    def approval_program(self) -> UInt64 | bool:
        """Represents the program called for all transactions
        where `OnCompletion` != `ClearState`"""
    @abc.abstractmethod
    def clear_state_program(self) -> UInt64 | bool:
        """Represents the program called when `OnCompletion` == `ClearState`"""
