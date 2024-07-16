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
    """
    Provides compiled programs and state allocation values for a Contract.
    Create by calling [`compile_contract`](#algopy.compile_contract).
    """

    @property
    def approval_program(self) -> tuple[Bytes, Bytes]:
        """
        Approval program pages for a contract, after template variables have been replaced
        and compiled to AVM bytecode
        """

    @property
    def clear_state_program(self) -> tuple[Bytes, Bytes]:
        """
        Clear state program pages for a contract, after template variables have been replaced
        and compiled to AVM bytecode
        """

    @property
    def extra_program_pages(self) -> UInt64:
        """
        By default, provides extra program pages required based on approval and clear state program
        size, can be overridden when calling compile_contract
        """

    @property
    def global_uints(self) -> UInt64:
        """
        By default, provides global num uints based on contract state totals, can be overridden
        when calling compile_contract
        """

    @property
    def global_bytes(self) -> UInt64:
        """
        By default, provides global num bytes based on contract state totals, can be overridden
        when calling compile_contract
        """

    @property
    def local_uints(self) -> UInt64:
        """
        By default, provides local num uints based on contract state totals, can be overridden
        when calling compile_contract
        """

    @property
    def local_bytes(self) -> UInt64:
        """
        By default, provides local num bytes based on contract state totals, can be overridden
        when calling compile_contract
        """

class CompiledLogicSig(typing.Protocol):
    """
    Provides account for a Logic Signature.
    Create by calling [`compile_logicsig`](#algopy.compile_logicsig).
    """

    @property
    def account(self) -> Account:
        """
        Address of a logic sig program, after template variables have been replaced and compiled
        to AVM bytecode
        """

def compile_contract(
    contract: type[Contract],
    /,
    *,
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

    :param contract: Algorand Python Contract to compile
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
    *,
    template_vars: Mapping[str, object] = ...,
    template_vars_prefix: str = ...,
) -> CompiledLogicSig:
    """
    Returns the Account for the specified logic signature

    :param logicsig: Algorand Python Logic Signature to compile
    :param template_vars: Template variables to substitute into the logic signature,
                          key should be without the prefix, must evaluate to a compile time constant
                          and match the type of the template var declaration
    :param template_vars_prefix: Prefix to add to provided template vars,
                                 defaults to the prefix supplied on command line (which defaults to TMPL_)
    """
