import contextlib
import itertools
import typing
from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping
from copy import deepcopy
from pathlib import Path

from immutabledict import immutabledict

from puya import artifact_metadata, log, program_refs
from puya.artifact_metadata import ContractMetaData, LogicSignatureMetaData
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
)
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.serialize import awst_from_json
from puya.context import ArtifactCompileContext, CompileContext
from puya.errors import InternalError
from puya.ir import arc4_router
from puya.ir._contract_metadata import build_contract_metadata
from puya.ir._utils import make_subroutine
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext
from puya.ir.destructure.main import destructure_ssa
from puya.ir.models import Contract, LogicSignature, ModuleArtifact, Program, Subroutine
from puya.ir.optimize.dead_code_elimination import remove_unused_subroutines
from puya.ir.optimize.main import optimize_program_ir
from puya.ir.to_text_visitor import render_program
from puya.ir.types_ import wtype_to_ir_type
from puya.ir.validation.main import validate_module_artifact
from puya.program_refs import ProgramKind
from puya.utils import StableSet, attrs_extend, coalesce, set_remove

logger = log.get_logger(__name__)


CalleesLookup: typing.TypeAlias = defaultdict[awst_nodes.Function, set[awst_nodes.Function]]
_EMBEDDED_LIB = Path(__file__).parent / "_puya_lib.awst.json"


