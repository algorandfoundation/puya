"""Unit tests for global value numbering passes."""

from collections.abc import Callable

from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize.global_value_numbering import global_value_numbering
from puya.ir.to_text_visitor import TextEmitter, render_subroutine
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
      - In block_b: a#1 and b#1 both with args (n from entry, a#2 from block_bc)
        — same vns_dict; a#1 becomes the leader, b#1 the non-leader.
      - In block_bc: b#2 and a#2 both with args (b#1 from block_b, n from block_other)
        — same vns_dict; b#2 becomes the leader, a#2 the non-leader.

    After _build_equivalence_sets removes the non-leaders, the surviving leader
    phis a#1 and b#2 cross-reference each other only through the removed
    non-leader registers:
      - a#1's back-edge arg is a#2, which resolves to b#2.
      - b#2's arg from block_b is b#1, which resolves to a#1.

    Only via register_replacements resolution does _refine_phi_congruence add the
    edges a#1 → b#2 and b#2 → a#1, discover the SCC, and merge both to the
    external parameter n. Without the resolution the SCC is missed and the two
    leader phis survive the pass with their args rewritten by MemoryReplacer to
    point directly at each other.
    """
    loc = SourceLocation(file=None, line=1)
    n = models.Parameter(
        name="n",
        version=0,
        ir_type=PrimitiveIRType.uint64,
        implicit_return=False,
        source_location=None,
    )

    # block_b ↔ block_bc reference each other through terminators, phi through-blocks
    # and predecessors; create them as bare placeholders so the rest can refer to
    # their identity, then patch in their content afterward.
    block1 = models.BasicBlock(id=1, source_location=loc)
    block3 = models.BasicBlock(id=3, source_location=loc)

    entry_block = models.BasicBlock(
        id=0,
        terminator=models.Goto(target=block1, source_location=loc),
        source_location=loc,
    )
    block_other = models.BasicBlock(
        id=2,
        terminator=models.Goto(target=block3, source_location=loc),
        predecessors=dict.fromkeys([block1]),
        source_location=loc,
    )
    exit_block = models.BasicBlock(
        id=4,
        terminator=models.SubroutineReturn(result=[], source_location=loc),
        predecessors=dict.fromkeys([block3]),
        source_location=loc,
    )

    block1_phi_args: Callable[[], list[models.PhiArgument]] = lambda: [  # noqa: E731
        models.PhiArgument(value=n, through=entry_block),
        models.PhiArgument(value=_reg("a", 2), through=block3),
    ]
    block1.phis = [
        models.Phi(register=_reg("a", 1), args=block1_phi_args()),
        models.Phi(register=_reg("b", 1), args=block1_phi_args()),
    ]
    block1.terminator = models.ConditionalBranch(
        source_location=loc,
        condition=n,
        non_zero=block3,
        zero=block_other,
    )
    block1.set_predecessors([entry_block, block3])

    block3_phi_args: Callable[[], list[models.PhiArgument]] = lambda: [  # noqa: E731
        models.PhiArgument(value=_reg("b", 1), through=block1),
        models.PhiArgument(value=n, through=block_other),
    ]
    block3.phis = [
        models.Phi(register=_reg("b", 2), args=block3_phi_args()),
        models.Phi(register=_reg("a", 2), args=block3_phi_args()),
    ]
    block3.terminator = models.ConditionalBranch(
        condition=n,
        zero=exit_block,
        non_zero=block1,
        source_location=loc,
    )
    block3.set_predecessors([block1, block_other])

    sub = models.Subroutine(
        id="test",
        short_name="test",
        parameters=[n],
        returns=[],
        body=[entry_block, block1, block_other, block3, exit_block],
        inline=None,
        source_location=loc,
    )

    context = CompileContext(
        options=PuyaOptions(),
        compilation_set={},
        sources_by_path={},
    )

    before_opt = _render_subroutine(sub)
    assert (
        before_opt
        == """subroutine test(n: uint64) -> void:
    block@0: // L1
        goto block@1
    block@1: // L1
        let a#1: uint64 = φ(n#0 <- block@0, a#2 <- block@3)
        let b#1: uint64 = φ(n#0 <- block@0, a#2 <- block@3)
        goto n#0 ? block@3 : block@2
    block@2: // L1
        goto block@3
    block@3: // L1
        let b#2: uint64 = φ(b#1 <- block@1, n#0 <- block@2)
        let a#2: uint64 = φ(b#1 <- block@1, n#0 <- block@2)
        goto n#0 ? block@1 : block@4
    block@4: // L1
        return """
    )
    # GVN defers SCC discovery when register_replacements is non-empty after
    # build_replacements (to avoid creating replacement chains), so we loop until
    # the pass reaches a fixed point — mirroring what the outer optimisation loop does.
    modified = False
    while global_value_numbering(context, sub):
        modified = True
    after_op = _render_subroutine(sub)
    assert modified is True
    assert before_opt != after_op
    assert (
        after_op
        == """subroutine test(n: uint64) -> void:
    block@0: // L1
        goto block@1
    block@1: // L1
        goto n#0 ? block@3 : block@2
    block@2: // L1
        goto block@3
    block@3: // L1
        goto n#0 ? block@1 : block@4
    block@4: // L1
        return """
    )
    remaining_phis = [phi for block in sub.body for phi in block.phis]
    assert len(remaining_phis) == 0


def _render_subroutine(sub: models.Subroutine) -> str:
    emitter = TextEmitter()
    render_subroutine(emitter, sub)
    rendered = "\n".join(emitter.lines)
    return rendered
