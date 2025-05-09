import contextlib
import typing
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from operator import itemgetter

import attrs
from immutabledict import immutabledict

import puya.artifact_metadata as models
from puya import algo_constants, log
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.function_traverser import FunctionTraverser
from puya.errors import CodeError, InternalError
from puya.ir._arc4_default_args import convert_default_args
from puya.ir.arc4_types import (
    get_arc4_name,
    wtype_to_arc4,
    wtype_to_arc4_wtype,
)
from puya.ir.builder.storage import get_storage_codec
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
    models.ContractMetaData,
    dict[awst_nodes.ContractMethod, models.ARC4Method],
]:
    global_state = dict[str, models.ContractState]()
    local_state = dict[str, models.ContractState]()
    boxes = dict[str, models.ContractState]()
    for state in contract.app_state:
        translated = _translate_state(state)
        match state.kind:
            case awst_nodes.AppStorageKind.app_global:
                global_state[state.member_name] = translated
            case awst_nodes.AppStorageKind.account_local:
                local_state[state.member_name] = translated
            case awst_nodes.AppStorageKind.box:
                boxes[state.member_name] = translated
            case unexpected:
                typing.assert_never(unexpected)
    state_totals = _build_state_totals(
        contract.state_totals,
        global_state=global_state,
        local_state=local_state,
        location=contract.source_location,
    )
    arc4_method_data, type_refs = _extract_arc4_methods_and_type_refs(ctx, contract)
    structs = _extract_structs(type_refs)
    template_var_types = _TemplateVariableTypeCollector.collect(ctx, contract, arc4_method_data)
    metadata = models.ContractMetaData(
        description=contract.description,
        name=contract.name,
        ref=contract.id,
        arc4_methods=list(arc4_method_data.values()),
        global_state=immutabledict(global_state),
        local_state=immutabledict(local_state),
        boxes=immutabledict(boxes),
        state_totals=state_totals,
        structs=immutabledict(structs),
        template_variable_types=immutabledict(template_var_types),
    )
    return metadata, arc4_method_data


def _translate_state(state: awst_nodes.AppStorageDefinition) -> models.ContractState:
    # assert, because it should have been validated by StorageTypeValidator at AWST level
    assert state.storage_wtype.persistable, f"non-persistable contract member: {state.member_name}"
    storage_codec = get_storage_codec(state.storage_wtype, state.kind, state.source_location)
    storage_type = storage_codec.encoded_avm_type
    if state.key_wtype is not None:
        if state.kind is not awst_nodes.AppStorageKind.box:
            raise InternalError(
                f"maps of {state.kind} are not supported by IR backend yet", state.source_location
            )
        arc56_key_type = _get_arc56_type(
            state.key_wtype, state.source_location, avm_uint64_supported=False
        )
        is_map = True
    else:
        arc56_key_type = (
            "AVMString" if state.key.encoding == awst_nodes.BytesEncoding.utf8 else "AVMBytes"
        )
        is_map = False
    if state.kind == awst_nodes.AppStorageKind.box:
        avm_uint64_supported = False
    else:
        typing.assert_type(
            state.kind,
            typing.Literal[
                awst_nodes.AppStorageKind.app_global, awst_nodes.AppStorageKind.account_local
            ],
        )
        avm_uint64_supported = True
    arc56_value_type = _get_arc56_type(
        state.storage_wtype, state.source_location, avm_uint64_supported=avm_uint64_supported
    )
    return models.ContractState(
        name=state.member_name,
        source_location=state.source_location,
        key_or_prefix=state.key.value,
        arc56_key_type=arc56_key_type,
        arc56_value_type=arc56_value_type,
        storage_type=storage_type,
        description=state.description,
        is_map=is_map,
    )


def _build_state_totals(
    declared_totals: awst_nodes.StateTotals | None,
    *,
    global_state: Mapping[str, models.ContractState],
    local_state: Mapping[str, models.ContractState],
    location: SourceLocation,
) -> models.StateTotals:
    global_by_type = Counter(s.storage_type for s in global_state.values())
    local_by_type = Counter(s.storage_type for s in local_state.values())
    merged = models.StateTotals(
        global_uints=global_by_type[AVMType.uint64],
        global_bytes=global_by_type[AVMType.bytes],
        local_uints=local_by_type[AVMType.uint64],
        local_bytes=local_by_type[AVMType.bytes],
    )
    if declared_totals is not None:
        insufficient_fields = []
        declared_dict = attrs.asdict(declared_totals, filter=attrs.filters.include(int))
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
            name: _get_arc56_type(var.wtype, var.source_location, avm_uint64_supported=True)
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
        super().visit_subroutine_call_expression(expr)
        target = self.context.resolve_function_reference(
            expr.target,
            expr.source_location,
            caller=self.current_func,
        )
        self.process_func(target)


