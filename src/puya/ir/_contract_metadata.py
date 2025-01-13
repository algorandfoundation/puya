import contextlib
import typing
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping

import attrs
from immutabledict import immutabledict

from puya import (
    algo_constants,
    log,
    models as puya_models,
)
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.arc4_types import maybe_avm_to_arc4_equivalent_type, wtype_to_arc4
from puya.awst.function_traverser import FunctionTraverser
from puya.errors import InternalError
from puya.ir.arc4_router import AWSTContractMethodSignature
from puya.ir.context import IRBuildContext
from puya.parse import SourceLocation
from puya.utils import StableSet, set_add, unique

__all__ = [
    "build_contract_metadata",
]

logger = log.get_logger(__name__)


def build_contract_metadata(
    ctx: IRBuildContext, contract: awst_nodes.Contract
) -> tuple[
    puya_models.ContractMetaData,
    Mapping[AWSTContractMethodSignature, puya_models.ARC4MethodConfig],
]:
    state = _fold_state(contract)
    arc4_method_data, structs = _extract_arc4_methods_and_structs(ctx, contract)
    metadata = puya_models.ContractMetaData(
        description=contract.description,
        name=contract.name,
        ref=contract.id,
        arc4_methods=list(arc4_method_data.values()),
        global_state=immutabledict(state.global_state),
        local_state=immutabledict(state.local_state),
        boxes=immutabledict(state.boxes),
        state_totals=state.build_state_totals(location=contract.source_location),
        structs=structs,
        template_variable_types=immutabledict(
            _TemplateVariableTypeCollector.collect(ctx, contract, arc4_method_data)
        ),
    )
    return metadata, {cm: md.config for cm, md in arc4_method_data.items()}


