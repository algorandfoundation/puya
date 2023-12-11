from collections.abc import Iterable
from math import ceil

import attrs
import structlog

from puya.codegen import ops
from puya.codegen.callgraph import CallGraph
from puya.codegen.context import ProgramCodeGenContext
from puya.codegen.emitprogram import CompiledContract, CompiledProgram
from puya.codegen.stack_assignment import (
    global_stack_assignment,
)
from puya.codegen.teal_writer import emit_memory_ir_as_teal
from puya.context import CompileContext
from puya.ir import models
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.visitor import IRVisitor
from puya.parse import SourceLocation
from puya.utils import attrs_extend

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


@attrs.define
class MemoryIrBuilder(IRVisitor[None]):
    context: ProgramCodeGenContext = attrs.field(on_setattr=attrs.setters.frozen)
    subroutine_names: dict[models.Subroutine, str]
    """Names to use for subroutines when generating block labels"""
    current_subroutine: models.Subroutine
    is_main: bool
    current_ops: list[ops.BaseOp] = attrs.field(factory=list)
    active_op: models.Op | models.ControlOp | None = None
    next_block: models.BasicBlock | None = None

    def _add_op(self, op: ops.BaseOp) -> None:
        self.current_ops.append(op)

    def _get_subroutine_block_name(
        self, subroutine: models.Subroutine, block: models.BasicBlock
    ) -> str:
        comment = (block.comment or "block").replace(" ", "_")
        subroutine_name = self.subroutine_names[subroutine]
        return f"{subroutine_name}_{comment}@{block.id}"

    def _get_block_name(self, block: models.BasicBlock) -> str:
        assert block in self.current_subroutine.body
        return self._get_subroutine_block_name(self.current_subroutine, block)

    def _get_subroutine_entry_block_name(self, subroutine: models.Subroutine) -> str:
        return self.subroutine_names[subroutine]

    def visit_assignment(self, ass: models.Assignment) -> None:
        ass.source.accept(self)
        # right most target is top of stack
        for target in reversed(ass.targets):
            try:
                param_idx = self.current_subroutine.parameters.index(target)
            except ValueError:
                self._add_op(
                    ops.StoreVirtual(
                        local_id=target.local_id,
                        source_location=target.source_location,
                        atype=target.atype,
                    )
                )
            else:
                index = param_idx - len(self.current_subroutine.parameters)
                self._add_op(
                    ops.StoreParam(
                        local_id=target.local_id,
                        index=index,
                        source_location=target.source_location,
                        atype=target.atype,
                    )
                )

    def visit_register(self, reg: models.Register) -> None:
        try:
            param_idx = self.current_subroutine.parameters.index(reg)
        except ValueError:
            self._add_op(
                ops.LoadVirtual(
                    local_id=reg.local_id,
                    source_location=reg.source_location,
                    atype=reg.atype,
                )
            )
        else:
            index = param_idx - len(self.current_subroutine.parameters)
            self._add_op(
                ops.LoadParam(
                    local_id=reg.local_id,
                    index=index,
                    source_location=reg.source_location,
                    atype=reg.atype,
                )
            )

    def visit_value_tuple(self, tup: models.ValueTuple) -> None:
        raise NotImplementedError

    def visit_uint64_constant(self, const: models.UInt64Constant) -> None:
        self._add_op(
            ops.PushInt(
                const.value if not const.teal_alias else const.teal_alias,
                source_location=const.source_location,
            )
        )

    def visit_biguint_constant(self, const: models.BigUIntConstant) -> None:
        byte_length = ceil(const.value.bit_length() / 8.0)
        assert byte_length <= 64, "Biguints must be 64 bytes or less"
        big_uint_bytes = const.value.to_bytes(byteorder="big", length=byte_length)
        self._add_op(
            ops.PushBytes(
                big_uint_bytes,
                source_location=const.source_location,
                comment=str(const.value),
                encoding=AVMBytesEncoding.base16,
            )
        )

    def visit_bytes_constant(self, const: models.BytesConstant) -> None:
        self._add_op(
            ops.PushBytes(
                const.value, encoding=const.encoding, source_location=const.source_location
            )
        )

    def visit_address_constant(self, const: models.AddressConstant) -> None:
        self._add_op(
            ops.PushAddress(
                const.value,
                source_location=const.source_location,
            )
        )

    def visit_method_constant(self, const: models.MethodConstant) -> None:
        self._add_op(
            ops.PushMethod(
                const.value,
                source_location=const.source_location,
            )
        )

    def visit_phi(self, phi: models.Phi) -> None:
        raise NotImplementedError

    def visit_phi_argument(self, arg: models.PhiArgument) -> None:
        raise NotImplementedError

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        for arg in intrinsic.args:
            arg.accept(self)
        self._add_op(
            ops.IntrinsicOp(
                op_code=intrinsic.op.code,
                immediates=intrinsic.immediates,
                source_location=intrinsic.source_location,
                consumes=len(intrinsic.op_signature.args),
                produces=len(intrinsic.op_signature.returns),
                comment=intrinsic.comment,
            )
        )

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        discard_results = callsub is self.active_op
        target = callsub.target

        callsub_op = ops.CallSub(
            target=self._get_subroutine_entry_block_name(target),
            parameters=len(target.parameters),
            returns=len(target.returns),
            source_location=callsub.source_location,
        )

        # prepare args
        for arg in callsub.args:
            arg.accept(self)

        # call sub
        self._add_op(callsub_op)

        if discard_results and target.returns:
            num_returns = len(target.returns)
            self._add_op(ops.Pop(num_returns))

    def visit_conditional_branch(self, branch: models.ConditionalBranch) -> None:
        branch.condition.accept(self)
        if self.next_block is branch.zero:
            op_code = "bnz"
            jump_block = branch.non_zero
            maybe_next_block = branch.zero
        else:
            op_code = "bz"
            jump_block = branch.zero
            maybe_next_block = branch.non_zero
        self._add_op(
            ops.IntrinsicOp(
                op_code=op_code,
                immediates=[self._get_block_name(jump_block)],
                source_location=branch.source_location,
                consumes=1,
                produces=0,
            )
        )
        self.maybe_branch_or_fallthrough(maybe_next_block, branch.source_location)

    def maybe_branch_or_fallthrough(
        self, maybe_next_block: models.BasicBlock, source_location: SourceLocation | None
    ) -> None:
        block_name = self._get_block_name(maybe_next_block)
        if self.next_block is not maybe_next_block:
            self._add_op(
                ops.IntrinsicOp(
                    op_code="b",
                    immediates=[block_name],
                    source_location=source_location,
                    consumes=0,
                    produces=0,
                )
            )
        else:
            self._add_op(
                ops.Comment(
                    f"Implicit fall through to {block_name}", source_location=source_location
                )
            )

    def visit_goto(self, goto: models.Goto) -> None:
        self.maybe_branch_or_fallthrough(goto.target, goto.source_location)

    def visit_goto_nth(self, goto_nth: models.GotoNth) -> None:
        block_labels = [self._get_block_name(block) for block in goto_nth.blocks]
        goto_nth.value.accept(self)
        self._add_op(
            ops.IntrinsicOp(
                op_code="switch",
                immediates=block_labels,
                source_location=goto_nth.source_location,
                consumes=1,
                produces=0,
            )
        )
        self.maybe_branch_or_fallthrough(goto_nth.default, goto_nth.source_location)

    def visit_switch(self, switch: models.Switch) -> None:
        blocks = list[str]()
        for case, block in switch.cases.items():
            case.accept(self)
            block_name = self._get_block_name(block)
            blocks.append(block_name)
        switch.value.accept(self)

        self._add_op(
            ops.IntrinsicOp(
                op_code="match",
                immediates=blocks,
                source_location=switch.source_location,
                consumes=len(switch.cases) + 1,
                produces=0,
            )
        )
        self.maybe_branch_or_fallthrough(switch.default, switch.source_location)

    def visit_subroutine_return(self, retsub: models.SubroutineReturn) -> None:
        for r in retsub.result:
            r.accept(self)
        self._add_op(
            ops.IntrinsicOp(
                op_code="return",
                source_location=retsub.source_location,
                consumes=len(retsub.result),
                produces=0,
            )
            if self.is_main
            else ops.RetSub(source_location=retsub.source_location, returns=len(retsub.result))
        )

    def visit_program_exit(self, exit_: models.ProgramExit) -> None:
        exit_.result.accept(self)
        self._add_op(
            ops.IntrinsicOp(
                op_code="return",
                source_location=exit_.source_location,
                consumes=0,
                produces=0,
            )
        )

    def visit_fail(self, fail: models.Fail) -> None:
        self._add_op(
            ops.IntrinsicOp(
                op_code="err",
                comment=fail.comment,
                source_location=fail.source_location,
                consumes=0,
                produces=0,
            )
        )

    def lower_block_to_teal(
        self, block: models.BasicBlock, next_block: models.BasicBlock | None
    ) -> ops.MemoryBasicBlock:
        self.next_block = next_block
        self.current_ops = list[ops.BaseOp]()
        for op in block.all_ops:
            assert not isinstance(op, models.Phi)
            self.active_op = op
            op.accept(self)
        block_name = self._get_block_name(block)
        predecessors = [self._get_block_name(b) for b in block.predecessors]
        successors = [self._get_block_name(b) for b in block.successors]
        return ops.MemoryBasicBlock(
            block_name=block_name,
            ops=self.current_ops,
            predecessors=predecessors,
            successors=successors,
            source_location=block.source_location,
        )


