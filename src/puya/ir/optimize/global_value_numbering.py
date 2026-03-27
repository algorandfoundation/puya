"""Global Value Numbering (GVN) for Puya IR.

Hash-based GVN that assigns a canonical value number (VN) to every SSA definition,
then eliminates redundant computations where a dominated definition has the same VN
as an earlier dominating one.

Complementary to the existing CSE pass (repeated_code_elimination.py): CSE catches
syntactically identical expressions cheaply; GVN reasons about value identity through
operand VNs and catches deeper equivalences (e.g. expressions with different operand
registers that hold the same value, commutative reorderings, redundant phis).

References:
    - Briggs, Cooper, Simpson. "Value Numbering." Software -- Practice and Experience, 1997.
    - Cooper & Torczon, Engineering a Compiler, 2nd ed., S8.4-8.5.

Correctness:
    1. Soundness: only pure, deterministic ops are numbered; VN equality requires
       structural match on (operator, VN(operands)); phi redundancy requires all args
       to have the same VN.
    2. Dominance: preorder dominator-tree walk ensures replacements only reference
       registers from dominating blocks.
    3. Conservative default: anything not explicitly handled gets a fresh VN.
"""

import itertools
import typing
from collections.abc import Mapping, Sequence, Set

import attrs
import networkx as nx  # type: ignore[import-untyped]
from immutabledict import immutabledict

