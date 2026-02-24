import contextlib
import functools
import typing
from collections import defaultdict
from collections.abc import Callable, Collection, Iterator, Set
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import artifact_metadata, log
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.serialize import awst_from_json
from puya.context import ArtifactCompileContext, CompileContext
from puya.ir import arc4_router
from puya.ir._contract_metadata import build_contract_metadata
from puya.ir._utils import deep_copy, make_subroutine
from puya.ir.arc4_router import AWSTContractMethodSignature
from puya.ir.builder.aggregates.main import lower_aggregate_nodes
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
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference, ProgramKind
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
        functools.partial(_lower_aggregate_ir, ref=ref),
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


def _lower_logic_sig_arg(
    wtype: wtypes.WType,
    arg_idx: int,
    *,
    validate: bool,
    loc: SourceLocation,
) -> tuple[awst_nodes.Expression, int]:
    """Lower a single logical arg starting at the given op.arg index.

    Returns the converted expression and the next available arg. index.
    For tuple types, each element consumes one or more argument indices (recursively).
    """
    if isinstance(wtype, wtypes.WTuple):
        items = list[awst_nodes.Expression]()
        for field_wtype in wtype.types:
            field_expr, arg_idx = _lower_logic_sig_arg(
                field_wtype, arg_idx, validate=validate, loc=loc
            )
            items.append(field_expr)
        return awst_nodes.TupleExpression(items=items, wtype=wtype, source_location=loc), arg_idx

    # (micro opt.) use the arg_N opcode for N<=3, otherwise arg with immediate
    raw_bytes = awst_nodes.IntrinsicCall(
        op_code=f"arg_{arg_idx}" if arg_idx <= 3 else "arg",
        immediates=[] if arg_idx <= 3 else [arg_idx],
        wtype=wtypes.bytes_wtype,
        source_location=loc,
    )
    if wtype.scalar_type == AVMType.uint64:
        converted: awst_nodes.Expression = awst_nodes.IntrinsicCall(
            op_code="btoi",
            stack_args=[raw_bytes],
            wtype=wtypes.uint64_wtype,
            source_location=loc,
        )
        if wtype != wtypes.uint64_wtype:
            converted = awst_nodes.ReinterpretCast(
                expr=converted,
                wtype=wtype,
                source_location=loc,
            )
    elif wtype == wtypes.bytes_wtype:
        converted = raw_bytes
    elif isinstance(wtype, wtypes.ARC4Type):
        converted = awst_nodes.ARC4FromBytes(
            value=raw_bytes,
            validate=validate,
            wtype=wtype,
            source_location=loc,
        )
    else:
        # other bytes-backed types need reinterpret
        converted = awst_nodes.ReinterpretCast(
            expr=raw_bytes,
            wtype=wtype,
            source_location=loc,
        )
    return converted, arg_idx + 1


def _lower_logic_sig_args(
    program: awst_nodes.Subroutine, *, validate: bool
) -> awst_nodes.Subroutine:
    """Transform a logicsig program with args into a parameterless one.

    Prepends assignment statements that read each arg via the `arg` opcode,
    with appropriate type conversion (and optionally validation), then
    clears the arg list.
    """
    if not program.args:
        return program

    arg_assignments = list[awst_nodes.Statement]()
    arg_idx = 0
    for arg in program.args:
        loc = arg.source_location
        converted, arg_idx = _lower_logic_sig_arg(arg.wtype, arg_idx, validate=validate, loc=loc)
        target = awst_nodes.VarExpression(
            name=arg.name,
            wtype=arg.wtype,
            source_location=loc,
        )
        arg_assignments.append(
            awst_nodes.AssignmentStatement(
                target=target,
                value=converted,
                source_location=loc,
            )
        )
    new_body = awst_nodes.Block(
        body=[*arg_assignments, *program.body.body],
        source_location=program.body.source_location,
    )
    # get rid of args in the program as they have already been materialized
    return attrs.evolve(program, args=(), body=new_body)


