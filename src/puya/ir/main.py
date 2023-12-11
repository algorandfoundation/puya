import itertools
import typing
from collections.abc import Iterable, Iterator, Sequence

import attrs
import structlog

from puya import metadata
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.function_traverser import FunctionTraverser
from puya.context import CompileContext
from puya.errors import CodeError, InternalError
from puya.ir.arc4_router import create_abi_router, create_default_clear_state
from puya.ir.arc4_util import get_abi_signature
from puya.ir.builder import FunctionIRBuilder, format_tuple_index
from puya.ir.context import IRBuildContext
from puya.ir.models import (
    Contract,
    Program,
    Register,
    Subroutine,
)
from puya.ir.types_ import wtype_to_avm_type
from puya.metadata import ARC4Method, ARC4MethodConfig
from puya.utils import attrs_extend

logger = structlog.get_logger()


def build_ir(
    compile_context: CompileContext,
    contract: awst_nodes.ContractFragment,
    module_awsts: dict[str, awst_nodes.Module],
) -> Contract:
    ctx: IRBuildContext = attrs_extend(
        IRBuildContext,
        compile_context,
        module_awsts=module_awsts,
        contract=contract,
        subroutines={},
    )
    with ctx.log_exceptions():
        return _build_ir(ctx, contract)


def _build_ir(ctx: IRBuildContext, contract: awst_nodes.ContractFragment) -> Contract:
    if contract.is_abstract:
        raise InternalError("attempted to compile abstract contract")
    folded = fold_state_and_special_methods(ctx, contract)
    if not (folded.approval_program and folded.clear_program):
        raise InternalError(
            "contract is non abstract but doesn't have approval and clear programs in hierarchy",
            contract.source_location,
        )
    # visit call graph starting at entry point(s) to collect all references for each
    approval_subs_srefs = SubroutineCollector.collect(ctx, start=folded.approval_program.body)
    clear_subs_srefs = SubroutineCollector.collect(ctx, start=folded.clear_program.body)
    if folded.init:
        approval_subs_srefs.append(folded.init)
        init_sub_srefs = SubroutineCollector.collect(ctx, start=folded.init.body)
        approval_subs_srefs.extend(init_sub_srefs)
    # construct unique Subroutine objects for each function
    # that was referenced through either entry point
    for func in itertools.chain(approval_subs_srefs, clear_subs_srefs):
        if func not in ctx.subroutines:
            # make the emtpy subroutine, because functions reference other functions
            ctx.subroutines[func] = _make_subroutine(func)
    # now construct the subroutine IR
    for func, sub in ctx.subroutines.items():
        FunctionIRBuilder.build_body(ctx, sub, function=func, on_create=None)

    approval_ir = _make_program(
        ctx, folded.approval_program, approval_subs_srefs, on_create=folded.init
    )
    clear_state_ir = _make_program(ctx, folded.clear_program, clear_subs_srefs, on_create=None)
    result = Contract(
        source_location=contract.source_location,
        approval_program=approval_ir,
        clear_program=clear_state_ir,
        metadata=_create_contract_metadata(
            contract,
            folded.global_state,
            folded.local_state,
            folded.arc4_methods,
        ),
    )

    return result


def _create_contract_metadata(
    contract: awst_nodes.ContractFragment,
    global_state: list[metadata.ContractState],
    local_state: list[metadata.ContractState],
    arc4_methods: list[ARC4Method] | None,
) -> metadata.ContractMetaData:
    result = metadata.ContractMetaData(
        description=contract.docstring,
        name_override=contract.name_override,
        module_name=contract.module_name,
        class_name=contract.name,
        is_arc4=contract.is_arc4,
        methods=arc4_methods or [],  # TODO: fixme
        global_state=global_state,
        local_state=local_state,
    )

    return result


def _expand_tuple_params(args: Sequence[awst_nodes.SubroutineArgument]) -> Iterator[Register]:
    idx = 0
    for arg in args:
        if isinstance(arg.wtype, wtypes.WTuple):
            for tup_idx, tup_type in enumerate(arg.wtype.types):
                yield Register(
                    source_location=arg.source_location,
                    version=0,
                    name=format_tuple_index(arg.name, tup_idx),
                    atype=wtype_to_avm_type(tup_type),
                )
                idx += 1
        else:
            yield (
                Register(
                    source_location=arg.source_location,
                    version=0,
                    name=arg.name,
                    atype=wtype_to_avm_type(arg.wtype),
                )
            )
            idx += 1


