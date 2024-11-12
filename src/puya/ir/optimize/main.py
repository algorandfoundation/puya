from collections.abc import Callable, Iterable
from copy import deepcopy
from pathlib import Path

import attrs

from puya import log
from puya.ir import models
from puya.ir.optimize.assignments import copy_propagation
from puya.ir.optimize.collapse_blocks import remove_empty_blocks, remove_linear_jump
from puya.ir.optimize.compiled_reference import replace_compiled_references
from puya.ir.optimize.constant_propagation import constant_replacer
from puya.ir.optimize.context import IROptimizeContext
from puya.ir.optimize.control_op_simplification import simplify_control_ops
from puya.ir.optimize.dead_code_elimination import (
    remove_calls_to_no_op_subroutines,
    remove_unreachable_blocks,
    remove_unused_ops,
    remove_unused_subroutines,
    remove_unused_variables,
)
from puya.ir.optimize.inner_txn import inner_txn_field_replacer
from puya.ir.optimize.intrinsic_simplification import intrinsic_simplifier
from puya.ir.optimize.repeated_code_elimination import repeated_expression_elimination
from puya.ir.to_text_visitor import output_artifact_ir_to_path

MAX_PASSES = 100
SubroutineOptimizerCallable = Callable[[IROptimizeContext, models.Subroutine], bool]
logger = log.get_logger(__name__)


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

    def optimize(self, context: IROptimizeContext, ir: models.Subroutine) -> bool:
        did_modify = self._optimize(context, ir)
        if did_modify:
            while self.loop and self._optimize(context, ir):
                pass
        return did_modify


def get_subroutine_optimizations(optimization_level: int) -> Iterable[SubroutineOptimization]:
    if optimization_level:
        return [
            SubroutineOptimization.from_function(constant_replacer, loop=True),
            SubroutineOptimization.from_function(copy_propagation),
            SubroutineOptimization.from_function(intrinsic_simplifier, loop=True),
            SubroutineOptimization.from_function(remove_unused_variables),
            SubroutineOptimization.from_function(remove_unused_ops),
            SubroutineOptimization.from_function(inner_txn_field_replacer),
            SubroutineOptimization.from_function(replace_compiled_references),
            SubroutineOptimization.from_function(simplify_control_ops, loop=True),
            SubroutineOptimization.from_function(remove_linear_jump),
            SubroutineOptimization.from_function(remove_empty_blocks),
            SubroutineOptimization.from_function(remove_unreachable_blocks),
            SubroutineOptimization.from_function(repeated_expression_elimination),
            SubroutineOptimization.from_function(remove_calls_to_no_op_subroutines),
        ]
    else:
        return [
            SubroutineOptimization.from_function(constant_replacer, loop=True),
            SubroutineOptimization.from_function(remove_unused_variables),
            SubroutineOptimization.from_function(inner_txn_field_replacer),
            SubroutineOptimization.from_function(replace_compiled_references),
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
    context: IROptimizeContext,
    artifact_ir: models.ModuleArtifact,
    output_ir_base_path: Path | None = None,
) -> models.ModuleArtifact:
    # TODO: program optimizer for trivial function inliner
    pipeline = get_subroutine_optimizations(context.options.optimization_level)
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
        artifact_ir = deepcopy(artifact_ir)
        for subroutine in artifact_ir.all_subroutines():
            logger.debug(f"Optimizing subroutine {subroutine.full_name}")
            if pass_num == 1:
                logger.debug("Splitting parallel copies prior to optimization")
                _split_parallel_copies(subroutine)
            for optimizer in pipeline:
                logger.debug(f"Optimizer: {optimizer.desc}")
                if optimizer.optimize(context, subroutine):
                    contract_modified = True
                subroutine.validate_with_ssa()
        if remove_unused_subroutines(context, artifact_ir):
            contract_modified = True
        if not contract_modified:
            logger.debug(f"No optimizations performed in pass {pass_num}, ending loop")
            break
        if output_ir_base_path:
            ir_path = output_ir_base_path.with_suffix(f".ssa.opt_pass_{pass_num}.ir")
            output_artifact_ir_to_path(artifact_ir, ir_path)
    return artifact_ir