def lower_subroutine_to_teal(
    context: ProgramCodeGenContext,
    subroutine_names: dict[models.Subroutine, str],
    subroutine: models.Subroutine,
    *,
    is_main: bool,
) -> list[ops.MemoryBasicBlock]:
    builder = MemoryIrBuilder(
        context=context,
        current_subroutine=subroutine,
        is_main=is_main,
        subroutine_names=subroutine_names,
    )
    blocks = list[ops.MemoryBasicBlock]()
    last_block = subroutine.entry
    for block in subroutine.body[1:]:
        blocks.append(builder.lower_block_to_teal(last_block, block))
        last_block = block
    blocks.append(builder.lower_block_to_teal(subroutine.body[-1], None))
    return blocks


def get_short_subroutine_names(program: models.Program) -> dict[models.Subroutine, str]:
    """Return a mapping of unique TEAL names for all subroutines in program, while attempting
    to use the shortest name possible"""
    names = dict[models.Subroutine, str]()
    names[program.main] = "main"
    seen_names = set(names.values())
    for subroutine in program.subroutines:
        name: str
        if subroutine.method_name not in seen_names:
            name = subroutine.method_name
        elif (
            class_prefixed := f"{subroutine.class_name}.{subroutine.method_name}"
        ) not in seen_names:
            name = class_prefixed
        else:
            name = subroutine.full_name
        assert name not in seen_names
        names[subroutine] = name
        seen_names.add(name)

    return names


