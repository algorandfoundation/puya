import contextlib
import itertools
import typing
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import algo_constants, log
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.function_traverser import FunctionTraverser
from puya.context import CompileContext
from puya.errors import CodeError, InternalError
from puya.ir.arc4_router import create_abi_router, create_default_clear_state
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext, IRBuildContextWithFallback
from puya.ir.destructure.main import destructure_ssa
from puya.ir.models import (
    Contract,
    LogicSignature,
    ModuleArtifact,
    Parameter,
    Program,
    Subroutine,
)
from puya.ir.optimize.dead_code_elimination import remove_unused_subroutines
from puya.ir.optimize.main import optimize_contract_ir
from puya.ir.to_text_visitor import output_artifact_ir_to_path
from puya.ir.types_ import wtype_to_avm_type, wtype_to_ir_type, wtype_to_ir_types
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
from puya.parse import EMBEDDED_MODULES, SourceLocation
from puya.utils import StableSet, attrs_extend

logger = log.get_logger(__name__)


CalleesLookup: typing.TypeAlias = defaultdict[awst_nodes.Function, set[awst_nodes.Function]]


def build_module_irs(
    context: CompileContext, module_asts: dict[str, awst_nodes.Module]
) -> dict[str, list[ModuleArtifact]]:
    embedded_funcs = [
        func
        for embedded_module_name in EMBEDDED_MODULES
        for func in module_asts[embedded_module_name].body
        if isinstance(func, awst_nodes.Function)
    ]
    build_context: IRBuildContext = attrs_extend(
        IRBuildContext,
        context,
        subroutines={},
        module_awsts=module_asts,
        embedded_funcs=embedded_funcs,
    )
    _build_embedded_ir(build_context)

    result = {}
    for source in context.parse_result.sources:
        artifacts = result[source.module_name] = list[ModuleArtifact]()
        concrete_contract_nodes = [
            node
            for node in module_asts[source.module_name].body
            if isinstance(node, awst_nodes.ContractFragment) and not node.is_abstract
        ]
        for contract_node in concrete_contract_nodes:
            ctx = build_context.for_contract(contract_node)
            with ctx.log_exceptions():
                contract_ir = _build_ir(ctx, contract_node)
                artifacts.append(contract_ir)

        logic_signature_nodes = [
            node
            for node in module_asts[source.module_name].body
            if isinstance(node, awst_nodes.LogicSignature)
        ]
        for logic_signature in logic_signature_nodes:
            ctx = build_context.for_logic_signature(logic_signature)
            with ctx.log_exceptions():
                logic_sig_ir = _build_logic_sig_ir(ctx, logic_signature)
                artifacts.append(logic_sig_ir)
    return result


def optimize_and_destructure_ir(
    context: CompileContext, artifact_ir: ModuleArtifact, artifact_ir_base_path: Path
) -> ModuleArtifact:
    remove_unused_subroutines(context, artifact_ir)
    if context.options.output_ssa_ir:
        output_artifact_ir_to_path(artifact_ir, artifact_ir_base_path.with_suffix(".ssa.ir"))
    logger.info(
        f"Optimizing {artifact_ir.metadata.full_name} "
        f"at level {context.options.optimization_level}"
    )
    artifact_ir = optimize_contract_ir(
        context,
        artifact_ir,
        artifact_ir_base_path if context.options.output_optimization_ir else None,
    )
    artifact_ir = destructure_ssa(context, artifact_ir)
    if context.options.output_destructured_ir:
        output_artifact_ir_to_path(
            artifact_ir, artifact_ir_base_path.with_suffix(".destructured.ir")
        )
    # validation is run as the last step, in case we've accidentally inserted something,
    # and in particular post subroutine removal, because some things that are "linked"
    # are not necessarily used from the current artifact
    validate_module_artifact(context, artifact_ir)
    return artifact_ir


def _build_embedded_ir(ctx: IRBuildContext) -> None:
    for func in ctx.embedded_funcs:
        ctx.subroutines[func] = _make_subroutine(func, allow_implicits=False)

    for func in ctx.embedded_funcs:
        sub = ctx.subroutines[func]
        FunctionIRBuilder.build_body(ctx, function=func, subroutine=sub, on_create=None)


