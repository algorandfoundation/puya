import contextlib
import copy
import functools
import typing
from collections import defaultdict
from collections.abc import Callable, Collection, Iterator, Set
from pathlib import Path

from immutabledict import immutabledict

from puya import artifact_metadata, log
from puya.avm import AVMType
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.serialize import awst_from_json
from puya.context import ArtifactCompileContext, CompileContext
from puya.ir import arc4_router
from puya.ir._contract_metadata import build_contract_metadata
from puya.ir._utils import make_subroutine
from puya.ir.arc4_router import AWSTContractMethodSignature
from puya.ir.builder.lower_array import lower_array_nodes
from puya.ir.builder.main import FunctionIRBuilder
from puya.ir.context import IRBuildContext
from puya.ir.destructure.main import destructure_ssa
from puya.ir.models import (
    Contract,
    LogicSignature,
    ModuleArtifact,
    Program,
    SlotAllocation,
    SlotAllocationStrategy,
    Subroutine,
)
from puya.ir.optimize.dead_code_elimination import remove_unused_subroutines
from puya.ir.optimize.main import optimize_program_ir
from puya.ir.optimize.slot_elimination import slot_elimination
from puya.ir.to_text_visitor import render_program
from puya.ir.types_ import wtype_to_ir_type
from puya.ir.validation.main import validate_module_artifact
from puya.program_refs import (
    ContractReference,
    LogicSigReference,
    ProgramKind,
)
from puya.utils import StableSet, attrs_extend, coalesce, set_add, set_remove

logger = log.get_logger(__name__)


CalleesLookup: typing.TypeAlias = defaultdict[awst_nodes.Function, set[awst_nodes.Function]]
_EMBEDDED_LIB = Path(__file__).parent / "_puya_lib.awst.json"


def awst_to_ir(context: CompileContext, awst: awst_nodes.AWST) -> Iterator[ModuleArtifact]:
    compilation_set = _CompilationSetCollector.collect(context, awst)

    ir_ctx = _build_subroutines(context, awst)

    for node in compilation_set:
        artifact_ctx = ir_ctx.for_root(node)
        with artifact_ctx.log_exceptions():
            if isinstance(node, awst_nodes.LogicSignature):
                yield _build_logic_sig_ir(artifact_ctx, node)
            else:
                yield _build_contract_ir(artifact_ctx, node)


def _build_subroutines(ctx: CompileContext, awst: awst_nodes.AWST) -> IRBuildContext:
    embedded_awst = awst_from_json(_EMBEDDED_LIB.read_text(encoding="utf8"))
    embedded_subroutines = {
        node: make_subroutine(node, allow_implicits=False)
        for node in embedded_awst
        if isinstance(node, awst_nodes.Subroutine)
    }
    user_subroutines = {
        node: make_subroutine(node, allow_implicits=True)
        for node in awst
        if isinstance(node, awst_nodes.Subroutine)
    }
    ir_ctx = attrs_extend(
        IRBuildContext,
        ctx,
        subroutines={**embedded_subroutines, **user_subroutines},
        awst=[*embedded_awst, *awst],
        embedded_funcs_lookup={func.id: sub for func, sub in embedded_subroutines.items()},
    )
    for func, sub in ir_ctx.subroutines.items():
        FunctionIRBuilder.build_body(ir_ctx, function=func, subroutine=sub)
    return ir_ctx


class _CompilationSetCollector(AWSTTraverser):
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


def get_transform_pipeline(
    artifact_ir: ModuleArtifact,
) -> list[Callable[[ArtifactCompileContext, Program], None]]:
    ref = artifact_ir.metadata.ref
    return [
        functools.partial(_optimize_program_ir, artifact_ir=artifact_ir, qualifier="ssa.opt"),
        functools.partial(_lower_array_ir, ref=ref),
        functools.partial(
            _optimize_program_ir, artifact_ir=artifact_ir, qualifier="ssa.array.opt"
        ),
        functools.partial(slot_elimination, ref=ref),
        destructure_ssa,
    ]


def transform_ir(context: ArtifactCompileContext, artifact_ir: ModuleArtifact) -> ModuleArtifact:
    pipeline = get_transform_pipeline(artifact_ir)
    for transform in pipeline:
        for program in artifact_ir.all_programs():
            transform(context, program)
        # each group starts at the same seq to improve stability of output paths
        context.begin_output_group()
    # validation is run as the last step, in case we've accidentally inserted something,
    # and in particular post subroutine removal, because some things that are "linked"
    # are not necessarily used from the current artifact
    validate_module_artifact(context, artifact_ir)
    return artifact_ir


def _build_logic_sig_ir(
    ctx: IRBuildContext, logic_sig: awst_nodes.LogicSignature
) -> LogicSignature:
    metadata = artifact_metadata.LogicSignatureMetaData(
        ref=logic_sig.id,
        description=logic_sig.docstring,
        name=logic_sig.short_name,
    )
    avm_version = coalesce(logic_sig.avm_version, ctx.options.target_avm_version)
    sig_ir = _make_program(
        ctx,
        logic_sig.program,
        kind=ProgramKind.logic_signature,
        avm_version=avm_version,
        reserved_scratch_space=logic_sig.reserved_scratch_space,
    )
    return LogicSignature(
        program=sig_ir, metadata=metadata, source_location=logic_sig.source_location
    )


