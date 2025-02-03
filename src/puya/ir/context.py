import contextlib
import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping
from functools import cached_property

import attrs

import puya.awst.nodes as awst_nodes
from puya.context import CompileContext
from puya.errors import CodeError, log_exceptions
from puya.ir.builder._utils import (
    assign,
    get_implicit_return_is_original,
    get_implicit_return_out,
)
from puya.ir.builder.blocks import BlocksBuilder
from puya.ir.models import (
    TMP_VAR_INDICATOR,
    Assignment,
    ConditionalBranch,
    Op,
    Register,
    Subroutine,
    ValueProvider,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.ssa import BraunSSA
from puya.ir.types_ import IRType, PrimitiveIRType
from puya.parse import SourceLocation
from puya.program_refs import ContractReference
from puya.utils import attrs_extend

if typing.TYPE_CHECKING:
    from puya.ir.builder.main import FunctionIRBuilder


@attrs.frozen(kw_only=True)
class IRBuildContext(CompileContext):
    awst: awst_nodes.AWST
    subroutines: dict[awst_nodes.Function, Subroutine]
    embedded_funcs_lookup: Mapping[str, Subroutine]
    root: awst_nodes.Contract | awst_nodes.LogicSignature | None = None
    routers: dict[ContractReference, Subroutine] = attrs.field(factory=dict)

    @cached_property
    def _awst_lookup(self) -> Mapping[str, awst_nodes.RootNode]:
        return {node.id: node for node in self.awst}

    def for_root(self, root: awst_nodes.Contract | awst_nodes.LogicSignature) -> typing.Self:
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

    def resolve_function_reference(
        self,
        target: awst_nodes.SubroutineTarget,
        source_location: SourceLocation,
        caller: awst_nodes.Function,
    ) -> awst_nodes.Function:
        if isinstance(target, awst_nodes.SubroutineID):
            func: awst_nodes.Node | None = self._awst_lookup.get(target.target)
        else:
            contract = self.root
            if not (
                isinstance(contract, awst_nodes.Contract)
                and isinstance(caller, awst_nodes.ContractMethod)
            ):
                raise CodeError(
                    "call to contract method from outside of contract class",
                    source_location,
                )
            match target:
                case awst_nodes.InstanceMethodTarget(member_name=member_name):
                    func = contract.resolve_contract_method(member_name)
                case awst_nodes.ContractMethodTarget(cref=start_at, member_name=member_name):
                    func = contract.resolve_contract_method(
                        member_name, source_location, start=start_at
                    )
                case awst_nodes.InstanceSuperMethodTarget(member_name=member_name):
                    func = contract.resolve_contract_method(
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
class IRFunctionBuildContext(IRBuildContext, IRRegisterContext):
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

    def new_register(
        self, name: str, ir_type: IRType, location: SourceLocation | None
    ) -> Register:
        return self.ssa.new_register(name, ir_type, location)

    def add_assignment(
        self, targets: list[Register], source: ValueProvider, loc: SourceLocation | None
    ) -> None:
        for target in targets:
            self.ssa.write_variable(target.name, self.block_builder.active_block, target)
        self.add_op(Assignment(targets=targets, source=source, source_location=loc))
        # also update any implicitly returned variables
        implicit_params = {p.name for p in self.subroutine.parameters if p.implicit_return}
        for target in targets:
            if target.name in implicit_params:
                self._update_implicit_out_var(target)

    def add_op(self, op: Op) -> None:
        self.block_builder.add(op)

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

    def _update_implicit_out_var(self, reg: Register) -> None:
        var = reg.name
        # emit conditional assignment equivalent to
        # if var%is_original:
        #   var%out = var
        loc = SourceLocation(file=None, line=1)

        if_body = self.block_builder.mkblock(loc, "if_body")
        next_block = self.block_builder.mkblock(loc, "after_if_else")

        condition_value = self.ssa.read_variable(
            get_implicit_return_is_original(var),
            PrimitiveIRType.bool,
            self.block_builder.active_block,
        )
        self.block_builder.terminate(
            ConditionalBranch(
                condition=condition_value,
                non_zero=if_body,
                zero=next_block,
                source_location=loc,
            )
        )
        self.block_builder.activate_block(if_body)

        assign(
            self,
            self.ssa.read_variable(var, reg.ir_type, if_body),
            name=get_implicit_return_out(var),
            assignment_location=loc,
        )
        self.block_builder.goto(next_block)
        self.block_builder.try_activate_block(next_block)
