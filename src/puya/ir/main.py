import contextlib
import itertools
import typing
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import algo_constants, log
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.serialize import awst_from_json
from puya.context import CompileContext
from puya.errors import CodeError, InternalError
from puya.ir import arc4_router
from puya.ir.arc4_router import extract_arc4_methods
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext
from puya.ir.destructure.main import destructure_ssa
from puya.ir.models import Contract, LogicSignature, ModuleArtifact, Parameter, Program, Subroutine
from puya.ir.optimize.context import IROptimizeContext
from puya.ir.optimize.dead_code_elimination import remove_unused_subroutines
from puya.ir.optimize.main import optimize_contract_ir
from puya.ir.to_text_visitor import output_artifact_ir_to_path
from puya.ir.types_ import wtype_to_ir_type, wtype_to_ir_types
from puya.ir.utils import format_tuple_index
from puya.ir.validation.main import validate_module_artifact
from puya.models import (
    ARC4Method,
    ARC4MethodConfig,
    ContractMetaData,
    ContractState,
    LogicSignatureMetaData,
    StateTotals,
)
from puya.parse import SourceLocation
from puya.utils import StableSet, attrs_extend, set_remove

logger = log.get_logger(__name__)


CalleesLookup: typing.TypeAlias = defaultdict[awst_nodes.Function, set[awst_nodes.Function]]
_EMBEDDED_LIB = Path(__file__).parent / "_puya_lib.awst.json"


class CompilationSetCollector(AWSTTraverser):
    def __init__(self, awst: awst_nodes.AWST, *, explicit_compilation_set: StableSet[str]) -> None:
        super().__init__()
        self._remaining_explicit_set: typing.Final = explicit_compilation_set
        self.compilation_set: typing.Final = dict[
            str, awst_nodes.ContractFragment | awst_nodes.LogicSignature
        ]()
        self._nodes_by_id: typing.Final = immutabledict[str, awst_nodes.RootNode](
            {n.id: n for n in awst}
        )

    @property
    def unresolved_explict_ids(self) -> Collection[str]:
        return self._remaining_explicit_set

    def visit_compiled_contract(self, compiled_contract: awst_nodes.CompiledContract) -> None:
        super().visit_compiled_contract(compiled_contract)
        node = self._nodes_by_id.get(compiled_contract.contract)
        match node:
            case awst_nodes.ContractFragment() as contract:
                self._visit_contract_or_lsig(contract, reference=True)
            case None:
                logger.error(
                    "unable to resolve contract reference",
                    location=compiled_contract.source_location,
                )
            case _:
                logger.error(
                    "reference is not a contract", location=compiled_contract.source_location
                )

    def visit_compiled_logicsig(self, compiled_lsig: awst_nodes.CompiledLogicSig) -> None:
        super().visit_compiled_logicsig(compiled_lsig)
        node = self._nodes_by_id.get(compiled_lsig.logic_sig)
        match node:
            case awst_nodes.LogicSignature() as lsig:
                self._visit_contract_or_lsig(lsig, reference=True)
            case None:
                logger.error(
                    "unable to resolve logic signature reference",
                    location=compiled_lsig.source_location,
                )
            case _:
                logger.error(
                    "reference is not a logic signature", location=compiled_lsig.source_location
                )

    def visit_contract_fragment(self, contract: awst_nodes.ContractFragment) -> None:
        return self._visit_contract_or_lsig(contract)

    def visit_logic_signature(self, lsig: awst_nodes.LogicSignature) -> None:
        return self._visit_contract_or_lsig(lsig)

    def _visit_contract_or_lsig(
        self,
        node: awst_nodes.ContractFragment | awst_nodes.LogicSignature,
        *,
        reference: bool = False,
    ) -> None:
        if node.id in self.compilation_set:
            return  # already visited
        direct = set_remove(self._remaining_explicit_set, node.id)
        if direct or reference:
            self.compilation_set[node.id] = node
            match node:
                case awst_nodes.ContractFragment():
                    super().visit_contract_fragment(node)
                case awst_nodes.LogicSignature():
                    super().visit_logic_signature(node)
                case unexpected:
                    typing.assert_never(unexpected)

    @classmethod
    def collect(
        cls, context: CompileContext, awst: awst_nodes.AWST
    ) -> Collection[awst_nodes.ContractFragment | awst_nodes.LogicSignature]:
        collector = cls(
            awst, explicit_compilation_set=StableSet.from_iter(context.compilation_set)
        )
        for node in awst:
            node.accept(collector)
        for unresolved_id in collector.unresolved_explict_ids:
            logger.error(f"unable to resolve compilation artifact '{unresolved_id}'")
        return collector.compilation_set.values()