class CompilationSetCollector(AWSTTraverser):
    def __init__(self, awst: awst_nodes.AWST, *, explicit_compilation_set: StableSet[str]) -> None:
        super().__init__()
        self._remaining_explicit_set: typing.Final = explicit_compilation_set
        self.compilation_set: typing.Final = dict[
            str, awst_nodes.Contract | awst_nodes.LogicSignature
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
            case awst_nodes.Contract() as contract:
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

    def visit_contract(self, contract: awst_nodes.Contract) -> None:
        return self._visit_contract_or_lsig(contract)

    def visit_logic_signature(self, lsig: awst_nodes.LogicSignature) -> None:
        return self._visit_contract_or_lsig(lsig)

    def _visit_contract_or_lsig(
        self,
        node: awst_nodes.Contract | awst_nodes.LogicSignature,
        *,
        reference: bool = False,
    ) -> None:
        if node.id in self.compilation_set:
            return  # already visited
        direct = set_remove(self._remaining_explicit_set, node.id)
        if direct or reference:
            self.compilation_set[node.id] = node
            match node:
                case awst_nodes.Contract():
                    super().visit_contract(node)
                case awst_nodes.LogicSignature():
                    super().visit_logic_signature(node)
                case unexpected:
                    typing.assert_never(unexpected)

    @classmethod
    def collect(
        cls, context: CompileContext, awst: awst_nodes.AWST
    ) -> Collection[awst_nodes.Contract | awst_nodes.LogicSignature]:
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
        ctx = build_context.for_root(node)
        with ctx.log_exceptions():
            ir: ModuleArtifact
            if isinstance(node, awst_nodes.Contract):
                ir = _build_contract_ir(ctx, node)
            else:
                ir = _build_logic_sig_ir(ctx, node)
            result.append(ir)
    return result


def optimize_and_destructure_ir(
    context: ArtifactCompileContext, artifact_ir: ModuleArtifact
) -> ModuleArtifact:
    match artifact_ir:
        case Contract() as contract_ir:
            contract_ir.approval_program = _optimize_and_destructure_program_ir(
                context, contract_ir.metadata, contract_ir.approval_program
            )
            contract_ir.clear_program = _optimize_and_destructure_program_ir(
                context, contract_ir.metadata, contract_ir.clear_program
            )
        case LogicSignature() as lsig_ir:
            lsig_ir.program = _optimize_and_destructure_program_ir(
                context, lsig_ir.metadata, lsig_ir.program
            )
        case unexpected:
            typing.assert_never(unexpected)
    # validation is run as the last step, in case we've accidentally inserted something,
    # and in particular post subroutine removal, because some things that are "linked"
    # are not necessarily used from the current artifact
    validate_module_artifact(context, artifact_ir)
    return artifact_ir


def _optimize_and_destructure_program_ir(
    context: ArtifactCompileContext,
    metadata: ContractMetaData | LogicSignatureMetaData,
    program: Program,
) -> Program:
    ref = metadata.ref
    if context.options.output_ssa_ir:
        render_program(context, program, qualifier="ssa")
    logger.info(
        f"optimizing {program.kind} program of {ref} at level {context.options.optimization_level}"
    )
    routable_method_ids = None
    if isinstance(metadata, ContractMetaData) and program.kind is ProgramKind.approval:
        routable_method_ids = {a4m.id for a4m in metadata.arc4_methods}
    program = deepcopy(program)
    optimize_program_ir(context, program, routable_method_ids=routable_method_ids)
    destructure_ssa(context, program)
    if context.options.output_destructured_ir:
        render_program(context, program, qualifier="destructured")

    return program


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
        sub = make_subroutine(func, allow_implicits=False)
        embedded_ctx.subroutines[func] = sub
        embedded_funcs_lookup[func.id] = sub

    for func in embedded_funcs:
        sub = embedded_ctx.subroutines[func]
        FunctionIRBuilder.build_body(embedded_ctx, function=func, subroutine=sub)
    return embedded_funcs_lookup


def _build_contract_ir(ctx: IRBuildContext, contract: awst_nodes.Contract) -> Contract:
    metadata, arc4_method_data = build_contract_metadata(ctx, contract)
    arc4_router_func = arc4_router.create_abi_router(contract, arc4_method_data)
    ctx.routers[contract.id] = arc4_router_ir = make_subroutine(
        arc4_router_func, allow_implicits=False
    )

    # visit call graph starting at entry point(s) to collect all references for each
    callees = CalleesLookup(set)
    approval_subs_srefs = SubroutineCollector.collect(
        ctx, start=contract.approval_program, callees=callees, arc4_router_func=arc4_router_func
    )
    clear_subs_srefs = SubroutineCollector.collect(
        ctx, start=contract.clear_program, callees=callees, arc4_router_func=arc4_router_func
    )

    # construct unique Subroutine objects for each function
    # that was referenced through either entry point
    for func in itertools.chain(approval_subs_srefs, clear_subs_srefs):
        if func not in ctx.subroutines:
            # insert the generated router function only if it's referenced,
            # this is to prevent compilation errors if it's not and there are arc4 methods
            # that aren't used otherwise
            if func is arc4_router_func:
                func_ir = arc4_router_ir
            else:
                allow_implicits = _should_include_implicit_returns(
                    func, callees=callees[func], arc4_router_func=arc4_router_func
                )
                # make the emtpy subroutine, because functions reference other functions
                func_ir = make_subroutine(func, allow_implicits=allow_implicits)
            ctx.subroutines[func] = func_ir

    # now construct the subroutine IR
    for func, sub in ctx.subroutines.items():
        if not sub.body:  # in case something is pre-built (ie from embedded lib)
            FunctionIRBuilder.build_body(ctx, function=func, subroutine=sub)

    avm_version = coalesce(contract.avm_version, ctx.options.target_avm_version)
    approval_ir = _make_program(
        ctx,
        contract.approval_program,
        StableSet(
            *(ctx.subroutines[ref] for ref in approval_subs_srefs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        ref=program_refs.ContractProgramReference(
            reference=contract.id,
            program_name=contract.approval_program.short_name,
            kind=program_refs.ProgramKind.approval,
        ),
        avm_version=avm_version,
    )
    clear_state_ir = _make_program(
        ctx,
        contract.clear_program,
        StableSet(
            *(ctx.subroutines[ref] for ref in clear_subs_srefs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        ref=program_refs.ContractProgramReference(
            reference=contract.id,
            program_name=contract.clear_program.short_name,
            kind=program_refs.ProgramKind.clear_state,
        ),
        avm_version=avm_version,
    )
    result = Contract(
        source_location=contract.source_location,
        approval_program=approval_ir,
        clear_program=clear_state_ir,
        metadata=metadata,
    )
    return result


def _build_logic_sig_ir(
    ctx: IRBuildContext, logic_sig: awst_nodes.LogicSignature
) -> LogicSignature:
    # visit call graph starting at entry point(s) to collect all references for each
    callees = CalleesLookup(set)
    program_sub_refs = SubroutineCollector.collect(
        ctx, start=logic_sig.program, callees=callees, arc4_router_func=None
    )

    # construct unique Subroutine objects for each function
    # that was referenced through either entry point
    for func in program_sub_refs:
        if func not in ctx.subroutines:
            # make the emtpy subroutine, because functions reference other functions
            ctx.subroutines[func] = make_subroutine(func, allow_implicits=True)
    # now construct the subroutine IR
    for func, sub in ctx.subroutines.items():
        if not sub.body:  # in case something is pre-built (ie from embedded lib)
            FunctionIRBuilder.build_body(ctx, function=func, subroutine=sub)

    sig_ir = _make_program(
        ctx,
        logic_sig.program,
        StableSet(
            *(ctx.subroutines[ref] for ref in program_sub_refs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        ref=program_refs.LogicSigProgramReference(reference=logic_sig.id),
        avm_version=coalesce(logic_sig.avm_version, ctx.options.target_avm_version),
    )
    result = LogicSignature(
        source_location=logic_sig.source_location,
        program=sig_ir,
        metadata=artifact_metadata.LogicSignatureMetaData(
            ref=logic_sig.id,
            description=logic_sig.docstring,
            name=logic_sig.short_name,
        ),
    )
    return result


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


def _make_program(
    ctx: IRBuildContext,
    main: awst_nodes.Function,
    references: Iterable[Subroutine],
    *,
    ref: program_refs.ProgramReference,
    avm_version: int,
) -> Program:
    if main.args:
        raise InternalError("main method should not have args")
    return_type = wtype_to_ir_type(main.return_type)
    if return_type.avm_type != AVMType.uint64:
        raise InternalError("main method should return uint64 backed type")
    main_sub = Subroutine(
        id=main.full_name,
        short_name=main.short_name,
        parameters=[],
        returns=[return_type],
        body=[],
        inline=False,
        source_location=main.source_location,
    )
    FunctionIRBuilder.build_body(ctx, function=main, subroutine=main_sub)
    program = Program(
        kind=ref.kind,
        main=main_sub,
        subroutines=tuple(references),
        avm_version=avm_version,
    )
    remove_unused_subroutines(program)
    return program


class SubroutineCollector(FunctionTraverser):
    def __init__(
        self,
        context: IRBuildContext,
        callees: CalleesLookup,
        arc4_router_func: awst_nodes.Function | None,
    ) -> None:
        self.context = context
        self.result = StableSet[awst_nodes.Function]()
        self.callees = callees
        self._func_stack = list[awst_nodes.Function]()
        self._arc4_router_func = arc4_router_func

    @classmethod
    def collect(
        cls,
        context: IRBuildContext,
        start: awst_nodes.Function,
        callees: CalleesLookup,
        *,
        arc4_router_func: awst_nodes.Function | None,
    ) -> StableSet[awst_nodes.Function]:
        collector = cls(context, callees, arc4_router_func)
        with collector._enter_func(start):  # noqa: SLF001
            start.body.accept(collector)
        return collector.result

    @typing.override
    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        callee = self._func_stack[-1]
        func = self.context.resolve_function_reference(
            expr.target, expr.source_location, caller=callee
        )
        self._visit_func(func)

    @typing.override
    def visit_arc4_router(self, expr: awst_nodes.ARC4Router) -> None:
        if self._arc4_router_func is not None:
            self._visit_func(self._arc4_router_func)

    def _visit_func(self, func: awst_nodes.Function) -> None:
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