@attrs.define(kw_only=True)
class _FoldedContractState:
    global_state: dict[str, puya_models.ContractState] = attrs.field(factory=dict)
    local_state: dict[str, puya_models.ContractState] = attrs.field(factory=dict)
    boxes: dict[str, puya_models.ContractState] = attrs.field(factory=dict)
    declared_totals: awst_nodes.StateTotals | None

    def build_state_totals(self, *, location: SourceLocation) -> puya_models.StateTotals:
        global_by_type = Counter(s.storage_type for s in self.global_state.values())
        local_by_type = Counter(s.storage_type for s in self.local_state.values())
        merged = puya_models.StateTotals(
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


def _fold_state(contract: awst_nodes.Contract) -> _FoldedContractState:
    result = _FoldedContractState(declared_totals=contract.state_totals)
    for state in contract.app_state:
        key_type = None
        if state.key_wtype is not None:
            key_type = wtypes.persistable_stack_type(state.key_wtype, state.source_location)
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
            case unexpected:
                typing.assert_never(unexpected)

    return result


def _get_contract_state(state: awst_nodes.AppStorageDefinition) -> puya_models.ContractState:
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
    return puya_models.ContractState(
        name=state.member_name,
        source_location=state.source_location,
        key_or_prefix=state.key.value,
        arc56_key_type=arc56_key_type,
        arc56_value_type=arc56_value_type,
        storage_type=storage_type,
        description=state.description,
        is_map=is_map,
    )


class _TemplateVariableTypeCollector(FunctionTraverser):
    def __init__(self, context: IRBuildContext) -> None:
        self.context = context
        self.vars = dict[str, awst_nodes.TemplateVar]()
        self._seen_functions = set[awst_nodes.Function]()
        self._func_stack = list[awst_nodes.Function]()

    def process_func(self, func: awst_nodes.Function) -> None:
        if set_add(self._seen_functions, func):
            with self._enter_func(func):
                func.body.accept(self)

    @classmethod
    def collect(
        cls,
        context: IRBuildContext,
        contract: awst_nodes.Contract,
        routable_methods: Iterable[awst_nodes.ContractMethod],
    ) -> dict[str, str]:
        collector = cls(context)
        for function in (contract.approval_program, contract.clear_program, *routable_methods):
            collector.process_func(function)
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

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        target = self.context.resolve_function_reference(
            expr.target,
            expr.source_location,
            caller=self.current_func,
        )
        self.process_func(target)


def _extract_arc4_methods_and_structs(
    ctx: IRBuildContext, contract: awst_nodes.Contract
) -> tuple[
    dict[awst_nodes.ContractMethod, puya_models.ARC4Method],
    immutabledict[str, puya_models.ARC4Struct],
]:
    event_collector = _EventCollector(ctx)

    result = dict[awst_nodes.ContractMethod, puya_models.ARC4Method]()

    # collect emitted events by method, and include any referenced structs
    struct_wtypes = [
        typ
        for state in contract.app_state
        for typ in (state.key_wtype, state.storage_wtype)
        if _is_arc4_struct(typ)
    ]
    for method_name in unique(m.member_name for m in contract.methods):
        m = contract.resolve_contract_method(method_name)
        arc4_config = m.arc4_method_config
        if isinstance(arc4_config, puya_models.ARC4BareMethodConfig):
            result[m] = puya_models.ARC4BareMethod(
                id=m.full_name,
                desc=m.documentation.description,
                config=arc4_config,
            )
        elif isinstance(arc4_config, puya_models.ARC4ABIMethodConfig):
            event_wtypes = event_collector.process_func(m)
            struct_wtypes.extend(
                wtype
                for wtype in (
                    m.return_type,
                    *(arg.wtype for arg in m.args),
                )
                if _is_arc4_struct(wtype)
            )
            # extend structs with any arc4 struct types that are part of an event
            struct_wtypes.extend(
                t
                for method_struct in event_wtypes
                for t in method_struct.fields.values()
                if _is_arc4_struct(t)
            )

            result[m] = puya_models.ARC4ABIMethod(
                id=m.full_name,
                name=m.member_name,
                desc=m.documentation.description,
                args=[
                    puya_models.ARC4MethodArg(
                        name=a.name,
                        type_=wtype_to_arc4(a.wtype),
                        struct=_get_arc4_struct_name(a.wtype),
                        desc=m.documentation.args.get(a.name),
                    )
                    for a in m.args
                ],
                returns=puya_models.ARC4Returns(
                    desc=m.documentation.returns,
                    type_=wtype_to_arc4(m.return_type),
                    struct=_get_arc4_struct_name(m.return_type),
                ),
                events=list(map(_wtype_to_struct, event_wtypes)),
                config=arc4_config,
            )
        else:
            typing.assert_type(arc4_config, None)
    # Produce a unique mapping of struct names to ARC4Struct definitions.
    # Will recursively include any structs referenced in fields
    struct_results = dict[str, puya_models.ARC4Struct]()
    while struct_wtypes:
        struct = struct_wtypes.pop()
        if struct.name in struct_results:
            continue
        struct_wtypes.extend(
            wtype
            for wtype in struct.fields.values()
            if _is_arc4_struct(wtype) and wtype.name not in struct_results
        )
        struct_results[struct.name] = _wtype_to_struct(struct)
    return result, immutabledict(sorted(struct_results.items(), key=lambda item: item[0]))


def _is_arc4_struct(
    wtype: wtypes.WType | None,
) -> typing.TypeGuard[wtypes.ARC4Struct | wtypes.WTuple]:
    return isinstance(wtype, wtypes.ARC4Struct | wtypes.WTuple) and bool(wtype.fields)


def _get_arc4_struct_name(wtype: wtypes.WType) -> str | None:
    return wtype.name if _is_arc4_struct(wtype) else None


def _wtype_to_struct(s: wtypes.ARC4Struct | wtypes.WTuple) -> puya_models.ARC4Struct:
    fields = []
    assert s.fields
    for field_name, field_wtype in s.fields.items():
        if not isinstance(field_wtype, wtypes.ARC4Type):
            maybe_arc4_field_wtype = maybe_avm_to_arc4_equivalent_type(field_wtype)
            if maybe_arc4_field_wtype is None:
                raise InternalError("expected ARC4 type")
            field_wtype = maybe_arc4_field_wtype
        fields.append(
            puya_models.ARC4StructField(
                name=field_name,
                type=field_wtype.arc4_name,
                struct=_get_arc4_struct_name(field_wtype),
            )
        )
    return puya_models.ARC4Struct(fullname=s.name, desc=s.desc, fields=fields)


@attrs.frozen
class _EventCollector(FunctionTraverser):
    context: IRBuildContext
    emits: dict[awst_nodes.Function, StableSet[wtypes.ARC4Struct]] = attrs.field(
        factory=dict, init=False
    )
    _func_stack: list[awst_nodes.Function] = attrs.field(factory=list)

    def process_func(self, func: awst_nodes.Function) -> StableSet[wtypes.ARC4Struct]:
        if func not in self.emits:
            self.emits[func] = StableSet[wtypes.ARC4Struct]()
            with self._enter_func(func):
                func.body.accept(self)
        return self.emits[func]

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
        self.emits[self.current_func] |= self.process_func(target)


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