def _make_subroutine(func: awst_nodes.Function) -> Subroutine:
    """Pre-construct subroutine with an empty body"""
    parameters = list(_expand_tuple_params(func.args))

    if isinstance(func.return_type, wtypes.WTuple):
        returns = [wtype_to_avm_type(t) for t in func.return_type.types]
    elif func.return_type is wtypes.void_wtype:
        returns = []
    else:
        returns = [wtype_to_avm_type(func.return_type)]

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
    main: awst_nodes.ContractMethod,
    references: Iterable[awst_nodes.Function],
    on_create: awst_nodes.Function | None,
) -> Program:
    if main.args:
        raise InternalError("main method should not have args")
    if wtype_to_avm_type(main.return_type) != AVMType.uint64:
        raise InternalError("main method should return uint64 stack type")
    main_sub = Subroutine(
        source_location=main.source_location,
        module_name=main.module_name,
        class_name=main.class_name,
        method_name=main.name,
        parameters=[],
        returns=[AVMType.uint64],
        body=[],
    )
    on_create_sub: Subroutine | None = None
    if on_create is not None:
        on_create_sub = ctx.subroutines[on_create]
    FunctionIRBuilder.build_body(ctx, main_sub, function=main, on_create=on_create_sub)
    return Program(
        main=main_sub,
        subroutines=[ctx.subroutines[ref] for ref in references],
    )


@attrs.define(kw_only=True)
class FoldedContract:
    init: awst_nodes.ContractMethod | None = None
    approval_program: awst_nodes.ContractMethod | None = None
    clear_program: awst_nodes.ContractMethod | None = None
    global_state: list[metadata.ContractState] = attrs.field(factory=list)
    local_state: list[metadata.ContractState] = attrs.field(factory=list)
    arc4_methods: list[ARC4Method] | None = attrs.field(default=None)


def wtype_to_storage_type(wtype: wtypes.WType) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
    atype = wtype_to_avm_type(wtype)
    assert atype is not AVMType.any
    return atype


def fold_state_and_special_methods(
    ctx: IRBuildContext, contract: awst_nodes.ContractFragment
) -> FoldedContract:
    bases = [ctx.resolve_contract_reference(cref) for cref in contract.bases]
    result = FoldedContract()
    arc4_method_refs = dict[str, tuple[awst_nodes.ContractMethod, ARC4MethodConfig]]()
    for c in [contract, *bases]:
        if result.init is None:
            result.init = c.init
        if result.approval_program is None:
            result.approval_program = c.approval_program
        if result.clear_program is None:
            result.clear_program = c.clear_program
        for state in c.app_state:
            translated = metadata.ContractState(
                name=state.member_name,
                source_location=state.source_location,
                key=state.key,
                storage_type=wtype_to_storage_type(state.storage_wtype),
                description=None,  # TODO, have some way to provide this
            )
            if state.kind == awst_nodes.AppStateKind.app_global:
                result.global_state.append(translated)
            elif state.kind == awst_nodes.AppStateKind.account_local:
                result.local_state.append(translated)
            else:
                raise InternalError(f"Unhandled state kind: {state.kind}", state.source_location)
        for cm in c.subroutines:
            if cm.abimethod_config:
                arc4_sig = get_abi_signature(cm, cm.abimethod_config)
                arc4_method_refs.setdefault(arc4_sig, (cm, cm.abimethod_config))
    if contract.is_arc4:
        if result.approval_program:
            raise CodeError(
                "approval_program should not be defined for ARC4 contracts",
                contract.source_location,
            )
        result.approval_program, result.arc4_methods = create_abi_router(
            contract,
            dict(arc4_method_refs.values()),
            local_state=result.local_state,
            global_state=result.global_state,
        )
        if not result.clear_program:
            result.clear_program = create_default_clear_state(contract)
    return result


class SubroutineCollector(FunctionTraverser):
    def __init__(self, context: IRBuildContext) -> None:
        self.context = context
        # use dictionary with empty values to have quick set semantics,
        # but maintain ordering
        self.result = dict[awst_nodes.Function, None]()

    @classmethod
    def collect(
        cls, context: IRBuildContext, start: awst_nodes.Statement
    ) -> list[awst_nodes.Function]:
        collector = cls(context)
        start.accept(collector)
        return list(collector.result.keys())

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        func = self.context.resolve_function_reference(expr)
        if func not in self.result:
            self.result[func] = None
            func.body.accept(self)
