"""Unit tests for global value numbering passes."""

from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize.global_value_numbering import global_value_numbering
from puya.ir.types_ import PrimitiveIRType
from puya.options import PuyaOptions
from puya.parse import SourceLocation


def _reg(name: str, version: int) -> models.Register:
    return models.Register(
        name=name,
        version=version,
        ir_type=PrimitiveIRType.uint64,
        source_location=None,
    )


def test_global_value_numbering_refines_phi_congruence_via_register_replacements() -> None:
    """End-to-end GVN scenario that exercises register_replacements resolution in SCC analysis.

    The input IR has two pairs of phis that hash-based GVN identifies as congruent:
      - In block_b: leader_a (var 'a') and nonleader_b (var 'b'), both with args
        (n from entry, nonleader_cl from block_bc) — same vns_dict.
      - In block_bc: leader_c (var 'b') and nonleader_cl (var 'a'), both with args
        (nonleader_b from block_b, n from block_other) — same vns_dict.

    After _build_equivalence_sets removes the non-leaders, the surviving leader
    phis cross-reference each other only through the removed non-leader registers:
      - leader_a's back-edge arg is nonleader_cl, which resolves to leader_c.
      - leader_c's arg from block_b is nonleader_b, which resolves to leader_a.

    Only via register_replacements resolution does _refine_phi_congruence add the
    edges leader_a → leader_c and leader_c → leader_a, discover the SCC, and
    merge both to the external parameter n. Without the resolution the SCC is
    missed and the two leader phis survive the pass.
    """
    loc = SourceLocation(file=None, line=1)
    n = models.Parameter(
        name="n",
        version=0,
        ir_type=PrimitiveIRType.uint64,
        implicit_return=False,
        source_location=None,
    )
    leader_a = _reg("a", 1)
    nonleader_b = _reg("b", 1)
    leader_c = _reg("b", 2)
    nonleader_cl = _reg("a", 2)

    # block_b ↔ block_bc reference each other through terminators, phi through-blocks
    # and predecessors; create them as bare placeholders so the rest can refer to
    # their identity, then patch in their content afterward.
    block_b = models.BasicBlock(source_location=loc, id=1)
    block_bc = models.BasicBlock(source_location=loc, id=3)

    entry_block = models.BasicBlock(
        id=0,
        terminator=models.Goto(source_location=loc, target=block_b),
        source_location=loc,
    )
    block_other = models.BasicBlock(
        id=2,
        terminator=models.Goto(source_location=loc, target=block_bc),
        predecessors=dict.fromkeys([block_b]),
        source_location=loc,
    )
    exit_block = models.BasicBlock(
        id=4,
        terminator=models.SubroutineReturn(source_location=loc, result=[]),
        predecessors=dict.fromkeys([block_bc]),
        source_location=loc,
    )

    phi_a = models.Phi(
        register=leader_a,
        args=[
            models.PhiArgument(value=n, through=entry_block),
            models.PhiArgument(value=nonleader_cl, through=block_bc),
        ],
    )
    phi_b = models.Phi(
        register=nonleader_b,
        args=[
            models.PhiArgument(value=n, through=entry_block),
            models.PhiArgument(value=nonleader_cl, through=block_bc),
        ],
    )
    phi_c = models.Phi(
        register=leader_c,
        args=[
            models.PhiArgument(value=nonleader_b, through=block_b),
            models.PhiArgument(value=n, through=block_other),
        ],
    )
    phi_cl = models.Phi(
        register=nonleader_cl,
        args=[
            models.PhiArgument(value=nonleader_b, through=block_b),
            models.PhiArgument(value=n, through=block_other),
        ],
    )

    block_b.phis.extend([phi_a, phi_b])
    block_b.terminator = models.ConditionalBranch(
        source_location=loc,
        condition=n,
        non_zero=block_bc,
        zero=block_other,
    )
    block_b.set_predecessors([entry_block, block_bc])

    block_bc.phis.extend([phi_c, phi_cl])
    block_bc.terminator = models.ConditionalBranch(
        source_location=loc,
        condition=n,
        non_zero=block_b,
        zero=exit_block,
    )
    block_bc.set_predecessors([block_b, block_other])

    sub = models.Subroutine(
        id="test",
        short_name="test",
        parameters=[n],
        returns=[],
        body=[entry_block, block_b, block_other, block_bc, exit_block],
        inline=None,
        source_location=loc,
    )

    context = CompileContext(
        options=PuyaOptions(),
        compilation_set={},
        sources_by_path={},
    )

    modified = global_value_numbering(context, sub)

    assert modified is True
    assert phi_a not in block_b.phis
    assert phi_c not in block_bc.phis