def awst_to_ir(context: CompileContext, awst: awst_nodes.AWST) -> list[ModuleArtifact]:
    embedded_funcs_lookup = _build_embedded_ir(context)
    build_context: IRBuildContext = attrs_extend(
        IRBuildContext,
        context,
        subroutines={},
        awst=awst,
        embedded_funcs_lookup=embedded_funcs_lookup,
    )

    compilation_set = CompilationSetCollector.collect(context, awst)
    result = list[ModuleArtifact]()
    for node in compilation_set:
        match node:
            case awst_nodes.ContractFragment() as contract_node:
                ctx = build_context.for_root(contract_node)
                with ctx.log_exceptions():
                    contract_ir = _build_ir(ctx, contract_node)
                    result.append(contract_ir)
            case awst_nodes.LogicSignature() as logic_signature:
                ctx = build_context.for_root(logic_signature)
                with ctx.log_exceptions():
                    logic_sig_ir = _build_logic_sig_ir(ctx, logic_signature)
                    result.append(logic_sig_ir)
            case unexpected:
                typing.assert_never(unexpected)
    return result


def optimize_and_destructure_ir(
    context: IROptimizeContext, artifact_ir: ModuleArtifact, artifact_ir_base_path: Path | None
) -> ModuleArtifact:
    remove_unused_subroutines(context, artifact_ir)
    if artifact_ir_base_path and context.options.output_ssa_ir:
        output_artifact_ir_to_path(artifact_ir, artifact_ir_base_path.with_suffix(".ssa.ir"))
    logger.info(
        f"optimizing {artifact_ir.metadata.ref} at level {context.options.optimization_level}"
    )
    artifact_ir = optimize_contract_ir(
        context,
        artifact_ir,
        artifact_ir_base_path if context.options.output_optimization_ir else None,
    )
    artifact_ir = destructure_ssa(context, artifact_ir)
    if artifact_ir_base_path and context.options.output_destructured_ir:
        output_artifact_ir_to_path(
            artifact_ir, artifact_ir_base_path.with_suffix(".destructured.ir")
        )
    # validation is run as the last step, in case we've accidentally inserted something,
    # and in particular post subroutine removal, because some things that are "linked"
    # are not necessarily used from the current artifact
    validate_module_artifact(context, artifact_ir)
    return artifact_ir


def _build_embedded_ir(ctx: CompileContext) -> Mapping[str, Subroutine]:
    embedded_funcs = [
        n
        for n in awst_from_json(_EMBEDDED_LIB.read_text())
        if isinstance(n, awst_nodes.Subroutine)
    ]
    embedded_funcs_lookup = dict[str, Subroutine]()
    embedded_ctx: IRBuildContext = attrs_extend(
        IRBuildContext,
        ctx,
        subroutines={},
        awst=embedded_funcs,
    )
    for func in embedded_funcs:
        sub = _make_subroutine(func, allow_implicits=False)
        embedded_ctx.subroutines[func] = sub
        embedded_funcs_lookup[func.id] = sub

    for func in embedded_funcs:
        sub = embedded_ctx.subroutines[func]
        FunctionIRBuilder.build_body(embedded_ctx, function=func, subroutine=sub, on_create=None)
    return embedded_funcs_lookup