def lower_program_ir_to_memory_ir(
    context: ProgramCodeGenContext,
) -> Iterable[ops.MemorySubroutine]:
    program = context.program
    subroutine_names = get_short_subroutine_names(program)

    for subroutine in program.all_subroutines:
        is_main = subroutine is program.main
        body = lower_subroutine_to_teal(
            context, subroutine_names, subroutine, is_main=subroutine is program.main
        )
        preamble = ops.MemoryBasicBlock(
            subroutine_names[subroutine],
            ops=[],
            predecessors=[],
            successors=[body[0].block_name],
            source_location=subroutine.source_location or body[0].source_location,
        )
        if not is_main:
            preamble.ops.append(
                ops.Proto(
                    parameters=len(subroutine.parameters),
                    returns=len(subroutine.returns),
                    source_location=subroutine.source_location,
                )
            )
        yield ops.MemorySubroutine(
            signature=ops.Signature(
                name=subroutine.full_name,
                parameters=[
                    ops.Parameter(local_id=p.local_id, atype=p.atype)
                    for p in subroutine.parameters
                ],
                returns=subroutine.returns,
            ),
            is_main=is_main,
            preamble=preamble,
            body=body,
        )


def compile_program_to_teal(
    context: CompileContext, contract: models.Contract, program: models.Program
) -> CompiledProgram:
    call_graph = CallGraph.build(program)
    cg_context = attrs_extend(
        ProgramCodeGenContext,
        context,
        contract=contract,
        program=program,
        call_graph=call_graph,
    )
    subroutines = list(lower_program_ir_to_memory_ir(cg_context))
    global_stack_assignment(cg_context, subroutines)

    cg_context_without_debug = attrs.evolve(
        cg_context, options=attrs.evolve(context.options, debug_level=0)
    )
    src = emit_memory_ir_as_teal(cg_context_without_debug, subroutines)
    debug_src = (
        emit_memory_ir_as_teal(cg_context, subroutines) if context.options.debug_level else None
    )
    return CompiledProgram(src=src, debug_src=debug_src)


def compile_ir_to_teal(context: CompileContext, ir: models.Contract) -> CompiledContract:
    return CompiledContract(
        approval_program=compile_program_to_teal(context, ir, ir.approval_program),
        clear_program=compile_program_to_teal(context, ir, ir.clear_program),
        metadata=ir.metadata,
    )