from puya import log
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import (
    encodings,
    models,
    types_ as types,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import compute_dominator_tree
from puya.ir.optimize.dead_code_elimination import PURE_AVM_OPS
from puya.ir.visitor_mem_replacer import MemoryReplacer
from puya.utils import symmetric_mapping

logger = log.get_logger(__name__)

VN: typing.TypeAlias = int

# Commutative AVM ops: sorting operand VNs lets us recognise a+b == b+a.
_COMMUTATIVE_OPS: typing.Final[Set[AVMOp]] = frozenset(
    [
        # uint64 arithmetic
        AVMOp.add,
        AVMOp.mul,
        # uint64 comparison
        AVMOp.eq,
        AVMOp.neq,
        # uint64 bitwise
        AVMOp.bitwise_and,
        AVMOp.bitwise_or,
        AVMOp.bitwise_xor,
        # uint64 logical
        AVMOp.and_,
        AVMOp.or_,
        # wide uint64 arithmetic
        AVMOp.addw,
        AVMOp.mulw,
        # bytes arithmetic
        AVMOp.add_bytes,
        AVMOp.mul_bytes,
        # bytes comparison
        AVMOp.eq_bytes,
        AVMOp.neq_bytes,
        # bytes bitwise
        AVMOp.bitwise_and_bytes,
        AVMOp.bitwise_or_bytes,
        AVMOp.bitwise_xor_bytes,
    ]
)

# Ordering ops: swapping operands requires mirroring the predicate.
# Sorting operand VNs (as with commutative ops) and adjusting the op code
# lets us recognise a<b == b>a, a<=b == b>=a, etc.
_MIRROR_OPS: typing.Final = symmetric_mapping(
    (AVMOp.lt, AVMOp.gt),
    (AVMOp.lte, AVMOp.gte),
    (AVMOp.lt_bytes, AVMOp.gt_bytes),
    (AVMOp.lte_bytes, AVMOp.gte_bytes),
)

# Inverse comparisons: !(a < b) == (a >= b), etc.
# Used for negation-aware numbering: when GVN sees !(comparison),
# it returns the inverse comparison's expression key.
_INVERSE_COMPARISONS: typing.Final = symmetric_mapping(
    (AVMOp.lt, AVMOp.gte),
    (AVMOp.gt, AVMOp.lte),
    (AVMOp.eq, AVMOp.neq),
    (AVMOp.lt_bytes, AVMOp.gte_bytes),
    (AVMOp.gt_bytes, AVMOp.lte_bytes),
    (AVMOp.eq_bytes, AVMOp.neq_bytes),
)


@attrs.frozen(kw_only=True)
class _ValueKey:
    """Base class for canonical value expression keys used in the GVN expression table."""


@attrs.frozen(kw_only=True)
class _IntrinsicKey(_ValueKey):
    op: AVMOp
    immediates: tuple[str | int, ...]
    arg_vns: tuple[VN, ...]


@attrs.frozen(kw_only=True)
class _ExtractKey(_ValueKey):
    base_vn: VN
    base_type: types.EncodedType
    index_vns: tuple[VN, ...]
    check_bounds: bool


@attrs.frozen(kw_only=True)
class _ReplaceKey(_ValueKey):
    base_vn: VN
    base_type: types.EncodedType
    index_vns: tuple[VN, ...]
    value_vn: VN


@attrs.frozen(kw_only=True)
class _ArrayLengthKey(_ValueKey):
    base_vn: VN
    base_type: types.IRType
    array_encoding: encodings.ArrayEncoding


@attrs.frozen(kw_only=True)
class _EncodeKey(_ValueKey):
    encoding: encodings.Encoding
    value_vns: tuple[VN, ...]
    values_type: types.IRType | types.TupleIRType


@attrs.frozen(kw_only=True)
class _DecodeKey(_ValueKey):
    encoding: encodings.Encoding
    value_vn: VN
    ir_type: types.IRType | types.TupleIRType


@attrs.frozen(kw_only=True)
class _CallSubKey(_ValueKey):
    target_id: str
    arg_vns: tuple[VN, ...]


@attrs.frozen(kw_only=True)
class _PhiKey(_ValueKey):
    block: models.BasicBlock
    args: immutabledict[models.BasicBlock, VN]


@attrs.define
class _ScopeDelta:
    """Keys added to each scoped table during a scope, removed on pop."""

    register_keys: list[models.Register] = attrs.field(factory=list)
    expr_keys: list[_ValueKey] = attrs.field(factory=list)


class _GVNTables:
    """Value numbering state, supporting scoped save/restore for dominator-tree walk."""

    def __init__(self) -> None:
        self._vn_counter = itertools.count()
        # VN assigned to each SSA register
        self._register_vn = dict[models.Register, VN]()
        # Canonical expression -> (VN, representative register(s))
        self._expr_table = dict[_ValueKey, tuple[VN, Sequence[models.Register]]]()
        # --- Unscoped tables (globally valid, never rolled back) ---
        # VN -> the first register assigned that VN (the representative).
        # VNs are globally unique (monotonic counter), so entries never collide.
        self._vn_to_register = dict[VN, models.Register]()
        # Constant value (frozen) -> VN. Constants are immutable and globally valid.
        self._const_vn = dict[object, VN]()
        # VN -> canonical comparison expression key.
        # Used by negation-aware numbering to resolve !(comparison) to the
        # inverse comparison's expression key.
        self._comparison_exprs = dict[VN, _IntrinsicKey]()
        # --- Scope management for dominator-tree walk ---
        # Only _register_vn and _expr_table are scoped: entries added in each
        # scope are tracked so they can be removed on pop_scope().
        self._scope_stack = list[_ScopeDelta]()

    def fresh_vn(self) -> VN:
        return next(self._vn_counter)

    def set_register_vn(self, reg: models.Register, vn: VN) -> None:
        if self._scope_stack and reg not in self._register_vn:
            self._scope_stack[-1].register_keys.append(reg)
        self._register_vn[reg] = vn
        # First register to receive this VN becomes the representative.
        # Unscoped: VNs are globally unique (monotonic counter), so entries
        # from popped scopes never collide with new ones.
        if vn not in self._vn_to_register:
            self._vn_to_register[vn] = reg

    def lookup_expr(self, expr: _ValueKey) -> tuple[VN, Sequence[models.Register]] | None:
        return self._expr_table.get(expr)

    def store_expr(self, expr: _ValueKey, vn: VN, targets: Sequence[models.Register]) -> None:
        if self._scope_stack and expr not in self._expr_table:
            self._scope_stack[-1].expr_keys.append(expr)
        self._expr_table[expr] = (vn, targets)

    def representative(self, vn: VN) -> models.Register | None:
        return self._vn_to_register.get(vn)

    def record_comparison(self, vn: VN, key: _IntrinsicKey) -> None:
        self._comparison_exprs[vn] = key

    def get_comparison_expr(self, vn: VN) -> _IntrinsicKey | None:
        return self._comparison_exprs.get(vn)

    def lookup_vn(self, value: models.Value) -> VN:
        """Get the VN for any Value (register or constant).

        If a register has not been numbered yet (e.g. a phi argument from a back edge),
        it is conservatively assigned a fresh VN.
        """
        if isinstance(value, models.Register):
            existing = self._register_vn.get(value)
            if existing is not None:
                return existing
            # Back-edge or otherwise not-yet-visited register: fresh VN
            vn = self.fresh_vn()
            self.set_register_vn(value, vn)
            return vn
        # Constants: intern by frozen value so identical constants share a VN.
        # Unscoped: constants are globally valid and immutable.
        key = value.freeze()
        existing = self._const_vn.get(key)
        if existing is not None:
            return existing
        vn = self.fresh_vn()
        self._const_vn[key] = vn
        return vn

    def push_scope(self) -> None:
        """Begin a new scope for dominator-tree walk."""
        self._scope_stack.append(_ScopeDelta())

    def pop_scope(self) -> None:
        """Remove entries added in the current scope."""
        delta = self._scope_stack.pop()
        for reg in delta.register_keys:
            del self._register_vn[reg]
        for expr in delta.expr_keys:
            del self._expr_table[expr]


def _index_vns(
    tables: _GVNTables, indexes: tuple[int | models.Value, ...]
) -> tuple[int | VN, ...]:
    """Compute VNs for aggregate indexes (ints pass through, Values get numbered)."""
    return tuple(
        tables.lookup_vn(idx) if isinstance(idx, models.Value) else idx for idx in indexes
    )


def _build_value_expr(
    tables: _GVNTables,
    source: models.ValueProvider,
) -> _ValueKey | None:
    """Build a canonical, hashable value expression for a ValueProvider.

    Returns None for side-effecting or unrecognised operations (they get a fresh VN).
    """
    match source:
        case models.Intrinsic(op=op, immediates=immediates, args=args) if (
            args  # TODO: handle no-args by keeping the definition but assigning same VN,
            #             and then using that VN in comparison / algebraic identities
            and op.code in PURE_AVM_OPS
        ):
            arg_vns = tuple(tables.lookup_vn(a) for a in args)
            # Negation-aware numbering: !(comparison) -> inverse comparison.
            # e.g. !(a < b) gets the same key as (a >= b).
            if op == AVMOp.not_ and len(arg_vns) == 1:
                comp = tables.get_comparison_expr(arg_vns[0])
                if comp is not None:
                    inverse_op = _INVERSE_COMPARISONS.get(comp.op)
                    if inverse_op is not None:
                        return _IntrinsicKey(
                            op=inverse_op,
                            immediates=comp.immediates,
                            arg_vns=comp.arg_vns,
                        )
            op_key = op
            if op in _COMMUTATIVE_OPS:
                arg_vns = tuple(sorted(arg_vns))
            elif op in _MIRROR_OPS and arg_vns[0] > arg_vns[1]:
                # Canonicalize ordering ops by sorting operand VNs,
                # mirroring the predicate to preserve semantics.
                # e.g. a<b and b>a get the same canonical key.
                arg_vns = (arg_vns[1], arg_vns[0])
                op_key = _MIRROR_OPS[op]
            return _IntrinsicKey(op=op_key, immediates=tuple(immediates), arg_vns=arg_vns)

        case models.ExtractValue(
            base=base, base_type=base_type, indexes=indexes, check_bounds=check_bounds
        ):
            return _ExtractKey(
                base_vn=tables.lookup_vn(base),
                base_type=base_type,
                index_vns=_index_vns(tables, indexes),
                check_bounds=check_bounds,
            )

        case models.ReplaceValue(base=base, base_type=base_type, indexes=indexes, value=value):
            return _ReplaceKey(
                base_vn=tables.lookup_vn(base),
                base_type=base_type,
                index_vns=_index_vns(tables, indexes),
                value_vn=tables.lookup_vn(value),
            )

        case models.BytesEncode(encoding=encoding, values=values, values_type=values_type):
            return _EncodeKey(
                encoding=encoding,
                value_vns=tuple(tables.lookup_vn(v) for v in values),
                values_type=values_type,
            )

        case models.DecodeBytes(encoding=encoding, value=value, ir_type=ir_type):
            return _DecodeKey(
                encoding=encoding,
                value_vn=tables.lookup_vn(value),
                ir_type=ir_type,
            )

        case models.ArrayLength(
            base=base, base_type=base_type, array_encoding=array_encoding
        ) if not isinstance(base_type, types.SlotType):
            # Only pure when the base is a stack value, not a slot reference.
            return _ArrayLengthKey(
                base_vn=tables.lookup_vn(base),
                base_type=base_type,
                array_encoding=array_encoding,
            )

        case models.InvokeSubroutine(target=target, args=args) if target.pure:
            arg_vns = tuple(tables.lookup_vn(a) for a in args)
            return _CallSubKey(target_id=target.id, arg_vns=arg_vns)

        case _:
            # Side-effecting, non-deterministic, or unrecognised — conservative fresh VN
            return None


def _try_replace(
    target: models.Register,
    candidate: models.Register | None,
    replacements: dict[models.Register, models.Register],
) -> bool:
    """Record a replacement if candidate is a valid substitute for target.

    Checks identity, non-self, and AVM type compatibility.
    Returns True if a replacement was recorded.
    """
    if (
        candidate is not None
        and candidate != target
        and target.ir_type.maybe_avm_type == candidate.ir_type.maybe_avm_type
    ):
        replacements[target] = candidate
        return True
    return False


def _process_phi(
    tables: _GVNTables,
    block: models.BasicBlock,
    phi: models.Phi,
    replacements: dict[models.Register, models.Register],
) -> None:
    """Assign a VN to a phi node's register.

    Redundant phis (all args same VN) are replaced with the representative.
    Non-redundant phis are hashed to detect congruent phis at the same block.
    """
    if not phi.args:
        vn = tables.fresh_vn()
        tables.set_register_vn(phi.register, vn)
        return

    phi_arg_vns = immutabledict[models.BasicBlock, VN](
        (arg.through, tables.lookup_vn(arg.value)) for arg in phi.args
    )

    unique_vns = set(phi_arg_vns.values())
    if len(unique_vns) == 1:
        # Redundant phi: all arguments have the same VN
        (the_vn,) = unique_vns
        tables.set_register_vn(phi.register, the_vn)
        representative = tables.representative(the_vn)
        if _try_replace(phi.register, representative, replacements):
            assert representative is not None
            logger.debug(
                f"GVN: redundant phi {phi.register.local_id}"
                f" -> {representative.local_id} (VN={the_vn})"
            )
        return

    # Non-redundant phi: hash by (block_id, arg_vns) to detect congruent phis
    phi_expr = _PhiKey(block=block, args=phi_arg_vns)
    existing = tables.lookup_expr(phi_expr)
    if existing is not None:
        existing_vn, (existing_reg,) = existing
        tables.set_register_vn(phi.register, existing_vn)
        if _try_replace(phi.register, existing_reg, replacements):
            logger.debug(
                f"GVN: congruent phi {phi.register.local_id}"
                f" -> {existing_reg.local_id} (VN={existing_vn})"
            )
    else:
        vn = tables.fresh_vn()
        tables.set_register_vn(phi.register, vn)
        tables.store_expr(phi_expr, vn, [phi.register])


def _process_assignment(
    tables: _GVNTables,
    assignment: models.Assignment,
    replacements: dict[models.Register, models.Register],
) -> None:
    """Assign VNs to an assignment's target registers.

    If the source is a register (copy), propagate its VN.
    If the source is a pure expression and a matching VN already exists,
    mark the target for replacement.
    Otherwise, assign a fresh VN.
    """
    source = assignment.source

    # Copy assignment: propagate VN directly
    if isinstance(source, models.Register) and len(assignment.targets) == 1:
        target = assignment.targets[0]
        vn = tables.lookup_vn(source)
        tables.set_register_vn(target, vn)
        _try_replace(target, tables.representative(vn), replacements)
        return

    targets = assignment.targets
    expr = _build_value_expr(tables, source)
    if expr is None:
        # Not a pure expression — fresh VN per target
        for reg in targets:
            tables.set_register_vn(reg, tables.fresh_vn())
        return

    existing = tables.lookup_expr(expr)
    if existing is not None:
        existing_vn, existing_regs = existing
        if len(existing_regs) != len(targets):
            raise InternalError(
                f"GVN: expression arity mismatch:" f" {len(existing_regs)} vs {len(targets)}"
            )
        for target, existing_reg in zip(targets, existing_regs, strict=True):
            tables.set_register_vn(target, tables.lookup_vn(existing_reg))
            if _try_replace(target, existing_reg, replacements):
                logger.debug(
                    f"GVN: redundant expr {target.local_id}"
                    f" -> {existing_reg.local_id} (VN={existing_vn})"
                )
    else:
        vn = tables.fresh_vn()
        for target in targets:
            tables.set_register_vn(target, tables.fresh_vn())
        tables.store_expr(expr, vn, targets)

    # Track comparison expressions for negation-aware numbering.
    # Single-target only — comparisons always produce one result.
    if len(targets) == 1 and isinstance(expr, _IntrinsicKey) and expr.op in _INVERSE_COMPARISONS:
        tables.record_comparison(tables.lookup_vn(targets[0]), expr)


def _process_block(
    tables: _GVNTables,
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    block: models.BasicBlock,
    replacements: dict[models.Register, models.Register],
) -> None:
    """Process a single block in the dominator-tree preorder walk.

    Scopes the tables so that entries added in this block are visible to
    dominated children but rolled back when returning to siblings.
    """
    tables.push_scope()

    for phi in block.phis:
        _process_phi(tables, block, phi, replacements)

    for op in block.ops:
        if isinstance(op, models.Assignment):
            _process_assignment(tables, op, replacements)

    for child in dom_tree.get(block, []):
        _process_block(tables, dom_tree, child, replacements)

    tables.pop_scope()


def _apply_replacements(
    subroutine: models.Subroutine,
    replacements: dict[models.Register, models.Register],
) -> None:
    """Apply the computed replacements: remove dead definitions and substitute uses."""
    # Both the hash-based pass and SCC pass always replace with a VN representative,
    # which is never itself a replacement target, so chains should not form.
    # MemoryReplacer also asserts this — validate here to catch bugs early.
    for target in replacements.values():
        if target in replacements:
            raise InternalError(
                f"GVN: replacement chain detected:"
                f" {target.local_id} -> {replacements[target].local_id}"
            )

    for block in subroutine.body:
        block.phis = [phi for phi in block.phis if phi.register not in replacements]
        block.ops = [
            op
            for op in block.ops
            if not (
                isinstance(op, models.Assignment) and all(t in replacements for t in op.targets)
            )
        ]

    MemoryReplacer.apply(subroutine.body, replacements=replacements)


def _refine_phi_congruence(
    tables: _GVNTables,
    subroutine: models.Subroutine,
    replacements: dict[models.Register, models.Register],
) -> None:
    """Phase 2: Find phi-cycle equivalences that hash-based numbering missed.

    Builds a dependency graph of phis, finds SCCs, and checks if all phis
    in an SCC have the same set of external (non-SCC) argument VNs. If so,
    they're all congruent and can be merged.

    This catches patterns like:
        x = phi(a, y)
        y = phi(b, x)
    where a and b have the same VN — hash-based GVN assigns x and y different
    VNs (due to back-edge conservatism), but SCC analysis reveals they're equal.
    """
    # Collect all phi registers and their phis
    phi_by_register = dict[models.Register, models.Phi]()
    for block in subroutine.body:
        for phi in block.phis:
            phi_by_register[phi.register] = phi

    if not phi_by_register:
        return

    # Build phi dependency graph: edge from P to Q if Q's register is an arg of P
    phi_regs = frozenset(phi_by_register.keys())
    graph = nx.DiGraph()
    for reg in phi_regs:
        graph.add_node(reg)
    for reg, phi in phi_by_register.items():
        for arg in phi.args:
            if arg.value in phi_regs:
                graph.add_edge(reg, arg.value)

    # Find SCCs
    for scc_set in nx.strongly_connected_components(graph):
        if len(scc_set) <= 1:
            continue

        # For each phi in the SCC, collect VNs of external arguments
        # (arguments whose value is NOT a register in this SCC)
        external_vn_sets = dict[models.Register, frozenset[VN]]()
        for reg in scc_set:
            phi = phi_by_register[reg]
            ext_vns = frozenset(
                tables.lookup_vn(arg.value) for arg in phi.args if arg.value not in scc_set
            )
            external_vn_sets[reg] = ext_vns

        # All phis in the SCC must have the same single external VN
        all_ext = set(external_vn_sets.values())
        if len(all_ext) != 1:
            continue
        (common_ext,) = all_ext
        if len(common_ext) != 1:
            raise InternalError(
                "GVN: SCC phis have multiple distinct external VNs"
                " — expected exactly one for structured control flow"
            )

        # All external args resolve to one VN — the whole SCC is equivalent
        (target_vn,) = common_ext
        representative = tables.representative(target_vn)
        if representative is None:
            raise InternalError(f"GVN: no representative register for VN={target_vn}")

        for reg in sorted(scc_set, key=lambda r: r.local_id):
            tables.set_register_vn(reg, target_vn)
            if _try_replace(reg, representative, replacements):
                logger.debug(
                    f"GVN: SCC phi congruence {reg.local_id}"
                    f" -> {representative.local_id} (VN={target_vn})"
                )


def _number_values(
    subroutine: models.Subroutine,
) -> tuple[_GVNTables, dict[models.Register, models.Register]]:
    """Phase 1: Assign value numbers to all definitions and find full redundancies."""
    start, dom_tree = compute_dominator_tree(subroutine)

    tables = _GVNTables()
    replacements = dict[models.Register, models.Register]()

    for param in subroutine.parameters:
        tables.set_register_vn(param, tables.fresh_vn())

    _process_block(tables, dom_tree, start, replacements)
    return tables, replacements


def global_value_numbering(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Run GVN on a subroutine.

    Flow: hash-based numbering -> SCC phi congruence -> eliminate.
    """
    tables, replacements = _number_values(subroutine)
    _refine_phi_congruence(tables, subroutine, replacements)

    if not replacements:
        return False

    logger.debug(f"GVN: {len(replacements)} replacement(s) in {subroutine.id}")
    _apply_replacements(subroutine, replacements)
    return True
