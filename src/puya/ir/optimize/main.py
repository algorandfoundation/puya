from collections.abc import Callable, Collection, Iterable

import attrs

from puya import log
from puya.context import ArtifactCompileContext
from puya.ir import models
from puya.ir.optimize.assignments import copy_propagation
from puya.ir.optimize.collapse_blocks import remove_empty_blocks, remove_linear_jump
from puya.ir.optimize.compiled_reference import replace_compiled_references
from puya.ir.optimize.constant_propagation import constant_replacer
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.optimize.control_op_simplification import simplify_control_ops
from puya.ir.optimize.dead_code_elimination import (
    remove_unreachable_blocks,
    remove_unused_subroutines,
    remove_unused_variables,
)
from puya.ir.optimize.inlining import analyse_subroutines_for_inlining, perform_subroutine_inlining
from puya.ir.optimize.inner_txn import inner_txn_field_replacer
from puya.ir.optimize.intrinsic_simplification import intrinsic_simplifier
from puya.ir.optimize.itxn_field_elision import elide_itxn_field_calls
from puya.ir.optimize.repeated_code_elimination import repeated_expression_elimination
from puya.ir.optimize.repeated_loads_elimination import (
    constant_reads_and_unobserved_writes_elimination,
)
from puya.ir.to_text_visitor import render_program
from puya.utils import attrs_extend

MAX_PASSES = 100
SubroutineOptimizerCallable = Callable[[IROptimizationContext, models.Subroutine], bool]
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
        func_desc = func_name.replace("_", " ").title().strip()
        return SubroutineOptimization(id=func_name, desc=func_desc, optimize=func, loop=loop)

    def optimize(self, context: IROptimizationContext, ir: models.Subroutine) -> bool:
        did_modify = self._optimize(context, ir)
        if did_modify:
            while self.loop and self._optimize(context, ir):
                pass
        return did_modify


def get_subroutine_optimizations(optimization_level: int) -> Iterable[SubroutineOptimization]:
    if optimization_level:
        return [
            SubroutineOptimization.from_function(perform_subroutine_inlining),
            SubroutineOptimization.from_function(_split_parallel_copies),
            SubroutineOptimization.from_function(constant_replacer),
            SubroutineOptimization.from_function(copy_propagation),
            SubroutineOptimization.from_function(elide_itxn_field_calls),
            SubroutineOptimization.from_function(remove_unused_variables),
            SubroutineOptimization.from_function(intrinsic_simplifier),
            SubroutineOptimization.from_function(inner_txn_field_replacer),
            SubroutineOptimization.from_function(replace_compiled_references),
            SubroutineOptimization.from_function(simplify_control_ops, loop=True),
            SubroutineOptimization.from_function(remove_linear_jump),
            SubroutineOptimization.from_function(remove_empty_blocks),
            SubroutineOptimization.from_function(remove_unreachable_blocks),
            SubroutineOptimization.from_function(repeated_expression_elimination),
            SubroutineOptimization.from_function(constant_reads_and_unobserved_writes_elimination),
        ]
    else:
        return [
            SubroutineOptimization.from_function(perform_subroutine_inlining),
            SubroutineOptimization.from_function(_split_parallel_copies),
            SubroutineOptimization.from_function(constant_replacer),
            SubroutineOptimization.from_function(remove_unused_variables),
            SubroutineOptimization.from_function(inner_txn_field_replacer),
            SubroutineOptimization.from_function(replace_compiled_references),
        ]


def _split_parallel_copies(_ctx: ArtifactCompileContext, sub: models.Subroutine) -> bool:
    # not an optimisation, but allows optimisations to assume there are no ValueTuples,
    # which makes finding copy assignments straight forward
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
    return any_modified


def optimize_program_ir(
    context: ArtifactCompileContext,
    program: models.Program,
    *,
    routable_method_ids: Collection[str] | None,
    qualifier: str,
) -> None:
    pipeline = [
        o
        for o in get_subroutine_optimizations(context.options.optimization_level)
        if o.id not in context.options.disabled_optimizations
    ]
    opt_context = attrs_extend(IROptimizationContext, context, expand_all_bytes=False)
    for pass_num in range(1, MAX_PASSES + 1):
        program_modified = False
        logger.debug(f"Begin optimization pass {pass_num}/{MAX_PASSES}")
        analyse_subroutines_for_inlining(opt_context, program, routable_method_ids)
        for subroutine in program.all_subroutines:
            logger.debug(f"Optimizing subroutine {subroutine.id}")
            for optimizer in pipeline:
                logger.debug(f"Optimizer: {optimizer.desc}")
                if optimizer.optimize(opt_context, subroutine):
                    program_modified = True
            subroutine.validate_with_ssa()
        if remove_unused_subroutines(program):
            logger.debug("Unused subroutines removed")
            program_modified = True
        if not program_modified:
            logger.debug(f"No optimizations performed in pass {pass_num}, ending loop")
            break
        if context.options.output_optimization_ir:
            render_program(context, program, qualifier=qualifier)
