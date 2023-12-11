import contextlib
from collections.abc import Iterator, Mapping

import attrs

import puya.awst.nodes as awst_nodes
from puya.context import CompileContext
from puya.errors import CodeError, InternalError, crash_report
from puya.ir.models import Subroutine
from puya.parse import SourceLocation
from puya.utils import attrs_extend


@attrs.frozen
class IRBuildContext(CompileContext):
    module_awsts: Mapping[str, awst_nodes.Module]
    contract: awst_nodes.ContractFragment
    subroutines: dict[awst_nodes.Function, Subroutine]

    def for_function(
        self, function: awst_nodes.Function, subroutine: Subroutine
    ) -> "IRFunctionBuildContext":
        return attrs_extend(
            IRFunctionBuildContext,
            self,
            function=function,
            subroutine=subroutine,
        )

    def _default_fallback(self) -> SourceLocation:
        return self.contract.source_location

    @contextlib.contextmanager
    def log_exceptions(self, fallback_location: SourceLocation | None = None) -> Iterator[None]:
        fallback_location = fallback_location or self._default_fallback()
        try:
            yield
        except CodeError as ex:
            self.errors.error(str(ex), location=ex.location or fallback_location)
        except InternalError as ex:
            self.errors.error(f"FATAL {ex!s}", location=ex.location or fallback_location)
            crash_report(ex.location or fallback_location)
        except Exception as ex:
            self.errors.error(f"UNEXPECTED {ex!s}", location=fallback_location)
            crash_report(fallback_location)

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
        self, invocation: awst_nodes.SubroutineCallExpression
    ) -> awst_nodes.Function:
        try:
            match invocation.target:
                case awst_nodes.BaseClassSubroutineTarget(base_class=cref, name=func_name):
                    contract = self.resolve_contract_reference(cref)
                    func: awst_nodes.Node = contract.symtable[func_name]
                case awst_nodes.InstanceSubroutineTarget(name=func_name) as instance:
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
                            f"Unable to locate {instance.name} in hierarchy"
                            f" for class {self.contract.full_name}",
                            invocation.source_location,
                        )
                case awst_nodes.FreeSubroutineTarget(module_name=module_name, name=func_name):
                    func = self.module_awsts[module_name].symtable[func_name]
                case _:
                    raise InternalError(
                        f"Unhandled subroutine invocation target: {invocation.target}",
                        invocation.source_location,
                    )
        except KeyError as ex:
            raise CodeError(
                f"Unable to resolve function reference {invocation.target}",
                invocation.source_location,
            ) from ex
        if not isinstance(func, awst_nodes.Function):
            raise CodeError(
                f"Function reference {invocation.target} resolved to {func}",
                invocation.source_location,
            )
        return func


@attrs.frozen
class IRFunctionBuildContext(IRBuildContext):
    """Context when building from an awst Function node"""

    function: awst_nodes.Function
    subroutine: Subroutine

    def _default_fallback(self) -> SourceLocation:
        return self.function.source_location
