import itertools
from collections.abc import Iterable, Iterator, Sequence

import attrs
import structlog

from wyvern.awst import (
    nodes as awst_nodes,
    wtypes,
)
from wyvern.awst.function_traverser import FunctionTraverser
from wyvern.context import CompileContext
from wyvern.errors import InternalError, TodoError
from wyvern.ir.builder import FunctionIRBuilder, format_tuple_index
from wyvern.ir.context import IRBuildContext
from wyvern.ir.models import (
    Contract,
    ContractState,
    Program,
    Register,
    Subroutine,
)
from wyvern.ir.types_ import AVMType, wtype_to_avm_type
from wyvern.utils import attrs_extend

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
        if contract.is_arc4:
            raise TodoError(
                contract.source_location,
                "TODO: synthesise approval / clear methods for ARC4 contracts",
            )
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
        module_name=contract.module_name,
        class_name=contract.name,
        name_override=contract.name_override,
        description=contract.docstring,
        global_state=folded.global_state,
        local_state=folded.local_state,
        approval_program=approval_ir,
        clear_program=clear_state_ir,
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
    global_state: list[ContractState] = attrs.field(factory=list)
    local_state: list[ContractState] = attrs.field(factory=list)


def fold_state_and_special_methods(
    ctx: IRBuildContext, contract: awst_nodes.ContractFragment
) -> FoldedContract:
    bases = [ctx.resolve_contract_reference(cref) for cref in contract.bases]
    result = FoldedContract()
    for c in [contract, *bases]:
        if result.init is None:
            result.init = c.init
        if result.approval_program is None:
            result.approval_program = c.approval_program
        if result.clear_program is None:
            result.clear_program = c.clear_program
        for state in c.app_state:
            translated = ContractState(
                source_location=state.source_location,
                key=state.key,
                type=wtype_to_avm_type(state.storage_wtype),
                description=None,  # TODO, have some way to provide this
            )
            if state.kind == awst_nodes.AppStateKind.app_global:
                result.global_state.append(translated)
            elif state.kind == awst_nodes.AppStateKind.account_local:
                result.local_state.append(translated)
            else:
                raise InternalError(f"Unhandled state kind: {state.kind}", state.source_location)
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