def _build_ir(ctx: IRBuildContext, contract: awst_nodes.ContractFragment) -> Contract:
    folded, arc4_method_data = _fold_state_and_special_methods(ctx, contract)
    if not (folded.approval_program and folded.clear_program):
        raise CodeError(
            "approval and clear-state programs must be implemented", contract.source_location
        )
    arc4_router_func = arc4_router.create_abi_router(contract, arc4_method_data)
    ctx.subroutines[arc4_router_func] = ctx.routers[contract.id] = _make_subroutine(
        arc4_router_func, allow_implicits=False
    )

    # visit call graph starting at entry point(s) to collect all references for each
    callees = CalleesLookup(set)
    approval_subs_srefs = StableSet[awst_nodes.Function]()
    approval_subs_srefs.add(arc4_router_func)
    approval_subs_srefs |= SubroutineCollector.collect(
        ctx, start=arc4_router_func, callees=callees
    )
    approval_subs_srefs |= SubroutineCollector.collect(
        ctx, start=folded.approval_program, callees=callees
    )
    clear_subs_srefs = SubroutineCollector.collect(
        ctx, start=folded.clear_program, callees=callees
    )
    if folded.init:
        approval_subs_srefs.add(folded.init)
        init_sub_srefs = SubroutineCollector.collect(ctx, start=folded.init, callees=callees)
        approval_subs_srefs |= init_sub_srefs
    # construct unique Subroutine objects for each function
    # that was referenced through either entry point
    for func in itertools.chain(approval_subs_srefs, clear_subs_srefs):
        if func not in ctx.subroutines:
            allow_implicits = _should_include_implicit_returns(
                func, callees=callees[func], arc4_router_func=arc4_router_func
            )
            # make the emtpy subroutine, because functions reference other functions
            ctx.subroutines[func] = _make_subroutine(func, allow_implicits=allow_implicits)
    # now construct the subroutine IR
    for func, sub in ctx.subroutines.items():
        if not sub.body:  # in case something is pre-built (ie from embedded lib)
            FunctionIRBuilder.build_body(ctx, function=func, subroutine=sub, on_create=None)

    approval_ir = _make_program(
        ctx,
        folded.approval_program,
        StableSet(
            *(ctx.subroutines[ref] for ref in approval_subs_srefs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        program_id=".".join((contract.id, folded.approval_program.short_name)),
        on_create=folded.init,
    )
    clear_state_ir = _make_program(
        ctx,
        folded.clear_program,
        StableSet(
            *(ctx.subroutines[ref] for ref in clear_subs_srefs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        program_id=".".join((contract.id, folded.clear_program.short_name)),
        on_create=None,
    )
    result = Contract(
        source_location=contract.source_location,
        approval_program=approval_ir,
        clear_program=clear_state_ir,
        metadata=ContractMetaData(
            description=contract.docstring,
            name=contract.name,
            ref=contract.id,
            arc4_methods=folded.arc4_methods,
            global_state=immutabledict(folded.global_state),
            local_state=immutabledict(folded.local_state),
            state_totals=folded.build_state_totals(location=contract.source_location),
        ),
    )
    return result


def _build_logic_sig_ir(
    ctx: IRBuildContext, logic_sig: awst_nodes.LogicSignature
) -> LogicSignature:
    # visit call graph starting at entry point(s) to collect all references for each
    callees = CalleesLookup(set)
    program_sub_refs = SubroutineCollector.collect(ctx, start=logic_sig.program, callees=callees)

    # construct unique Subroutine objects for each function
    # that was referenced through either entry point
    for func in program_sub_refs:
        if func not in ctx.subroutines:
            # make the emtpy subroutine, because functions reference other functions
            ctx.subroutines[func] = _make_subroutine(func, allow_implicits=True)
    # now construct the subroutine IR
    for func, sub in ctx.subroutines.items():
        if not sub.body:  # in case something is pre-built (ie from embedded lib)
            FunctionIRBuilder.build_body(ctx, function=func, subroutine=sub, on_create=None)

    sig_ir = _make_program(
        ctx,
        logic_sig.program,
        StableSet(
            *(ctx.subroutines[ref] for ref in program_sub_refs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        program_id=logic_sig.id,
        on_create=None,
    )
    result = LogicSignature(
        source_location=logic_sig.source_location,
        program=sig_ir,
        metadata=LogicSignatureMetaData(
            ref=logic_sig.id,
            description=logic_sig.docstring,
            name=logic_sig.short_name,
        ),
    )
    return result


def _expand_tuple_parameters(
    name: str, typ: wtypes.WType, *, allow_implicits: bool, source_location: SourceLocation | None
) -> Iterator[Parameter]:
    if isinstance(typ, wtypes.WTuple):
        for item_idx, item_type in enumerate(typ.types):
            item_name = format_tuple_index(name, item_idx)
            yield from _expand_tuple_parameters(
                item_name,
                item_type,
                allow_implicits=allow_implicits,
                source_location=source_location,
            )
    else:
        yield Parameter(
            name=name,
            ir_type=wtype_to_ir_type(typ),
            version=0,
            implicit_return=allow_implicits and not typ.immutable,
            source_location=source_location,
        )


def _should_include_implicit_returns(
    func: awst_nodes.Function,
    callees: set[awst_nodes.Function],
    arc4_router_func: awst_nodes.Function,
) -> bool:
    """
    Determine if a function should implicitly return mutable reference parameters.

    ABI methods which are only called by the ABI router in the approval_program do not need to
    implicitly return anything as we know our router is not interested in anything but the explicit
    return value.

    Anything else would require further analysis, so err on the side of caution and include
    the implicit returns.
    """
    if isinstance(func, awst_nodes.ContractMethod) and func.arc4_method_config:
        return bool(callees - {arc4_router_func})
    return True


def _make_subroutine(func: awst_nodes.Function, *, allow_implicits: bool) -> Subroutine:
    """Pre-construct subroutine with an empty body"""
    parameters = [
        param
        for arg in func.args
        for param in _expand_tuple_parameters(
            arg.name,
            arg.wtype,
            allow_implicits=allow_implicits,
            source_location=arg.source_location,
        )
    ]
    returns = wtype_to_ir_types(func.return_type)
    return Subroutine(
        full_name=func.full_name,
        short_name=func.short_name,
        parameters=parameters,
        returns=returns,
        body=[],
        source_location=func.source_location,
    )


def _make_program(
    ctx: IRBuildContext,
    main: awst_nodes.Function,
    references: Iterable[Subroutine],
    *,
    program_id: str,
    on_create: awst_nodes.Function | None,
) -> Program:
    if main.args:
        raise InternalError("main method should not have args")
    return_type = wtype_to_ir_type(main.return_type)
    if return_type.avm_type != AVMType.uint64:
        raise InternalError("main method should return uint64 backed type")
    main_sub = Subroutine(
        full_name=main.full_name,
        short_name=main.short_name,
        parameters=[],
        returns=[return_type],
        body=[],
        source_location=main.source_location,
    )
    on_create_sub: Subroutine | None = None
    if on_create is not None:
        on_create_sub = ctx.subroutines[on_create]
    FunctionIRBuilder.build_body(ctx, function=main, subroutine=main_sub, on_create=on_create_sub)
    return Program(
        id=program_id,
        main=main_sub,
        subroutines=tuple(references),
    )


@attrs.define(kw_only=True)
class FoldedContract:
    init: awst_nodes.ContractMethod | None = None
    approval_program: awst_nodes.ContractMethod | None = None
    clear_program: awst_nodes.ContractMethod | None = None
    global_state: dict[str, ContractState] = attrs.field(factory=dict)
    local_state: dict[str, ContractState] = attrs.field(factory=dict)
    arc4_methods: list[ARC4Method] = attrs.field(factory=list)
    declared_totals: awst_nodes.StateTotals | None

    def build_state_totals(self, *, location: SourceLocation) -> StateTotals:
        global_by_type = Counter(s.storage_type for s in self.global_state.values())
        local_by_type = Counter(s.storage_type for s in self.local_state.values())
        merged = StateTotals(
            global_uints=global_by_type[AVMType.uint64],
            global_bytes=global_by_type[AVMType.bytes],
            local_uints=local_by_type[AVMType.uint64],
            local_bytes=local_by_type[AVMType.bytes],
        )
        if self.declared_totals is not None:
            insufficient_fields = []
            declared_dict = attrs.asdict(self.declared_totals, filter=attrs.filters.include(int))
            for field, declared in declared_dict.items():
                calculated = getattr(merged, field)
                if declared < calculated:
                    insufficient_fields.append(f"{field}: {declared=}, {calculated=}")
                merged = attrs.evolve(merged, **{field: declared})
            if insufficient_fields:
                logger.warning(
                    f"State totals declared on the class are less than totals calculated from"
                    f" explicitly declared properties: {', '.join(sorted(insufficient_fields))}.",
                    location=location,
                )
        global_total = merged.global_uints + merged.global_bytes
        local_total = merged.local_uints + merged.local_bytes
        if global_total > algo_constants.MAX_GLOBAL_STATE_KEYS:
            logger.warning(
                f"Total global state key count of {global_total}"
                f" exceeds consensus parameter value {algo_constants.MAX_GLOBAL_STATE_KEYS}",
                location=location,
            )
        if local_total > algo_constants.MAX_LOCAL_STATE_KEYS:
            logger.warning(
                f"Total local state key count of {local_total}"
                f" exceeds consensus parameter value {algo_constants.MAX_LOCAL_STATE_KEYS}",
                location=location,
            )
        return merged


def _gather_arc4_methods(
    ctx: IRBuildContext, contract: awst_nodes.ContractFragment
) -> dict[awst_nodes.ContractMethod, ARC4MethodConfig]:
    bases = [ctx.resolve_contract_reference(cref) for cref in contract.bases]
    maybe_arc4_method_refs = dict[str, tuple[awst_nodes.ContractMethod, ARC4MethodConfig] | None]()
    for c in [contract, *bases]:
        for cm in c.subroutines:
            if (c is contract) or cm.inheritable:
                if cm.arc4_method_config:
                    maybe_arc4_method_refs.setdefault(cm.member_name, (cm, cm.arc4_method_config))
                else:
                    maybe_arc4_method_refs.setdefault(cm.member_name, None)
    arc4_method_refs = dict(filter(None, maybe_arc4_method_refs.values()))
    return arc4_method_refs


def _fold_state_and_special_methods(
    ctx: IRBuildContext, contract: awst_nodes.ContractFragment
) -> tuple[FoldedContract, dict[awst_nodes.ContractMethod, ARC4MethodConfig]]:
    bases = [ctx.resolve_contract_reference(cref) for cref in contract.bases]
    if contract.state_totals is None:
        base_with_defined = next((b for b in bases if b.state_totals is not None), None)
        if base_with_defined:
            logger.warning(
                f"Contract {contract.name} extends base contract {base_with_defined.name} "
                "with explicit state_totals, but does not define its own state_totals. "
                "This could result in insufficient reserved state at run time.",
                location=contract.source_location,
            )
    result = FoldedContract(
        declared_totals=contract.state_totals,
        init=contract.init,
        approval_program=contract.approval_program,
        clear_program=contract.clear_program,
    )
    for c in [contract, *bases]:
        if result.init is None:  # noqa: SIM102
            if c.init and c.init.inheritable:
                result.init = c.init
        if result.approval_program is None:  # noqa: SIM102
            if c.approval_program and c.approval_program.inheritable:
                result.approval_program = c.approval_program
        if result.clear_program is None:  # noqa: SIM102
            if c.clear_program and c.clear_program.inheritable:
                result.clear_program = c.clear_program
        for state in c.app_state.values():
            storage_type = wtypes.persistable_stack_type(
                state.storage_wtype, state.source_location
            )
            key_type = None
            if state.key_wtype is not None:
                key_type = wtypes.persistable_stack_type(state.key_wtype, state.source_location)
            match state.kind:
                case awst_nodes.AppStorageKind.app_global:
                    if key_type is not None:
                        raise InternalError(
                            f"maps of {state.kind} are not supported yet", state.source_location
                        )
                    translated = ContractState(
                        name=state.member_name,
                        source_location=state.source_location,
                        key=state.key.value,  # TODO: pass encoding?
                        storage_type=storage_type,
                        description=state.description,
                    )
                    result.global_state[translated.name] = translated
                case awst_nodes.AppStorageKind.account_local:
                    if key_type is not None:
                        raise InternalError(
                            f"maps of {state.kind} are not supported yet", state.source_location
                        )
                    translated = ContractState(
                        name=state.member_name,
                        source_location=state.source_location,
                        key=state.key.value,  # TODO: pass encoding?
                        storage_type=storage_type,
                        description=state.description,
                    )
                    result.local_state[translated.name] = translated
                case awst_nodes.AppStorageKind.box:
                    pass  # TODO: forward these on
                case _:
                    typing.assert_never(state.kind)
    arc4_method_refs = _gather_arc4_methods(ctx, contract)
    if arc4_method_refs:
        result.arc4_methods = extract_arc4_methods(
            arc4_method_refs,
            local_state=result.local_state,
            global_state=result.global_state,
        )
    return result, arc4_method_refs


class SubroutineCollector(FunctionTraverser):
    def __init__(self, context: IRBuildContext, callees: CalleesLookup) -> None:
        self.context = context
        self.result = StableSet[awst_nodes.Function]()
        self.callees = callees
        self._func_stack = list[awst_nodes.Function]()

    @classmethod
    def collect(
        cls, context: IRBuildContext, start: awst_nodes.Function, callees: CalleesLookup
    ) -> StableSet[awst_nodes.Function]:
        collector = cls(context, callees)
        with collector._enter_func(start):  # noqa: SLF001
            start.body.accept(collector)
        return collector.result

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        callee = self._func_stack[-1]
        func = self.context.resolve_function_reference(
            expr.target, expr.source_location, caller=callee
        )
        self.callees[func].add(callee)
        if func not in self.result:
            self.result.add(func)
            with self._enter_func(func):
                func.body.accept(self)

    @contextlib.contextmanager
    def _enter_func(self, func: awst_nodes.Function) -> Iterator[None]:
        self._func_stack.append(func)
        try:
            yield
        finally:
            self._func_stack.pop()
