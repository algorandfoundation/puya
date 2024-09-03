import contextlib
import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping
from functools import cached_property

import attrs

import puya.awst.nodes as awst_nodes
import puya.models
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
    awst: awst_nodes.AWST
    subroutines: dict[awst_nodes.Function, Subroutine]
    embedded_funcs_lookup: Mapping[str, Subroutine] = attrs.field(default=dict)
    root: awst_nodes.ContractFragment | awst_nodes.LogicSignature | None = None
    routers: dict[puya.models.ContractReference, Subroutine] = attrs.field(factory=dict)

    @cached_property
    def _awst_lookup(self) -> Mapping[str, awst_nodes.RootNode]:
        return {node.id: node for node in self.awst}

    def for_root(
        self, root: awst_nodes.ContractFragment | awst_nodes.LogicSignature
    ) -> typing.Self:
        return attrs.evolve(
            self,
            root=root,
            # copy subroutines so that contract specific subroutines do not pollute other passes
            subroutines=self.subroutines.copy(),
        )

    def for_function(
        self, function: awst_nodes.Function, subroutine: Subroutine, visitor: "FunctionIRBuilder"
    ) -> "IRFunctionBuildContext":
        return attrs_extend(
            IRFunctionBuildContext, self, visitor=visitor, function=function, subroutine=subroutine
        )

    def resolve_contract_reference(
        self, cref: puya.models.ContractReference
    ) -> awst_nodes.ContractFragment:
        contract = self._awst_lookup[cref]
        if not isinstance(contract, awst_nodes.ContractFragment):
            raise InternalError(f"contract reference {cref} resolved to {contract}")
        return contract

    def resolve_function_reference(
        self,
        target: awst_nodes.SubroutineTarget,
        source_location: SourceLocation,
        caller: awst_nodes.Function,
    ) -> awst_nodes.Function:
        match target:
            case awst_nodes.SubroutineID(sub_id):
                func: awst_nodes.Node | None = self._awst_lookup.get(sub_id)
            case awst_nodes.InstanceMethodTarget(member_name=member_name):
                func = self._resolve_contract_method(member_name, source_location)
            case awst_nodes.ContractMethodTarget(cref=start_at, member_name=member_name):
                func = self._resolve_contract_method(member_name, source_location, start=start_at)
            case awst_nodes.InstanceSuperMethodTarget(member_name=member_name):
                if not isinstance(caller, awst_nodes.ContractMethod):
                    raise CodeError(
                        "call to contract method from outside of contract class",
                        source_location,
                    )
                func = self._resolve_contract_method(
                    member_name, source_location, start=caller.cref, skip=True
                )
            case unexpected:
                typing.assert_never(unexpected)
        if func is None:
            raise CodeError(f"unable to resolve function reference {target}", source_location)
        if not isinstance(func, awst_nodes.Function):
            raise CodeError(
                f"function reference {target} resolved to non-function {func}", source_location
            )
        return func

    @typing.overload
    def _resolve_contract_method(
        self, name: str, source_location: SourceLocation
    ) -> awst_nodes.ContractMethod: ...

    @typing.overload
    def _resolve_contract_method(
        self,
        name: str,
        source_location: SourceLocation,
        *,
        start: puya.models.ContractReference,
        skip: bool = False,
    ) -> awst_nodes.ContractMethod: ...

    def _resolve_contract_method(
        self,
        name: str,
        source_location: SourceLocation,
        *,
        start: puya.models.ContractReference | None = None,
        skip: bool = False,
    ) -> awst_nodes.ContractMethod | None:
        root = self.root
        if not isinstance(root, awst_nodes.ContractFragment):
            raise InternalError(
                f"cannot resolve contract member {name} as there is no current contract",
                source_location,
            )
        mro = [root.id, *root.bases]
        if start:
            try:
                curr_idx = mro.index(start)
            except ValueError:
                raise CodeError(
                    "call to base method outside current hierarchy", source_location
                ) from None
            mro = mro[curr_idx:]
        if skip:
            mro = mro[1:]
        for cref in mro:
            contract = self.resolve_contract_reference(cref)
            with contextlib.suppress(KeyError):
                method = contract.methods[name]
                if method.inheritable or cref == root.id:
                    return method
        return None

    @property
    def default_fallback(self) -> SourceLocation | None:
        if self.root:
            return self.root.source_location
        return None

    @contextlib.contextmanager
    def log_exceptions(self, fallback_location: SourceLocation | None = None) -> Iterator[None]:
        with log_exceptions(fallback_location or self.default_fallback):
            yield


@attrs.frozen(kw_only=True)
class IRFunctionBuildContext(IRBuildContext):
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

    @property
    def default_fallback(self) -> SourceLocation | None:
        return self.function.source_location

    def resolve_subroutine(
        self,
        target: awst_nodes.SubroutineTarget,
        source_location: SourceLocation,
        *,
        caller: awst_nodes.Function | None = None,
    ) -> Subroutine:
        func = self.resolve_function_reference(
            target=target, source_location=source_location, caller=caller or self.function
        )
        return self.subroutines[func]
