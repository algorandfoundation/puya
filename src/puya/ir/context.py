import contextlib
from collections.abc import Iterator, Mapping, Sequence

import attrs

import puya.awst.nodes as awst_nodes
from puya.context import CompileContext
from puya.errors import CodeError, InternalError, log_exceptions
from puya.ir.models import Subroutine
from puya.parse import SourceLocation
from puya.utils import attrs_extend


@attrs.frozen(kw_only=True)
class IRBuildContext(CompileContext):
    module_awsts: Mapping[str, awst_nodes.Module]
    subroutines: dict[awst_nodes.Function, Subroutine]
    embedded_funcs: Sequence[awst_nodes.Function] = attrs.field()
    contract: awst_nodes.ContractFragment | None = attrs.field(default=None)

    def resolve_contract_reference(
        self, cref: awst_nodes.ContractReference
    ) -> awst_nodes.ContractFragment:
        # TODO: this probably shouldn't be required, AWST should stitch things together
        try:
            module = self.module_awsts[cref.module_name]
            contract = module.symtable[cref.class_name]
        except KeyError as ex:
            raise InternalError(f"Failed to resolve contract reference {cref}") from ex
        if not isinstance(contract, awst_nodes.ContractFragment):
            raise InternalError(f"Contract reference {cref} resolved to {contract}")
        return contract

    def resolve_function_reference(
        self, target: awst_nodes.SubroutineTarget, source_location: SourceLocation
    ) -> awst_nodes.Function:
        try:
            match target:
                case awst_nodes.BaseClassSubroutineTarget(base_class=cref, name=func_name):
                    contract = self.resolve_contract_reference(cref)
                    func: awst_nodes.Node = contract.symtable[func_name]
                case awst_nodes.InstanceSubroutineTarget(name=func_name):
                    if self.contract is None:
                        raise InternalError(
                            f"Cannot resolve instance function {func_name} "
                            f"as there is no current contract",
                            source_location,
                        )
                    for contract in (
                        self.contract,
                        *[self.resolve_contract_reference(cref) for cref in self.contract.bases],
                    ):
                        try:
                            func = contract.symtable[func_name]
                        except KeyError:
                            pass
                        else:
                            break
                    else:
                        raise InternalError(
                            f"Unable to locate {func_name} in hierarchy "
                            f"for class {self.contract.full_name}",
                            source_location,
                        )
                case awst_nodes.FreeSubroutineTarget(module_name=module_name, name=func_name):
                    # remap the internal _puyapy_ lib to puyapy so that functions
                    # defined in _puyapy_ can reference other functions defined in the same module
                    module_name = "puyapy" if module_name == "_puyapy_" else module_name
                    func = self.module_awsts[module_name].symtable[func_name]
                case _:
                    raise InternalError(
                        f"Unhandled subroutine invocation target: {target}",
                        source_location,
                    )
        except KeyError as ex:
            raise CodeError(
                f"Unable to resolve function reference {target}",
                source_location,
            ) from ex
        if not isinstance(func, awst_nodes.Function):
            raise CodeError(
                f"Function reference {target} resolved to {func}",
                source_location,
            )
        return func

    def for_contract(self, contract: awst_nodes.ContractFragment) -> "IRBuildContextWithFallback":
        return attrs_extend(
            IRBuildContextWithFallback,
            self,
            default_fallback=contract.source_location,
            contract=contract,
            # copy subroutines so that contract specific subroutines do not pollute other contract
            # passes
            subroutines=self.subroutines.copy(),
        )

    def for_function(
        self, function: awst_nodes.Function, subroutine: Subroutine
    ) -> "IRFunctionBuildContext":
        return attrs_extend(
            IRFunctionBuildContext,
            self,
            default_fallback=function.source_location,
            function=function,
            subroutine=subroutine,
        )


@attrs.define
class IRBuildContextWithFallback(IRBuildContext):
    default_fallback: SourceLocation

    @contextlib.contextmanager
    def log_exceptions(self, fallback_location: SourceLocation | None = None) -> Iterator[None]:
        fallback_location = fallback_location or self.default_fallback
        with log_exceptions(self.errors, fallback_location):
            yield


@attrs.frozen(kw_only=True)
class IRFunctionBuildContext(IRBuildContextWithFallback):
    """Context when building from an awst Function node"""

    function: awst_nodes.Function
    subroutine: Subroutine
