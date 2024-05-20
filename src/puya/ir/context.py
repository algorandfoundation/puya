import contextlib
import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence

import attrs

import puya.awst.nodes as awst_nodes
from puya.context import CompileContext
from puya.errors import CodeError, InternalError, log_exceptions
from puya.ir.builder.blocks import BlocksBuilder
from puya.ir.models import Subroutine
from puya.ir.ssa import BraunSSA
from puya.parse import SourceLocation
from puya.utils import attrs_extend

if typing.TYPE_CHECKING:
    from puya.ir.builder.main import FunctionIRBuilder

TMP_VAR_INDICATOR = "%"


@attrs.frozen(kw_only=True)
class IRBuildContext(CompileContext):
    module_awsts: Mapping[str, awst_nodes.Module]
    subroutines: dict[awst_nodes.Function, Subroutine]
    embedded_funcs: Sequence[awst_nodes.Function] = attrs.field()
    contract: awst_nodes.ContractFragment | None = None
    logic_sig: awst_nodes.LogicSignature | None = None

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
        self, function: awst_nodes.Function, subroutine: Subroutine, visitor: "FunctionIRBuilder"
    ) -> "IRFunctionBuildContext":
        return attrs_extend(
            IRFunctionBuildContext,
            self,
            default_fallback=function.source_location,
            visitor=visitor,
            function=function,
            subroutine=subroutine,
        )

    def for_logic_signature(
        self, logic_sig: awst_nodes.LogicSignature
    ) -> "IRBuildContextWithFallback":
        return attrs_extend(
            IRBuildContextWithFallback,
            self,
            default_fallback=logic_sig.source_location,
            logic_sig=logic_sig,
            subroutines=self.subroutines.copy(),
        )

    def resolve_contract_reference(
        self, cref: awst_nodes.ContractReference
    ) -> awst_nodes.ContractFragment:
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
                case awst_nodes.BaseClassSubroutineTarget(base_class=base_cref, name=func_name):
                    func: awst_nodes.Node = self._resolve_contract_attribute(
                        func_name, source_location, start=base_cref
                    )
                case awst_nodes.InstanceSubroutineTarget(name=func_name):
                    func = self._resolve_contract_attribute(func_name, source_location)
                case awst_nodes.FreeSubroutineTarget(module_name=module_name, name=func_name):
                    # remap the internal _algopy_ lib to algopy so that functions
                    # defined in _algopy_ can reference other functions defined in the same module
                    module_name = "algopy" if module_name == "_algopy_" else module_name
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

    def resolve_state(  # TODO: yeet me
        self, field_name: str, source_location: SourceLocation
    ) -> awst_nodes.AppStorageDefinition:
        node = self._resolve_contract_attribute(field_name, source_location)
        if not isinstance(node, awst_nodes.AppStorageDefinition):
            raise CodeError(f"State reference {field_name} resolved to {node}", source_location)
        return node

    def _resolve_contract_attribute(
        self,
        name: str,
        source_location: SourceLocation,
        *,
        start: awst_nodes.ContractReference | None = None,
    ) -> awst_nodes.ContractMethod | awst_nodes.AppStorageDefinition:
        current = self.contract
        if current is None:
            raise InternalError(
                f"Cannot resolve contract member {name} as there is no current contract",
                source_location,
            )
        if start is None:
            start_contract = current
        else:
            if start not in current.bases:
                raise CodeError("Call to base method outside current hierarchy", source_location)
            start_contract = self.resolve_contract_reference(start)
        for contract in (
            start_contract,
            *[self.resolve_contract_reference(cref) for cref in start_contract.bases],
        ):
            with contextlib.suppress(KeyError):
                return contract.symtable[name]
        raise CodeError(
            f"Unresolvable attribute '{name}' of {start_contract.full_name}",
            source_location,
        )


@attrs.define(kw_only=True)
class IRBuildContextWithFallback(IRBuildContext):
    default_fallback: SourceLocation

    @contextlib.contextmanager
    def log_exceptions(self, fallback_location: SourceLocation | None = None) -> Iterator[None]:
        with log_exceptions(fallback_location or self.default_fallback):
            yield


@attrs.frozen(kw_only=True)
class IRFunctionBuildContext(IRBuildContextWithFallback):
    """Context when building from an awst Function node"""

    function: awst_nodes.Function
    subroutine: Subroutine
    visitor: "FunctionIRBuilder"
    block_builder: BlocksBuilder = attrs.field()
    _tmp_counters: defaultdict[str, Iterator[int]] = attrs.field(
        factory=lambda: defaultdict(itertools.count)
    )

    @property
    def ssa(self) -> BraunSSA:
        return self.block_builder.ssa

    @block_builder.default
    def _block_builder_factory(self) -> BlocksBuilder:
        return BlocksBuilder(self.subroutine.parameters, self.function.source_location)

    def next_tmp_name(self, description: str) -> str:
        counter_value = next(self._tmp_counters[description])
        return f"{description}{TMP_VAR_INDICATOR}{counter_value}"