def _extract_arc4_methods_and_type_refs(
    ctx: IRBuildContext, contract: awst_nodes.Contract
) -> tuple[dict[awst_nodes.ContractMethod, models.ARC4Method], list[wtypes.WType]]:
    event_collector = _EventCollector(ctx)
    type_refs = [
        typ
        for state in contract.app_state
        for typ in (state.key_wtype, state.storage_wtype)
        if typ is not None
    ]
    methods = dict[awst_nodes.ContractMethod, models.ARC4Method]()

    # aggregate errors for the contract so that the user doesn't get incremental errors
    with _collect_arc4_type_mapping_errors() as type_mapper:
        for method_name in unique(m.member_name for m in contract.methods):
            m = contract.resolve_contract_method(method_name)
            assert m is not None  # shouldn't logically be possible
            match m.arc4_method_config:
                case None:
                    pass
                case awst_nodes.ARC4BareMethodConfig() as bare_method_config:
                    methods[m] = models.ARC4BareMethod(
                        id=m.full_name, desc=m.documentation.description, config=bare_method_config
                    )
                case abi_method_config:
                    event_wtypes = event_collector.process_func(m)
                    events = list(map(_wtype_to_struct, event_wtypes))
                    methods[m] = _abi_method_metadata(
                        ctx, contract, m, abi_method_config, events, type_mapper
                    )
                    if m.return_type is not None:
                        type_refs.append(m.return_type)
                    type_refs.extend(arg.wtype for arg in m.args)
                    for event_struct in event_wtypes:
                        type_refs.extend(event_struct.types)
    return methods, type_refs


_ARC4TypeMapper = Callable[
    [typing.Literal["argument", "return"], wtypes.WType, SourceLocation], str
]


@contextlib.contextmanager
def _collect_arc4_type_mapping_errors() -> Iterator[_ARC4TypeMapper]:
    errors = list[Exception]()

    def _map(
        kind: typing.Literal["argument", "return"], wtype: wtypes.WType, loc: SourceLocation
    ) -> str:
        try:
            return wtype_to_arc4(kind, wtype, loc)
        # collect CodeErrors from this function, let any other errors propagate
        except CodeError as ex:
            errors.append(ex)
            return ""

    try:
        yield _map
    except Exception as ex:
        # if another exception occurs other than a CodeError in `wtype_to_arc4`,
        # ensure that neither it nor any gathered exceptions are discarded
        if errors:
            errors.append(ex)
        else:
            raise
    if errors:
        raise ExceptionGroup("ARC-4 type mapping errors", errors)


def _extract_structs(
    typ_refs: Sequence[wtypes.WType],
) -> dict[str, models.ARC4Struct]:
    # Produce a unique mapping of struct names to ARC4Struct definitions.
    # Will recursively include any structs referenced in fields
    struct_wtypes = list(filter(_is_arc4_struct, typ_refs))
    struct_results = dict[str, models.ARC4Struct]()
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
    return dict(sorted(struct_results.items(), key=itemgetter(0)))


def _abi_method_metadata(
    ctx: IRBuildContext,
    contract: awst_nodes.Contract,
    m: awst_nodes.ContractMethod,
    config: awst_nodes.ARC4ABIMethodConfig,
    events: Sequence[models.ARC4Struct],
    type_mapper: _ARC4TypeMapper,
) -> models.ARC4ABIMethod:
    assert config is m.arc4_method_config
    default_args = convert_default_args(ctx, contract, m, config)
    args = [
        models.ARC4MethodArg(
            name=a.name,
            type_=type_mapper("argument", a.wtype, a.source_location),
            struct=_get_arc4_struct_name(a.wtype),
            desc=m.documentation.args.get(a.name),
            client_default=default_args[a],
        )
        for a in m.args
    ]
    returns = models.ARC4Returns(
        desc=m.documentation.returns,
        type_=type_mapper("return", m.return_type, m.source_location),
        struct=_get_arc4_struct_name(m.return_type),
    )
    return models.ARC4ABIMethod(
        id=m.full_name,
        desc=m.documentation.description,
        args=args,
        returns=returns,
        events=events,
        config=config,
    )


def _is_arc4_struct(
    wtype: wtypes.WType | None,
) -> typing.TypeGuard[wtypes.ARC4Struct | wtypes.WTuple]:
    return isinstance(wtype, wtypes.ARC4Struct | wtypes.WTuple) and bool(wtype.fields)


def _get_arc4_struct_name(wtype: wtypes.WType) -> str | None:
    return wtype.name if _is_arc4_struct(wtype) else None


def _wtype_to_struct(s: wtypes.ARC4Struct | wtypes.WTuple) -> models.ARC4Struct:
    fields = []
    assert s.fields
    for field_name, field_wtype in s.fields.items():
        if not isinstance(field_wtype, wtypes.ARC4Type):
            field_wtype = wtype_to_arc4_wtype(field_wtype, None)
        fields.append(
            models.ARC4StructField(
                name=field_name,
                type=get_arc4_name(field_wtype, use_alias=True),
                struct=_get_arc4_struct_name(field_wtype),
            )
        )
    return models.ARC4Struct(fullname=s.name, desc=s.desc, fields=fields)


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


def _get_arc56_type(
    wtype: wtypes.WType, loc: SourceLocation, *, avm_uint64_supported: bool
) -> str:
    if isinstance(wtype, wtypes.StackArray | wtypes.WTuple):
        wtype = wtype_to_arc4_wtype(wtype, loc)
    if wtype == wtypes.account_wtype:
        wtype = wtypes.arc4_address_alias
    if isinstance(wtype, wtypes.ARC4Struct):
        return wtype.name
    if isinstance(wtype, wtypes.ARC4Type):
        return get_arc4_name(wtype, use_alias=True)
    if wtype == wtypes.string_wtype:
        return "AVMString"
    match wtype.scalar_type:
        case AVMType.uint64:
            if avm_uint64_supported:
                return "AVMUint64"
            else:
                return "uint64"
        case AVMType.bytes | None:
            return "AVMBytes"