def _build_ir(ctx: IRBuildContextWithFallback, contract: awst_nodes.ContractFragment) -> Contract:
    if contract.is_abstract:
        raise InternalError("attempted to compile abstract contract")
    folded = fold_state_and_special_methods(ctx, contract)
    if not (folded.approval_program and folded.clear_program):
        raise InternalError(
            "contract is non abstract but doesn't have approval and clear programs in hierarchy",
            contract.source_location,
        )
    # visit call graph starting at entry point(s) to collect all references for each
    callees = CalleesLookup(set)
    approval_subs_srefs = SubroutineCollector.collect(
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
                func, callees=callees[func], approval_program=folded.approval_program
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
        StableSet(*approval_subs_srefs, *ctx.embedded_funcs),
        on_create=folded.init,
    )
    clear_state_ir = _make_program(
        ctx,
        folded.clear_program,
        StableSet(*clear_subs_srefs, *ctx.embedded_funcs),
        on_create=None,
    )
    result = Contract(
        source_location=contract.source_location,
        approval_program=approval_ir,
        clear_program=clear_state_ir,
        metadata=ContractMetaData(
            description=contract.docstring,
            name_override=contract.name_override,
            module_name=contract.module_name,
            class_name=contract.name,
            arc4_methods=folded.arc4_methods,
            global_state=immutabledict(folded.global_state),
            local_state=immutabledict(folded.local_state),
            state_totals=folded.build_state_totals(location=contract.source_location),
        ),
    )
    return result


def _build_logic_sig_ir(
    ctx: IRBuildContextWithFallback, logic_sig: awst_nodes.LogicSignature
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
        StableSet(*program_sub_refs, *ctx.embedded_funcs),
        on_create=None,
    )
    result = LogicSignature(
        source_location=logic_sig.source_location,
        program=sig_ir,
        metadata=LogicSignatureMetaData(
            module_name=logic_sig.module_name,
            name=logic_sig.name,
            description=logic_sig.program.docstring,
        ),
    )
    return result


def _build_parameter_list(
    args: Sequence[awst_nodes.SubroutineArgument], *, allow_implicits: bool
) -> Iterator[Parameter]:
    for arg in args:
        if isinstance(arg.wtype, wtypes.WTuple):
            for tup_idx, tup_type in enumerate(arg.wtype.types):
                yield Parameter(
                    source_location=arg.source_location,
                    version=0,
                    name=format_tuple_index(arg.name, tup_idx),
                    ir_type=wtype_to_ir_type(tup_type),
                    implicit_return=allow_implicits and not tup_type.immutable,
                )
        else:
            yield (
                Parameter(
                    source_location=arg.source_location,
                    version=0,
                    name=arg.name,
                    ir_type=wtype_to_ir_type(arg.wtype),
                    implicit_return=allow_implicits and not arg.wtype.immutable,
                )
            )


def _should_include_implicit_returns(
    func: awst_nodes.Function,
    callees: set[awst_nodes.Function],
    approval_program: awst_nodes.Function,
) -> bool:
    """
    Determine if a function should implicitly return mutable reference parameters.

    ABI methods which are only called by the ABI router in the approval_program do not need to
    implicitly return anything as we know our router is not interested in anything but the explicit
    return value.

    Anything else would require further analysis, so err on the side of caution and include
    the implicit returns.
    """
    if isinstance(func, awst_nodes.ContractMethod) and func.abimethod_config:
        return bool(callees - {approval_program})
    return True


def _make_subroutine(func: awst_nodes.Function, *, allow_implicits: bool) -> Subroutine:
    """Pre-construct subroutine with an empty body"""

    parameters = list(_build_parameter_list(func.args, allow_implicits=allow_implicits))

    returns = wtype_to_ir_types(func.return_type)

    return Subroutine(
        source_location=func.source_location,
        module_name=func.module_name,
        class_name=func.class_name if isinstance(func, awst_nodes.ContractMethod) else None,
        method_name=func.name,
        parameters=parameters,
        returns=returns,
        body=[],
    )


