import contextlib
import itertools
import typing
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
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
from puya.errors import InternalError
from puya.ir import arc4_router
from puya.ir.arc4_router import extract_arc4_methods, maybe_avm_to_arc4_equivalent_type
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
    ARC4ABIMethod,
    ARC4Method,
    ARC4MethodConfig,
    ARC4Struct,
    ARC4StructField,
    ContractMetaData,
    ContractState,
    LogicSignatureMetaData,
    StateTotals,
)
from puya.parse import SourceLocation
from puya.utils import StableSet, attrs_extend, coalesce, set_remove, unique

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
        match node:
            case awst_nodes.Contract() as contract_node:
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
        FunctionIRBuilder.build_body(embedded_ctx, function=func, subroutine=sub)
    return embedded_funcs_lookup


def _build_ir(ctx: IRBuildContext, contract: awst_nodes.Contract) -> Contract:
    folded, arc4_method_data = _fold_state_and_special_methods(contract)
    arc4_router_func = arc4_router.create_abi_router(contract, arc4_method_data)
    ctx.subroutines[arc4_router_func] = ctx.routers[contract.id] = _make_subroutine(
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
    function_emits = EventCollector.collect(ctx, unique((*approval_subs_srefs, *clear_subs_srefs)))

    # collect emitted events by method, and include any referenced structs
    structs = list(folded.structs)
    arc4_methods = []
    for method, arc4_method in arc4_method_data.items():
        if isinstance(arc4_method, ARC4ABIMethod):
            method_structs = function_emits[method]
            # extend structs with any arc4 struct types that are part of an event
            structs.extend(
                t
                for method_struct in method_structs
                for t in method_struct.fields.values()
                if isinstance(t, wtypes.ARC4Struct)
            )
            arc4_method = attrs.evolve(
                arc4_method, events=list(map(_wtype_to_struct, method_structs))
            )
        arc4_methods.append(arc4_method)
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
            FunctionIRBuilder.build_body(ctx, function=func, subroutine=sub)

    avm_version = coalesce(contract.avm_version, ctx.options.target_avm_version)
    approval_ir = _make_program(
        ctx,
        contract.approval_program,
        StableSet(
            *(ctx.subroutines[ref] for ref in approval_subs_srefs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        program_id=".".join((contract.id, contract.approval_program.short_name)),
        avm_version=avm_version,
    )
    clear_state_ir = _make_program(
        ctx,
        contract.clear_program,
        StableSet(
            *(ctx.subroutines[ref] for ref in clear_subs_srefs),
            *ctx.embedded_funcs_lookup.values(),
        ),
        program_id=".".join((contract.id, contract.clear_program.short_name)),
        avm_version=avm_version,
    )
    result = Contract(
        source_location=contract.source_location,
        approval_program=approval_ir,
        clear_program=clear_state_ir,
        metadata=ContractMetaData(
            description=contract.description,
            name=contract.name,
            ref=contract.id,
            arc4_methods=arc4_methods,
            global_state=immutabledict(folded.global_state),
            local_state=immutabledict(folded.local_state),
            boxes=immutabledict(folded.boxes),
            state_totals=folded.build_state_totals(location=contract.source_location),
            structs=immutabledict(_wtypes_to_structs(structs)),
            template_variable_types=immutabledict(
                TemplateVariableTypeCollector.collect(ctx.subroutines)
            ),
        ),
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
            ctx.subroutines[func] = _make_subroutine(func, allow_implicits=True)
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
        program_id=logic_sig.id,
        avm_version=coalesce(logic_sig.avm_version, ctx.options.target_avm_version),
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
            item_name = format_tuple_index(typ, name, item_idx)
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
    avm_version: int,
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
    FunctionIRBuilder.build_body(ctx, function=main, subroutine=main_sub)
    return Program(
        id=program_id,
        main=main_sub,
        subroutines=tuple(references),
        avm_version=avm_version,
    )


@attrs.define(kw_only=True)
class FoldedContract:
    global_state: dict[str, ContractState] = attrs.field(factory=dict)
    local_state: dict[str, ContractState] = attrs.field(factory=dict)
    boxes: dict[str, ContractState] = attrs.field(factory=dict)
    arc4_methods: list[ARC4Method] = attrs.field(factory=list)
    structs: list[wtypes.ARC4Struct | wtypes.WTuple] = attrs.field(factory=list)
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
    contract: awst_nodes.Contract,
) -> dict[awst_nodes.ContractMethod, ARC4MethodConfig]:
    maybe_arc4_method_refs = dict[str, tuple[awst_nodes.ContractMethod, ARC4MethodConfig] | None]()
    for cref in (contract.id, *contract.method_resolution_order):
        for cm in contract.methods:
            if cm.cref == cref:
                if cm.arc4_method_config:
                    maybe_arc4_method_refs.setdefault(cm.member_name, (cm, cm.arc4_method_config))
                else:
                    maybe_arc4_method_refs.setdefault(cm.member_name, None)
    arc4_method_refs = dict(filter(None, maybe_arc4_method_refs.values()))
    return arc4_method_refs


def _fold_state_and_special_methods(
    contract: awst_nodes.Contract,
) -> tuple[FoldedContract, dict[awst_nodes.ContractMethod, ARC4Method]]:
    result = FoldedContract(
        declared_totals=contract.state_totals,
    )
    struct_types = list[wtypes.ARC4Struct | wtypes.WTuple]()
    for state in contract.app_state:
        key_type = None
        if state.key_wtype is not None:
            key_type = wtypes.persistable_stack_type(state.key_wtype, state.source_location)
            if _is_arc4_struct(state.key_wtype):
                struct_types.append(state.key_wtype)
        if _is_arc4_struct(state.storage_wtype):
            struct_types.append(state.storage_wtype)
        translated = _get_contract_state(state)
        match state.kind:
            case awst_nodes.AppStorageKind.app_global:
                if key_type is not None:
                    raise InternalError(
                        f"maps of {state.kind} are not supported yet", state.source_location
                    )
                result.global_state[state.member_name] = translated
            case awst_nodes.AppStorageKind.account_local:
                if key_type is not None:
                    raise InternalError(
                        f"maps of {state.kind} are not supported yet", state.source_location
                    )
                result.local_state[state.member_name] = translated
            case awst_nodes.AppStorageKind.box:
                result.boxes[state.member_name] = translated
            case _:
                typing.assert_never(state.kind)
    arc4_method_refs = _gather_arc4_methods(contract)
    for arc4_method in arc4_method_refs:
        for wtype in (arc4_method.return_type, *(arg.wtype for arg in arc4_method.args)):
            if _is_arc4_struct(wtype):
                struct_types.append(wtype)
    if arc4_method_refs:
        methods = extract_arc4_methods(
            arc4_method_refs,
            local_state=result.local_state,
            global_state=result.global_state,
        )
        result.arc4_methods = list(methods.values())
    else:
        methods = {}
    result.structs = struct_types
    return result, methods


def _is_arc4_struct(wtype: wtypes.WType) -> typing.TypeGuard[wtypes.ARC4Struct | wtypes.WTuple]:
    return isinstance(wtype, wtypes.ARC4Struct | wtypes.WTuple) and bool(wtype.fields)


def _wtypes_to_structs(
    structs: Sequence[wtypes.ARC4Struct | wtypes.WTuple],
) -> dict[str, ARC4Struct]:
    """
    Produce a unique mapping of struct names to ARC4Struct definitions.
    Will recursively include any structs referenced in fields
    """
    structs = list(structs)
    struct_results = dict[wtypes.ARC4Struct | wtypes.WTuple, ARC4Struct]()
    while structs:
        struct = structs.pop()
        if struct in struct_results:
            continue
        structs.extend(
            wtype
            for wtype in struct.fields.values()
            if isinstance(wtype, wtypes.ARC4Struct) and wtype not in struct_results
        )
        struct_results[struct] = _wtype_to_struct(struct)
    return {
        wtype.name: struct_results[wtype] for wtype in sorted(struct_results, key=lambda s: s.name)
    }


def _wtype_to_struct(struct: wtypes.ARC4Struct | wtypes.WTuple) -> ARC4Struct:
    fields = []
    for field_name, field_wtype in struct.fields.items():
        if not isinstance(field_wtype, wtypes.ARC4Type):
            maybe_arc4_field_wtype = maybe_avm_to_arc4_equivalent_type(field_wtype)
            if maybe_arc4_field_wtype is None:
                raise InternalError("expected ARC4 type")
            field_wtype = maybe_arc4_field_wtype
        fields.append(
            ARC4StructField(
                name=field_name,
                type=field_wtype.arc4_name,
                struct=field_wtype.name if _is_arc4_struct(field_wtype) else None,
            )
        )
    return ARC4Struct(
        fullname=struct.name,
        desc=struct.desc,
        fields=fields,
    )


def _get_contract_state(state: awst_nodes.AppStorageDefinition) -> ContractState:
    storage_type = wtypes.persistable_stack_type(state.storage_wtype, state.source_location)
    if state.key_wtype is not None:
        arc56_key_type = _get_arc56_type(state.key_wtype, state.source_location)
        is_map = True
    else:
        arc56_key_type = (
            "AVMString" if state.key.encoding == awst_nodes.BytesEncoding.utf8 else "AVMBytes"
        )
        is_map = False
    arc56_value_type = _get_arc56_type(state.storage_wtype, state.source_location)
    return ContractState(
        name=state.member_name,
        source_location=state.source_location,
        key_or_prefix=state.key.value,
        arc56_key_type=arc56_key_type,
        arc56_value_type=arc56_value_type,
        storage_type=storage_type,
        description=state.description,
        is_map=is_map,
    )


def _get_arc56_type(wtype: wtypes.WType, loc: SourceLocation) -> str:
    if isinstance(wtype, wtypes.ARC4Struct):
        return wtype.name
    if isinstance(wtype, wtypes.ARC4Type):
        return wtype.arc4_name
    if wtype == wtypes.string_wtype:
        return "AVMString"
    storage_type = wtypes.persistable_stack_type(wtype, loc)
    match storage_type:
        case AVMType.uint64:
            return "AVMUint64"
        case AVMType.bytes:
            return "AVMBytes"


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


@attrs.frozen
class EventCollector(FunctionTraverser):
    context: IRBuildContext
    emits: dict[awst_nodes.Function, StableSet[wtypes.ARC4Struct]] = attrs.field(factory=dict)
    _func_stack: list[awst_nodes.Function] = attrs.field(factory=list)

    @classmethod
    def collect(
        cls, context: IRBuildContext, all_funcs: Iterable[awst_nodes.Function]
    ) -> Mapping[awst_nodes.Function, StableSet[wtypes.ARC4Struct]]:
        collector = cls(context)
        for func in all_funcs:
            collector.process_func(func)
        return collector.emits

    def process_func(self, func: awst_nodes.Function) -> None:
        if func in self.emits:
            return
        self.emits[func] = StableSet[wtypes.ARC4Struct]()
        with self._enter_func(func):
            func.body.accept(self)

    @contextlib.contextmanager
    def _enter_func(self, func: awst_nodes.Function) -> Iterator[None]:
        self._func_stack.append(func)
        try:
            yield
        finally:
            self._func_stack.pop()

    @property
    def current_func(self) -> awst_nodes.Function:
        return self._func_stack[-1]

    def visit_emit(self, emit: awst_nodes.Emit) -> None:
        assert isinstance(emit.value.wtype, wtypes.ARC4Struct)
        self.emits[self.current_func].add(emit.value.wtype)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        target = self.context.resolve_function_reference(
            expr.target,
            expr.source_location,
            caller=self.current_func,
        )
        self.process_func(target)
        self.emits[self.current_func] |= self.emits[target]


class TemplateVariableTypeCollector(FunctionTraverser):
    def __init__(self) -> None:
        self.vars = dict[str, awst_nodes.TemplateVar]()

    @classmethod
    def collect(cls, functions: Iterable[awst_nodes.Function]) -> dict[str, str]:
        collector = cls()
        for function in functions:
            function.body.accept(collector)
        return {
            name: _get_arc56_type(var.wtype, var.source_location)
            for name, var in collector.vars.items()
        }

    def visit_template_var(self, var: awst_nodes.TemplateVar) -> None:
        try:
            existing = self.vars[var.name]
        except KeyError:
            self.vars[var.name] = var
        else:
            if existing.wtype != var.wtype:
                logger.error(
                    "inconsistent types specified for template var",
                    location=var.source_location,
                )
                logger.info("other template var", location=existing.source_location)
