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
    def global_num_uint(self) -> UInt64:
        """TODO"""

    @property
    def global_num_bytes(self) -> UInt64:
        """TODO"""

    @property
    def local_num_uint(self) -> UInt64:
        """TODO"""

    @property
    def local_num_bytes(self) -> UInt64:
        """TODO"""

class CompiledLogicSig(typing.Protocol):
    @property
    def account(self) -> Account:
        """TODO"""

def compile_contract(
    contract: type[Contract],
    /,
    template_vars: Mapping[str, object] = ...,
    template_vars_prefix: str = ...,
) -> CompiledContract:
    """
    Returns the compiled data for the specified contract

    :param contract: Contract
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