def _make_program(
    ctx: IRBuildContext,
    main: awst_nodes.Function,
    references: Iterable[awst_nodes.Function],
    on_create: awst_nodes.Function | None,
) -> Program:
    if main.args:
        raise InternalError("main method should not have args")
    return_type = wtype_to_ir_type(main.return_type)
    if return_type.avm_type != AVMType.uint64:
        raise InternalError("main method should return uint64 backed type")
    main_sub = Subroutine(
        source_location=main.source_location,
        module_name=main.module_name,
        class_name=main.class_name if isinstance(main, awst_nodes.ContractMethod) else None,
        method_name=main.name,
        parameters=[],
        returns=[return_type],
        body=[],
    )
    on_create_sub: Subroutine | None = None
    if on_create is not None:
        on_create_sub = ctx.subroutines[on_create]
    FunctionIRBuilder.build_body(ctx, function=main, subroutine=main_sub, on_create=on_create_sub)
    return Program(
        main=main_sub,
        subroutines=[ctx.subroutines[ref] for ref in references],
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


def fold_state_and_special_methods(
    ctx: IRBuildContext, contract: awst_nodes.ContractFragment
) -> FoldedContract:
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
    result = FoldedContract(declared_totals=contract.state_totals)
    maybe_arc4_method_refs = dict[str, tuple[awst_nodes.ContractMethod, ARC4MethodConfig] | None]()
    for c in [contract, *bases]:
        if result.init is None:
            result.init = c.init
        if result.approval_program is None:
            result.approval_program = c.approval_program
        if result.clear_program is None:
            result.clear_program = c.clear_program
        for state in c.app_state.values():
            match state.kind:
                case awst_nodes.AppStorageKind.app_global:
                    if state.key_wtype is not None:
                        raise InternalError(
                            f"maps of {state.kind} are not supported yet", state.source_location
                        )
                    translated = ContractState(
                        name=state.member_name,
                        source_location=state.source_location,
                        key=state.key.value,  # TODO: pass encoding?
                        storage_type=wtype_to_avm_type(state.storage_wtype),
                        description=state.description,
                    )
                    result.global_state[translated.name] = translated
                case awst_nodes.AppStorageKind.account_local:
                    if state.key_wtype is not None:
                        raise InternalError(
                            f"maps of {state.kind} are not supported yet", state.source_location
                        )
                    translated = ContractState(
                        name=state.member_name,
                        source_location=state.source_location,
                        key=state.key.value,  # TODO: pass encoding?
                        storage_type=wtype_to_avm_type(state.storage_wtype),
                        description=state.description,
                    )
                    result.local_state[translated.name] = translated
                case awst_nodes.AppStorageKind.box:
                    pass  # TODO: forward these on
                case _:
                    typing.assert_never(state.kind)
        for cm in c.subroutines:
            if cm.abimethod_config:
                maybe_arc4_method_refs.setdefault(cm.name, (cm, cm.abimethod_config))
            else:
                maybe_arc4_method_refs.setdefault(cm.name, None)
    if not (c.init and c.init.body.body):
        result.init = None
    arc4_method_refs = dict(filter(None, maybe_arc4_method_refs.values()))
    if arc4_method_refs and not contract.is_arc4:
        raise InternalError(
            "Contracts making use of the @abimethod decorator "
            "should extend the ARC4Contract class",
            contract.source_location,
        )
    if contract.is_arc4:
        if result.approval_program:
            raise CodeError(
                "approval_program should not be defined for ARC4 contracts",
                contract.source_location,
            )
        result.approval_program, result.arc4_methods = create_abi_router(
            contract,
            arc4_method_refs,
            local_state=result.local_state,
            global_state=result.global_state,
        )
        if not result.clear_program:
            result.clear_program = create_default_clear_state(contract)
    return result


class SubroutineCollector(FunctionTraverser):
    def __init__(self, context: IRBuildContext, callees: CalleesLookup) -> None:
        self.context = context
        self.result = StableSet[awst_nodes.Function]()
        self.callees = callees
        self._func_stack = list[awst_nodes.Function]()

    @classmethod
    def collect(
        cls,
        context: IRBuildContext,
        start: awst_nodes.Function,
        callees: CalleesLookup,
    ) -> StableSet[awst_nodes.Function]:
        collector = cls(context, callees)
        with collector._enter_func(start):  # noqa: SLF001
            start.body.accept(collector)
        return collector.result

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        func = self.context.resolve_function_reference(expr.target, expr.source_location)
        callee = self._func_stack[-1]
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