def _build_logic_sig_ir(
    ctx: IRBuildContext, logic_sig: awst_nodes.LogicSignature
) -> LogicSignature:
    metadata = artifact_metadata.LogicSignatureMetaData(
        ref=logic_sig.id,
        description=logic_sig.docstring,
        name=logic_sig.short_name,
    )

    validate = coalesce(logic_sig.validate_encoding, ctx.options.validate_abi_args)
    program = _lower_logic_sig_args(logic_sig.program, validate=validate)

    avm_version = coalesce(logic_sig.avm_version, ctx.options.target_avm_version)
    sig_ir = _make_program(
        ctx,
        program,
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
    logger.debug(
        f"optimizing {program.kind} program of {artifact_ir.metadata.ref}"
        f" at level {context.options.optimization_level}"
    )
    optimize_program_ir(context, program, qualifier=qualifier)


def _lower_aggregate_ir(
    context: ArtifactCompileContext,
    program: Program,
    *,
    ref: ContractReference | LogicSigReference,
) -> None:
    logger.debug(f"lowering array IR nodes in {program.kind} program of {ref}")
    lower_aggregate_nodes(program)
    if context.options.output_ssa_ir:
        render_program(context, program, qualifier="ssa.array")


def _build_contract_ir(ctx: IRBuildContext, contract: awst_nodes.Contract) -> Contract:
    metadata, arc4_methods = build_contract_metadata(ctx, contract)
    if arc4_methods:
        routing_data = {
            md: AWSTContractMethodSignature(
                target=awst_nodes.ContractMethodTarget(cref=cm.cref, member_name=cm.member_name),
                return_type=cm.return_type,
                parameter_types=[a.wtype for a in cm.args],
            )
            for cm, md in arc4_methods.items()
        }
        router_can_exit_early = _CanExitAfterRouterApproval.analyse(contract)
        arc4_router_awst, wrapper_funcs = arc4_router.create_abi_router(
            contract,
            routing_data,
            can_exit_early=router_can_exit_early,
            validate_args_default=ctx.options.validate_abi_args,
        )
        ctx = attrs.evolve(ctx, awst=[*ctx.awst, *wrapper_funcs])

        ctx.routers[contract.id] = ctx.subroutines[arc4_router_awst] = make_subroutine(
            arc4_router_awst, allow_implicits=False
        )

        for wf in wrapper_funcs:
            wrapper_sub = make_subroutine(wf, allow_implicits=False)
            wrapper_sub.is_routing_wrapper = True
            ctx.subroutines[wf] = wrapper_sub

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


@attrs.define
class _CanExitAfterRouterApproval(FunctionTraverser):
    has_router_return: bool = attrs.field(default=False, init=False)

    class _HasRouterCallOutsideReturn(Exception):  # noqa: N818
        pass

    @classmethod
    def analyse(cls, contract: awst_nodes.Contract) -> bool:
        approval_returns_router = False
        for method in contract.all_methods:
            traverser = cls()
            try:
                method.body.accept(traverser)
            except cls._HasRouterCallOutsideReturn:
                return False
            if traverser.has_router_return:
                if method == contract.approval_program:
                    approval_returns_router = True
                else:
                    return False
        if not approval_returns_router:
            # Ff there was a non-return call to router before this, or a return call to the router
            # from a method other than approval_program itself, we would have exited early.
            # Thus, if we get here, there are no usages of ARC4Router anywhere.
            # The most likely cause in puyapy for example would be overriding the approval-program
            # but not calling the super/base method
            logger.warning(
                f"contract {contract.id} has routable methods but does not have a router",
                location=contract.approval_program.source_location,
            )
        return True

    @typing.override
    def visit_arc4_router(self, expr: awst_nodes.ARC4Router) -> None:
        raise self._HasRouterCallOutsideReturn

    @typing.override
    def visit_return_statement(self, statement: awst_nodes.ReturnStatement) -> None:
        match statement.value:
            case awst_nodes.ARC4Router():
                self.has_router_return = True
            case value if value is not None:
                value.accept(self)


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
    # copy to ensure program has unique copies of subroutines
    program = deep_copy(program)
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
