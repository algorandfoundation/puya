from collections.abc import Callable, Iterable
from copy import deepcopy
from pathlib import Path

import attrs
import structlog

from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize.arithmetic import arithmetic_simplification
from puya.ir.optimize.assignments import copy_propagation
from puya.ir.optimize.collapse_blocks import remove_empty_blocks, remove_linear_jump
from puya.ir.optimize.constant_propagation import (
    constant_replacer,
    intrinsic_simplifier,
    simplify_conditional_branches,
)
from puya.ir.optimize.dead_code_elimination import (
    remove_unreachable_blocks,
    remove_unused_variables,
)
from puya.ir.to_text_visitor import output_contract_ir_to_path

MAX_PASSES = 100
SubroutineOptimizerCallable = Callable[[CompileContext, models.Subroutine], bool]
logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


@attrs.define(kw_only=True)
class SubroutineOptimization:
    id: str
    desc: str
    _optimize: SubroutineOptimizerCallable
    loop: bool

    @classmethod
    def from_function(
        cls, func: SubroutineOptimizerCallable, *, loop: bool = False
    ) -> "SubroutineOptimization":
        func_name = func.__name__
        func_desc = func_name.replace("_", " ").title()
        return SubroutineOptimization(id=func_name, desc=func_desc, optimize=func, loop=loop)

    def optimize(self, context: CompileContext, ir: models.Subroutine) -> bool:
        did_modify = self._optimize(context, ir)
        if did_modify:
            while self.loop and self._optimize(context, ir):
                pass
        return did_modify


def get_all_optimizations() -> Iterable[SubroutineOptimization]:
    return [
        SubroutineOptimization.from_function(arithmetic_simplification, loop=True),
        SubroutineOptimization.from_function(constant_replacer, loop=True),
        SubroutineOptimization.from_function(copy_propagation),
        SubroutineOptimization.from_function(intrinsic_simplifier),
        SubroutineOptimization.from_function(remove_unused_variables),
        SubroutineOptimization.from_function(simplify_conditional_branches),
        SubroutineOptimization.from_function(remove_linear_jump),
        SubroutineOptimization.from_function(remove_empty_blocks),
        SubroutineOptimization.from_function(remove_unreachable_blocks),
    ]


def _split_parallel_copies(sub: models.Subroutine) -> None:
    any_modified = False
    for block in sub.body:
        ops = list[models.Op]()
        modified = False
        for op in block.ops.copy():
            if isinstance(op, models.Assignment) and isinstance(op.source, models.ValueTuple):
                for dst, src in zip(op.targets, op.source.values, strict=True):
                    modified = True
                    ops.append(
                        models.Assignment(
                            targets=[dst],
                            source=src,
                            source_location=op.source_location,
                        )
                    )
            else:
                ops.append(op)
        if modified:
            any_modified = True
            block.ops = ops
    if any_modified:
        sub.validate_with_ssa()


def optimize_contract_ir(
    context: CompileContext,
    contract_ir: models.Contract,
    output_ir_base_path: Path | None = None,
) -> models.Contract:
    # TODO: program optimizer for trivial function inliner
    pipeline = get_all_optimizations()
    if output_ir_base_path:
        existing = list(
            output_ir_base_path.parent.glob(f"{output_ir_base_path.stem}.ssa.opt_pass_*.ir")
        )
        if existing:
            for remove in existing:
                remove.unlink(missing_ok=True)
    for pass_num in range(1, MAX_PASSES + 1):
        contract_modified = False
        logger.debug(f"Begin optimization pass {pass_num}/{MAX_PASSES}")
        contract_ir = deepcopy(contract_ir)
        for subroutine in contract_ir.all_subroutines():
            logger.debug(f"Optimizing subroutine {subroutine.full_name}")
            if pass_num == 1:
                logger.debug("Splitting parallel copies prior to optimization")
                _split_parallel_copies(subroutine)
            for optimizer in pipeline:
                logger.debug(f"Optimizer: {optimizer.desc}")
                if optimizer.optimize(context, subroutine):
                    contract_modified = True
                subroutine.validate_with_ssa()
        if not contract_modified:
            logger.debug(f"No optimizations performed in pass {pass_num}, ending loop")
            break
        if output_ir_base_path:
            ir_path = output_ir_base_path.with_suffix(f".ssa.opt_pass_{pass_num}.ir")
            output_contract_ir_to_path(contract_ir, ir_path)
    return contract_ir
