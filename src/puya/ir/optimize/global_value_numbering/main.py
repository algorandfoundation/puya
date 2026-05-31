from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize._utils import SSAReadTracker, compute_dominator_tree
from puya.ir.optimize.global_value_numbering.assert_elimination import eliminate_redundant_asserts
from puya.ir.optimize.global_value_numbering.builder import number_values
from puya.ir.optimize.global_value_numbering.constant_materialization import materialize_constants
from puya.ir.optimize.global_value_numbering.redundancy_elimination import (
    eliminate_redundant_computations,
)


def global_value_numbering(context: CompileContext, subroutine: models.Subroutine) -> bool:
    dom_tree = compute_dominator_tree(subroutine)
    tables = number_values(subroutine, dom_tree)
    ssa_reads = SSAReadTracker()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)
    materialized = materialize_constants(
        tables,
        subroutine,
        dom_tree.root,
        ssa_reads,
        expand_all_bytes=context.options.expand_all_bytes,
    )
    asserts_removed = eliminate_redundant_asserts(tables, dom_tree, ssa_reads)
    eliminated = eliminate_redundant_computations(subroutine, tables, dom_tree, ssa_reads)
    modified = materialized or asserts_removed or eliminated
    return modified
