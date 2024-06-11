from collections.abc import Mapping
import typing
from algopy import (
    Account,
    Bytes,
    Contract,
    LogicSig,
    UInt64,
)

class CompiledContract(typing.Protocol):
    @property
    def approval_program(self) -> tuple[Bytes, Bytes]:
        """TODO"""

    @property
    def clear_state_program(self) -> tuple[Bytes, Bytes]:
        """TODO"""

    @property
    def extra_program_pages(self) -> UInt64:
        """TODO"""

    @property
    def global_uints(self) -> UInt64:
        """TODO"""

    @property
    def global_bytes(self) -> UInt64:
        """TODO"""

    @property
    def local_uints(self) -> UInt64:
        """TODO"""

    @property
    def local_bytes(self) -> UInt64:
        """TODO"""

class CompiledLogicSig(typing.Protocol):
    @property
    def account(self) -> Account:
        """TODO"""

def compile_contract(
    contract: type[Contract],
    /,
    extra_program_pages: UInt64 | int = ...,
    global_uints: UInt64 | int = ...,
    global_bytes: UInt64 | int = ...,
    local_uints: UInt64 | int = ...,
    local_bytes: UInt64 | int = ...,
    template_vars: Mapping[str, object] = ...,
    template_vars_prefix: str = ...,
) -> CompiledContract:
    """
    Returns the compiled data for the specified contract

    :param contract: Contract
    :param extra_program_pages: Number of extra program pages, defaults to minimum required for contract
    :param global_uints: Number of global uint64s, defaults to value defined for contract
    :param global_bytes: Number of global bytes, defaults to value defined for contract
    :param local_uints: Number of local uint64s, defaults to value defined for contract
    :param local_bytes: Number of local bytes, defaults to value defined for contract
    :param template_vars: Template variables to substitute into the contract,
                          key should be without the prefix, must evaluate to a compile time constant
                          and match the type of the template var declaration
    :param template_vars_prefix: Prefix to add to provided template vars,
                   defaults to the prefix supplied on command line (which defaults to TMPL_)
    """

def compile_logicsig(
    logicsig: LogicSig,
    /,
    template_vars: Mapping[str, object] = ...,
    template_vars_prefix: str = ...,
) -> CompiledLogicSig:
    """
    Returns the Account for the specified logic signature

    :param logicsig: Logic Signature
    :param template_vars: Template variables to substitute into the logic signature,
                          key should be without the prefix, must evaluate to a compile time constant
                          and match the type of the template var declaration
    :param template_vars_prefix: Prefix to add to provided template vars,
                                 defaults to the prefix supplied on command line (which defaults to TMPL_)
    """