def _optimize_program_ir(
    context: ArtifactCompileContext,
    program: Program,
    *,
    artifact_ir: ModuleArtifact,
    qualifier: str,
) -> None:
    if isinstance(artifact_ir, LogicSignature):
        routable_method_ids = None
    else:
        routable_method_ids = {a4m.id for a4m in artifact_ir.metadata.arc4_methods}
    ref = artifact_ir.metadata.ref
    logger.debug(
        f"optimizing {program.kind} program of {ref} at level {context.options.optimization_level}"
    )

    optimize_program_ir(
        context, program, routable_method_ids=routable_method_ids, qualifier=qualifier
    )


def _lower_array_ir(
    context: ArtifactCompileContext,
    program: Program,
    *,
    ref: ContractReference | LogicSigReference,
) -> None:
    logger.debug(f"lowering array IR nodes in {program.kind} program of {ref}")
    for sub in program.all_subroutines:
        lower_array_nodes(sub)
        sub.validate_with_ssa()
    if context.options.output_ssa_ir:
        render_program(context, program, qualifier="ssa.array")


def _build_contract_ir(ctx: IRBuildContext, contract: awst_nodes.Contract) -> Contract:
    metadata, arc4_methods = build_contract_metadata(ctx, contract)
    routing_data = {
        md: AWSTContractMethodSignature(
            target=awst_nodes.ContractMethodTarget(cref=cm.cref, member_name=cm.member_name),
            return_type=cm.return_type,
            parameter_types=[a.wtype for a in cm.args],
        )
        for cm, md in arc4_methods.items()
    }
    arc4_router_awst = arc4_router.create_abi_router(contract, routing_data)
    ctx.routers[contract.id] = ctx.subroutines[arc4_router_awst] = make_subroutine(
        arc4_router_awst, allow_implicits=False
    )

    # Build callees list, excluding calls from router.
    # Used to if a function should implicitly return mutable reference parameters.
    callees = SubroutineCollector.collect(
        ctx, contract.approval_program, contract.clear_program, *arc4_methods
    )

    # construct unique Subroutine objects for each function
    # that was referenced through either entry point
    for method in contract.methods:
        # ABI methods which are only called by the ABI router in the approval_program do not need
        # to implicitly return anything as we know our router is not interested in anything but the
        # explicit return value.
        allow_implicits = bool(callees[method])
        # make the emtpy subroutine, because functions reference other functions
        func_ir = make_subroutine(method, allow_implicits=allow_implicits)
        ctx.subroutines[method] = func_ir

    # now construct the subroutine IR
    for func, sub in ctx.subroutines.items():
        if not sub.body:  # in case something is pre-built (ie from embedded lib)
            FunctionIRBuilder.build_body(ctx, function=func, subroutine=sub)

    avm_version = coalesce(contract.avm_version, ctx.options.target_avm_version)
    approval_ir = _make_program(
        ctx,
        contract.approval_program,
        kind=ProgramKind.approval,
        avm_version=avm_version,
        reserved_scratch_space=contract.reserved_scratch_space,
    )
    clear_state_ir = _make_program(
        ctx,
        contract.clear_program,
        kind=ProgramKind.clear_state,
        avm_version=avm_version,
        reserved_scratch_space=contract.reserved_scratch_space,
    )
    return Contract(
        approval_program=approval_ir,
        clear_program=clear_state_ir,
        metadata=metadata,
        source_location=contract.source_location,
    )


def _make_program(
    ctx: IRBuildContext,
    main: awst_nodes.Function,
    *,
    kind: ProgramKind,
    avm_version: int,
    reserved_scratch_space: Set[int],
) -> Program:
    assert not main.args, "main method should not have args"
    return_type = wtype_to_ir_type(main.return_type, main.source_location)
    assert return_type.avm_type == AVMType.uint64, "main method should return uint64 backed type"
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
        kind=kind,
        main=main_sub,
        subroutines=tuple(ctx.subroutines.values()),
        avm_version=avm_version,
        slot_allocation=SlotAllocation(
            reserved=reserved_scratch_space,
            strategy=SlotAllocationStrategy.none,
        ),
        source_location=ctx.root.source_location if ctx.root else None,
    )
    remove_unused_subroutines(program)
    program = copy.deepcopy(program)
    return program


class SubroutineCollector(FunctionTraverser):
    def __init__(self, context: IRBuildContext, callees: CalleesLookup) -> None:
        self.context = context
        self._seen = StableSet[awst_nodes.Function]()
        self.callees = callees
        self._func_stack = list[awst_nodes.Function]()

    @classmethod
    def collect(cls, context: IRBuildContext, *entry_points: awst_nodes.Function) -> CalleesLookup:
        callees = CalleesLookup(set)
        collector = cls(context, callees)
        for start in entry_points:
            with collector._enter_func(start):  # noqa: SLF001
                start.body.accept(collector)
        return callees

    @typing.override
    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        callee = self._func_stack[-1]
        func = self.context.resolve_function_reference(
            expr.target, expr.source_location, caller=callee
        )
        self.callees[func].add(callee)
        if set_add(self._seen, func):
            with self._enter_func(func):
                func.body.accept(self)

    @contextlib.contextmanager
    def _enter_func(self, func: awst_nodes.Function) -> Iterator[None]:
        self._func_stack.append(func)
        try:
            yield
        finally:
            self._func_stack.pop()
