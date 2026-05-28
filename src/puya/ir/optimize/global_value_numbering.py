"""
Hash-based GVN with optimistic phi numbering.

Assigns a canonical value number (VN) to every SSA definition via a dominator-tree
walk, then eliminates redundant computations where a dominated definition shares a
VN with a dominating one.

Phi cycles are handled by optimistic iteration (GCC SCC-VN style): back-edge phi
arguments are filtered out on the first walk (treated as the lattice top), and the
walk is re-run with successively-refined VN assignments until the partition over
registers stabilises. Non-redundant phis receive a stable per-phi VN that persists
across iterations to ensure convergence.

References:
    - Briggs, Cooper, Simpson. "Value Numbering." Software -- Practice and Experience, 1997.
      (https://www.cs.tufts.edu/~nr/cs257/archive/keith-cooper/value-numbering.pdf)
    - Cooper & Simpson. "SCC-Based Value Numbering." Rice CS-TR95-261.
    - Cooper & Torczon, Engineering a Compiler, 2nd ed., S8.4-8.5.
"""

import itertools
import typing
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence, Set
from functools import cached_property

import attrs
import networkx as nx  # type: ignore[import-untyped]

from puya import algo_constants, log
from puya.avm import AVMType
from puya.avm_encoding import encode_bytes, encode_varuint
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import (
    encodings,
    models,
    types_ as types,
)
from puya.ir._utils import bfs_block_order, get_bytes_constant
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._intrinsics import (
    COMPILE_TIME_CONSTANT_OPS,
    PURE_AVM_OPS,
    BinarySimplification,
    choose_encoding,
    chop_encoding,
    fold_addw,
    fold_biguint_const_binary_op,
    fold_bytes_const_binary_op,
    fold_bytes_const_unary_op,
    fold_divmodw,
    fold_divw,
    fold_expw,
    fold_extract_uint_n,
    fold_getbit_bytes,
    fold_getbyte,
    fold_mulw,
    fold_replace2,
    fold_setbit_bytes,
    fold_setbit_uint64,
    fold_setbyte,
    fold_uint64_const_binary_op,
    fold_uint64_const_unary_op,
    hash_eval_funcs,
    simplify_bytes_binary_op_one_const,
    simplify_uint64_binary_op_one_const,
    valid_uint64,
)
from puya.ir.optimize._utils import SSAReadTracker, compute_dominator_tree
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.ir.visitor import NoOpIRVisitor, ValueProviderVisitor
from puya.ir.visitor_mem_replacer import MemoryReplacer
from puya.utils import (
    Address,
    biguint_bytes_eval,
    lazy_setdefault,
    method_selector_hash,
    set_add,
    symmetric_mapping,
    unique,
)

logger = log.get_logger(__name__)

VN: typing.TypeAlias = int

# Phi treatment classification produced by ``_classify_phi_sccs`` and consulted
# by ``GVNBlockVisitor.visit_phi``. Phis absent from the treatment map default
# to the standard optimistic redundancy claim; phis mapped to ``_PESSIMISTIC``
# have that claim gated on every arg already being numbered.
_PhiTreatment: typing.TypeAlias = typing.Literal["pessimistic"]
_PESSIMISTIC: _PhiTreatment = "pessimistic"

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
# lets us recognise a<b as equivalent to b>a, a<=b as equivalent to b>=a, etc.
_MIRROR_OPS: typing.Final = symmetric_mapping(
    (AVMOp.lt, AVMOp.gt),
    (AVMOp.lte, AVMOp.gte),
    (AVMOp.lt_bytes, AVMOp.gt_bytes),
    (AVMOp.lte_bytes, AVMOp.gte_bytes),
)

# Inverse comparisons: !(a < b) is equivalent to (a >= b), etc.
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

# Encoding preference for `lookup_or_assign_const` collisions: when two
# `_BytesConstKey`s with the same value but different encodings unify to one VN,
# the more-informative encoding wins. Order follows the enum definition:
# unknown < base16 < base32 < base64 < utf8.
_ENCODING_PREF: typing.Final[Mapping[AVMBytesEncoding, int]] = {
    enc: i for i, enc in enumerate(AVMBytesEncoding)
}


@attrs.frozen(kw_only=True)
class _ProviderKey:
    """Base class for canonical ValueProvider keys used in the GVN expression table."""


@attrs.frozen(kw_only=True)
class _IndexVN:
    """Tagged index for aggregate ops — distinguishes static int indices from dynamic VNs."""

    kind: typing.Literal["static", "value"]
    index: int


@attrs.frozen(kw_only=True)
class _IntrinsicKey(_ProviderKey):
    op: AVMOp
    immediates: tuple[str | int, ...]
    arg_vns: tuple[VN, ...]


@attrs.frozen(kw_only=True)
class _ExtractKey(_ProviderKey):
    base_vn: VN
    base_type: types.EncodedType  # important if there's aliasing through storage
    index_vns: tuple[_IndexVN, ...]
    check_bounds: bool


@attrs.frozen(kw_only=True)
class _ReplaceKey(_ProviderKey):
    base_vn: VN
    base_type: types.EncodedType
    index_vns: tuple[_IndexVN, ...]
    value_vn: VN


@attrs.frozen(kw_only=True)
class _ArrayLengthKey(_ProviderKey):
    base_vn: VN
    base_type: types.IRType


@attrs.frozen(kw_only=True)
class _ArrayPopKey(_ProviderKey):
    base_vn: VN
    base_type: types.EncodedType


@attrs.frozen(kw_only=True)
class _ArrayConcatKey(_ProviderKey):
    base_vn: VN
    base_type: types.EncodedType
    items_vn: VN
    item_encoding: encodings.Encoding
    # num_items: redundant in combination with all other data above


@attrs.frozen(kw_only=True)
class _EncodeKey(_ProviderKey):
    encoding: encodings.Encoding
    value_vns: tuple[VN, ...]
    values_type: types.IRType | types.TupleIRType


@attrs.frozen(kw_only=True)
class _DecodeKey(_ProviderKey):
    encoding: encodings.Encoding
    value_vn: VN
    ir_type: types.IRType | types.TupleIRType


@attrs.frozen(kw_only=True)
class _CallSubKey(_ProviderKey):
    target_id: str
    arg_vns: tuple[VN, ...]


@attrs.frozen(kw_only=True)
class _ConstKey:
    """Base class for canonical "constant" keys used in the GVN expression table."""


@attrs.frozen(kw_only=True)
class _UInt64ConstKey(_ConstKey):
    value: int


@attrs.frozen(kw_only=True)
class _BytesConstKey(_ConstKey):
    value: bytes
    # encoding is metadata only — same bytes with different encodings get the same VN.
    encoding: AVMBytesEncoding = attrs.field(default=AVMBytesEncoding.unknown, eq=False)

    @property
    def as_biguint(self) -> int | None:
        if len(self.value) > 64:
            return None
        return int.from_bytes(self.value, "big", signed=False)


@attrs.frozen(kw_only=True)
class _TemplateVarKey(_ConstKey):
    name: str


if typing.TYPE_CHECKING:
    _IntCounter = itertools.count[int]
else:
    _IntCounter = itertools.count


@attrs.define
class _GVNTables:
    """
    Value numbering state accumulated during pre-order dominator walk,
    makes use of the "Unified has table" approach from Briggs et al.

    Tables persist across optimistic iterations within a single
    :func:`_number_values` call: ``_vn_counter`` and ``_provider_key_to_vns``
    are monotonic, so the same syntactic expression with stable arg VNs gets
    the same VN every iteration. ``register_vn`` is overwritten in place as
    later iterations refine VN assignments.
    """

    _vn_counter: _IntCounter = attrs.field(factory=itertools.count)
    register_vn: dict[models.Register, VN] = attrs.field(factory=dict)
    _provider_key_to_vns: dict[_ProviderKey, tuple[VN, ...]] = attrs.field(factory=dict)
    _const_vn: dict[_ConstKey, VN] = attrs.field(factory=dict)
    vn_definition: dict[VN, _ConstKey | _ProviderKey] = attrs.field(factory=dict)
    # Stable VN per non-redundant phi, pinned once minted so its identity
    # survives optimistic re-iteration.
    _phi_stable_vn: dict[models.Phi, VN] = attrs.field(factory=dict)
    # Memo for VNs minted for non-structurally-numbered value providers
    # (side-effecting reads, undefined values, compiled references, etc.).
    # Keyed by ``id(vp)`` so the same op instance is stable across
    # optimistic-iteration re-walks.
    _identity_vns: dict[int, tuple[VN, ...]] = attrs.field(factory=dict)

    def next_vn(self) -> VN:
        return next(self._vn_counter)

    def set_register_vn(self, reg: models.Register, vn: VN) -> None:
        """Record an assignment of a VN to a register.

        Overwrites any prior entry — the optimistic-iteration loop in
        :func:`_number_values` re-walks the dominator tree, re-numbering each
        register based on the previous iteration's VN map. Within a single
        walk a register is still only assigned once (enforced by the
        structure of the visitor, not a runtime check).
        """
        self.register_vn[reg] = vn

    def assign_register_fresh_vn(self, reg: models.Register) -> VN:
        """Generate and assign a new VN to the register, returning it."""
        vn = self.next_vn()
        self.set_register_vn(reg, vn)
        return vn

    def stable_phi_vn(self, phi: models.Phi) -> VN:
        """Return the persistent VN for a non-redundant phi, minting once.

        The same VN is returned for the same ``phi`` object across iterations,
        so the partition reaches a fixed point even when args never agree on
        a single VN.
        """
        return lazy_setdefault(self._phi_stable_vn, phi, lambda _: self.next_vn())

    def fresh_vns(self, vp: models.ValueProvider) -> tuple[VN, ...]:
        """Mint VNs for a value provider that can't be value-numbered structurally.

        Memoised by ``id(vp)`` so that the same op instance gets the same VNs
        across optimistic-iteration walks — this stops downstream expression
        keys from shifting each iteration. Different op instances still get
        distinct VNs, which is what we want for side-effecting reads (each
        call to ``box_get`` / ``read_slot`` / a non-pure subroutine / etc. may
        return a different value).
        """
        return lazy_setdefault(
            self._identity_vns, id(vp), lambda _: tuple(self.next_vn() for _ in vp.types)
        )

    def lookup_or_assign_vp(
        self, key: _ProviderKey, source: models.ValueProvider
    ) -> tuple[VN, ...]:
        try:
            return self._provider_key_to_vns[key]
        except KeyError:
            pass
        # Mint fresh VNs directly rather than via fresh_vns: this is a
        # structural-key lookup, so cross-iteration stability comes from the
        # key cache itself — the same key in iteration N+1 returns the same
        # VN. Routing through fresh_vns would entangle the ``id(source)``
        # memo with the key cache, so if source's key shifted between
        # iterations (e.g. via an upstream phi VN downgrade) the new key
        # would alias to the old VN and produce false equivalences.
        vns = tuple(self.next_vn() for _ in source.types)
        self._provider_key_to_vns[key] = vns
        if len(vns) == 1:
            (vn,) = vns
            self.vn_definition[vn] = key
        return vns

    def lookup_or_assign_const(self, key: _ConstKey) -> tuple[VN, ...]:
        vn = lazy_setdefault(self._const_vn, key, lambda _: self.next_vn())
        if isinstance(key, _BytesConstKey):
            prior = self.vn_definition.get(vn)
            if prior is not None:
                assert isinstance(prior, _BytesConstKey)
                if _ENCODING_PREF[prior.encoding] > _ENCODING_PREF[key.encoding]:
                    key = prior
        self.vn_definition[vn] = key
        return (vn,)

    # def is_register_constant(self, reg: models.Register) -> bool:
    #     reg_vn = self.register_vn[reg]
    #     defn = self.vn_definition.get(reg_vn)
    #     return isinstance(defn, _ConstKey)


_MaybeAVMType: typing.TypeAlias = AVMType | str
_VNRepresentativeMap: typing.TypeAlias = dict[tuple[VN, _MaybeAVMType], models.Register]


def _materialize_constants(
    tables: _GVNTables,
    subroutine: models.Subroutine,
    start: models.BasicBlock,
    ssa_reads: SSAReadTracker,
    *,
    expand_all_bytes: bool,
) -> bool:
    modified = False
    defining_op = {
        target: op
        for block in subroutine.body
        for op in block.ops
        if isinstance(op, models.Assignment)
        for target in op.targets
    }
    for block in bfs_block_order(start):
        for op in block.ops:
            if not isinstance(op, models.Assignment):
                continue
            if isinstance(op.source, models.MultiValue):
                continue
            folded = _try_fold_constants(
                op, tables, ssa_reads, defining_op, expand_all_bytes=expand_all_bytes
            )
            if folded is not None:
                modified = True
                with ssa_reads.update(op):
                    op.source = folded
    return modified


def _try_fold_constants(
    op: models.Assignment,
    tables: _GVNTables,
    ssa_reads: SSAReadTracker,
    defining_op: Mapping[models.Register, models.Assignment],
    *,
    expand_all_bytes: bool,
) -> models.MultiValue | None:
    target_vns = [tables.register_vn[t] for t in op.targets]
    target_defns = [tables.vn_definition.get(vn) for vn in target_vns]
    if len(target_defns) == 1:
        (target_defn,) = target_defns
        (source_type,) = op.source.types
        match target_defn:
            case _UInt64ConstKey(value=uint64_const):
                return models.UInt64Constant(
                    value=uint64_const,
                    ir_type=source_type,
                    source_location=op.source.source_location,
                )
            case _BytesConstKey(
                value=bytes_const, encoding=bytes_encoding
            ) if expand_all_bytes or (
                isinstance(op.source, models.Intrinsic)
                and len(encode_bytes(bytes_const))
                <= _intrinsic_dead_cost(op, op.source, ssa_reads, defining_op)
            ):
                return models.BytesConstant(
                    value=bytes_const,
                    encoding=bytes_encoding,
                    ir_type=source_type,
                    source_location=op.source.source_location,
                )
    elif _is_list_of(target_defns, _UInt64ConstKey):
        return models.ValueTuple(
            values=[
                models.UInt64Constant(
                    value=uint64_defn.value,
                    ir_type=source_type,
                    source_location=op.source.source_location,
                )
                for uint64_defn, source_type in zip(target_defns, op.source.types, strict=True)
            ],
            source_location=op.source_location,
        )

    return None


def _is_list_of[T, U](lst: list[U], typ: type[T]) -> typing.TypeGuard[list[T]]:
    return all(isinstance(x, typ) for x in lst)


def _intrinsic_dead_cost(
    op: models.Assignment,
    source: models.Intrinsic,
    ssa_reads: SSAReadTracker,
    defining_op: Mapping[models.Register, models.Assignment],
) -> int:
    cost = _cost(source)
    for reg in unique(a for a in source.args if isinstance(a, models.Register)):
        if ssa_reads.is_sole_usage(reg, op):
            defn = defining_op.get(reg)
            if defn is None or len(defn.targets) != 1:
                continue
            match defn.source:
                case models.Intrinsic() as inner if inner.op in COMPILE_TIME_CONSTANT_OPS:
                    cost += _intrinsic_dead_cost(defn, inner, ssa_reads, defining_op)
                case models.Constant() as const:
                    cost += _get_const_size(const)
    return cost


def _cost(intrinsic: models.Intrinsic) -> int:
    instr_size = intrinsic.op.size
    const_arg_sizes = sum(
        _get_const_size(arg) for arg in intrinsic.args if isinstance(arg, models.Constant)
    )
    return instr_size + const_arg_sizes


def _get_const_size(arg: models.Constant) -> int:
    bytes_const = get_bytes_constant(arg)
    if bytes_const is not None:
        return len(encode_bytes(bytes_const))
    match arg:
        case models.ITxnConstant():
            return 0  # immediates get counted as part of op
        case models.SlotConstant():
            raise InternalError("slot constant should not appear in IR during optimisation")
        case models.UInt64Constant(value=int_value):
            return len(encode_varuint(int_value))
    logger.debug(f"GVN: unhandled constant type {type(arg).__name__}")
    return 0


def _build_equivalence_sets(
    subroutine: models.Subroutine,
    tables: _GVNTables,
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    start: models.BasicBlock,
    ssa_reads: SSAReadTracker,
) -> tuple[bool, Collection[Sequence[models.Register]]]:
    """Walk the dominator tree to build equivalence sets respecting dominance.

    Each (VN, AVMType) pair tracks the first register on each dominator path.
    Later registers with the same key are appended — they can safely be replaced
    by the dominating first register.

    Also drops redundant asserts where the condition VN was already asserted on
    this dominator path.
    """
    modified = False
    all_sets = defaultdict[models.Register, list[models.Register]](list)

    def _keep_defn(
        reg: models.Register, vn_to_rep: _VNRepresentativeMap, *, force_new_rep: bool = False
    ) -> bool:
        """Process a register definition, returning if it's the dominant (and should be kept)"""
        vn = tables.register_vn[reg]
        key = (vn, reg.ir_type.maybe_avm_type)
        if force_new_rep:
            rep = vn_to_rep[key] = reg
        else:
            rep = vn_to_rep.setdefault(key, reg)
        all_sets[rep].append(reg)
        return rep == reg

    # Seed with parameters — they dominate all blocks
    initial_scope = _VNRepresentativeMap()
    for param in subroutine.parameters:
        keep_param = _keep_defn(param, initial_scope)
        assert keep_param

    def _walk(
        block: models.BasicBlock,
        vn_to_rep: _VNRepresentativeMap,
        asserted_: Set[VN | models.Value],
    ) -> None:
        nonlocal modified

        scope = dict(vn_to_rep)
        asserted = set(asserted_)
        phis = []
        for phi in block.phis:
            if _keep_defn(phi.register, scope):
                phis.append(phi)
            else:
                modified = True
                ssa_reads.remove(phi)
        block.phis[:] = phis

        ops = []
        for op in block.ops:
            ops.append(op)
            if isinstance(op, models.Assert):
                if isinstance(op.condition, models.Register):
                    condition_vn = tables.register_vn[op.condition]
                    if not set_add(asserted, condition_vn):
                        modified = True
                        logger.debug(f"removing redundant assert of {op.condition}")
                        ops.pop()
                        ssa_reads.remove(op)
            elif isinstance(op, models.Assignment):
                match op.source:
                    case models.Constant():
                        continue
                    case models.ValueTuple(values=values) if all(
                        isinstance(v, models.Constant) for v in values
                    ):
                        # matches multi-target ops folded by _materialize_constants —
                        # mirrors the single-target Constant skip above
                        continue
                    case models.Intrinsic(args=[]):
                        force_new_rep = True
                    case _:
                        force_new_rep = False
                if len(op.targets) == 1 or force_new_rep:
                    keep = False
                    for target in op.targets:
                        keep |= _keep_defn(target, scope, force_new_rep=force_new_rep)
                    if not keep:
                        ops.pop()
                        modified = True
                        ssa_reads.remove(op)
                else:
                    # Multi-target: only drop the op if EVERY target has an external
                    # dominating rep. Partial folding would let MemoryReplacer rewrite
                    # only some targets on the LHS, producing duplicate Assignment
                    # targets and violating SSA. When kept, still register the novel
                    # targets as reps so a later identical op can drop itself.
                    target_keys = [
                        (tables.register_vn[t], t.ir_type.maybe_avm_type) for t in op.targets
                    ]
                    external_reps = [scope.get(k) for k in target_keys]
                    if all(rep is not None for rep in external_reps):
                        for target, rep in zip(op.targets, external_reps, strict=True):
                            assert rep is not None
                            all_sets[rep].append(target)
                        ops.pop()
                        modified = True
                        ssa_reads.remove(op)
                    else:
                        seen_keys = set[tuple[VN, _MaybeAVMType]]()
                        for target, key, ext_rep in zip(
                            op.targets, target_keys, external_reps, strict=True
                        ):
                            if ext_rep is None and set_add(seen_keys, key):
                                _keep_defn(target, scope, force_new_rep=False)

        block.ops[:] = ops
        for child in dom_tree.get(block, []):
            _walk(child, scope, asserted)

    _walk(start, initial_scope, set())
    return modified, [s for s in all_sets.values() if len(s) > 1]


def build_replacements(
    subroutine: models.Subroutine, equivalence_sets: Collection[Sequence[models.Register]]
) -> dict[models.Register, models.Register]:
    """Build the final replacement map with preferred register names."""
    register_map = dict[models.Register, models.Register]()

    for equivalence_set in equivalence_sets:
        assert len(equivalence_set) > 1

        parameters = [r for r in equivalence_set if r in subroutine.parameters]
        match parameters:
            case [param]:
                replacement = param
            case []:
                for reg in equivalence_set:
                    if models.TMP_VAR_INDICATOR not in reg.name:
                        replacement = reg
                        break
                else:  # fall back to first register if all are temp
                    replacement = equivalence_set[0]
            case _:
                raise InternalError("multiple parameters in the same equivalence set")

        equiv_set_ids = ", ".join(r.local_id for r in equivalence_set)
        logger.debug(
            f"GVN found equivalence set: ({equiv_set_ids}),"
            f" selected replacement: {replacement.local_id}"
        )

        for reg in equivalence_set:
            if reg is not replacement:
                register_map[reg] = replacement

    for target in register_map.values():
        if target in register_map:
            raise InternalError(
                f"GVN: replacement chain detected:"
                f" {target.local_id} -> {register_map[target].local_id}"
            )

    return register_map


@attrs.frozen
class _ProviderVNBuilder(ValueProviderVisitor[tuple[VN, ...]]):
    """Number a ValueProvider: build a canonical key, look up or assign VNs.

    Returns the VN tuple for pure expressions (either existing or freshly assigned),
    or None for side-effecting or unrecognised operations.
    """

    _tables: _GVNTables

    def _const_uint64(self, value: int) -> tuple[VN, ...]:
        key = _UInt64ConstKey(value=value)
        return self._tables.lookup_or_assign_const(key)

    def _const_bytes(self, value: bytes, encoding: AVMBytesEncoding) -> tuple[VN, ...]:
        key = _BytesConstKey(value=value, encoding=encoding)
        return self._tables.lookup_or_assign_const(key)

    def _const_biguint(self, value: int) -> tuple[VN, ...]:
        evald = biguint_bytes_eval(value)
        return self._const_bytes(evald, AVMBytesEncoding.base16)

    def _const_wide_math_result(self, values: tuple[int, ...]) -> tuple[VN, ...]:
        return tuple(vn for val in values for vn in self._const_uint64(val))

    def _index_vns(self, indexes: tuple[int | models.Value, ...]) -> tuple[_IndexVN, ...]:
        return tuple(
            (
                _IndexVN(kind="value", index=self._visit_value(idx))
                if isinstance(idx, models.Value)
                else _IndexVN(kind="static", index=idx)
            )
            for idx in indexes
        )

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> tuple[VN, ...]:
        key = _ExtractKey(
            base_vn=self._visit_value(read.base),
            base_type=read.base_type,
            index_vns=self._index_vns(read.indexes),
            check_bounds=read.check_bounds,
        )
        return self._tables.lookup_or_assign_vp(key, read)

    @typing.override
    def visit_replace_value(self, write: models.ReplaceValue) -> tuple[VN, ...]:
        base_vn = self._visit_value(write.base)
        index_vns = self._index_vns(write.indexes)
        value_vn = self._visit_value(write.value)
        key = _ReplaceKey(
            base_vn=base_vn,
            base_type=write.base_type,
            index_vns=index_vns,
            value_vn=value_vn,
        )
        return self._tables.lookup_or_assign_vp(key, write)

    @typing.override
    def visit_array_concat(self, concat: models.ArrayConcat) -> tuple[VN, ...]:
        base_vn = self._visit_value(concat.base)
        items_vn = self._visit_value(concat.items)
        key = _ArrayConcatKey(
            base_vn=base_vn,
            base_type=concat.base_type,
            items_vn=items_vn,
            item_encoding=concat.item_encoding,
        )
        return self._tables.lookup_or_assign_vp(key, concat)

    @typing.override
    def visit_array_length(self, length: models.ArrayLength) -> tuple[VN, ...]:
        if isinstance(length.base_type, types.SlotType):
            return self._tables.fresh_vns(length)
        base_vn = self._visit_value(length.base)
        key = _ArrayLengthKey(
            base_vn=base_vn,
            base_type=length.base_type,
        )
        return self._tables.lookup_or_assign_vp(key, length)

    @typing.override
    def visit_array_pop(self, pop: models.ArrayPop) -> tuple[VN, ...]:
        base_vn = self._visit_value(pop.base)
        key = _ArrayPopKey(
            base_vn=base_vn,
            base_type=pop.base_type,
        )
        return self._tables.lookup_or_assign_vp(key, pop)

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> tuple[VN, ...]:
        return self._tables.fresh_vns(read)  # stateful, leave this up to repeated-reads

    @typing.override
    def visit_bytes_encode(self, encode: models.BytesEncode) -> tuple[VN, ...]:
        value_vns = tuple(self._visit_value(v) for v in encode.values)
        key = _EncodeKey(
            encoding=encode.encoding,
            value_vns=value_vns,
            values_type=encode.values_type,
        )
        return self._tables.lookup_or_assign_vp(key, encode)

    @typing.override
    def visit_decode_bytes(self, decode: models.DecodeBytes) -> tuple[VN, ...]:
        value_vn = self._visit_value(decode.value)
        key = _DecodeKey(
            encoding=decode.encoding,
            value_vn=value_vn,
            ir_type=decode.ir_type,
        )
        return self._tables.lookup_or_assign_vp(key, decode)

    @typing.override
    def visit_inner_transaction_field(
        self, intrinsic: models.InnerTransactionField
    ) -> tuple[VN, ...]:
        # stateful - implicitly depends on the most recent itxn_submit
        return self._tables.fresh_vns(intrinsic)

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> tuple[VN, ...]:
        match intrinsic:
            # special case - `global` is not a pure op necessarily, but there is one constant case
            case models.Intrinsic(op=AVMOp.global_, immediates=["ZeroAddress"]):
                bytes_const_evald = Address.parse(algo_constants.ZERO_ADDRESS).public_key
                return self._const_bytes(bytes_const_evald, AVMBytesEncoding.base32)

        op = intrinsic.op
        if op.code not in PURE_AVM_OPS:
            return self._tables.fresh_vns(intrinsic)
        args = intrinsic.args
        arg_vns = tuple(self._visit_value(a) for a in args)
        arg_defns = [self._tables.vn_definition.get(arg_vn) for arg_vn in arg_vns]

        if (
            not intrinsic.immediates
            and len(intrinsic.types) == 1
            and op in COMPILE_TIME_CONSTANT_OPS
        ):
            match arg_defns:
                case [_UInt64ConstKey(value=x), _UInt64ConstKey(value=y)]:
                    z = fold_uint64_const_binary_op(op, x, y)
                    if z is not None:
                        return self._const_uint64(z)
                case [
                    _BytesConstKey(value=xb, encoding=ea, as_biguint=xb_int),
                    _BytesConstKey(value=yb, encoding=eb, as_biguint=yb_int),
                ]:
                    if xb_int is not None and yb_int is not None:
                        zi = fold_biguint_const_binary_op(op, xb_int, yb_int)
                        if zi is not None:
                            (ir_type,) = intrinsic.types
                            if ir_type == PrimitiveIRType.biguint:
                                return self._const_biguint(zi)
                            assert ir_type.avm_type is AVMType.uint64
                            return self._const_uint64(zi)
                    match fold_bytes_const_binary_op(op, xb, yb):
                        case int(zi):
                            return self._const_uint64(zi)
                        case bytes(zb):
                            return self._const_bytes(zb, choose_encoding(ea, eb))
                        case other:
                            typing.assert_type(other, None)

        match op:
            case AVMOp.len_:
                match arg_defns:
                    case [_BytesConstKey(value=len_arg)]:
                        len_result = len(len_arg)
                        if len_result <= algo_constants.MAX_BYTES_LENGTH:
                            return self._const_uint64(len(len_arg))
            case AVMOp.itob:
                match arg_defns:
                    case [_UInt64ConstKey(value=itob_arg)]:
                        if valid_uint64(itob_arg):
                            bytes_const_evald = itob_arg.to_bytes(8, byteorder="big", signed=False)
                            return self._const_bytes(bytes_const_evald, AVMBytesEncoding.base16)
            case AVMOp.bzero:
                match arg_defns:
                    case [_UInt64ConstKey(value=bzero_arg)]:
                        if bzero_arg <= algo_constants.MAX_BYTES_LENGTH:
                            bytes_const_evald = b"\x00" * bzero_arg
                            return self._const_bytes(bytes_const_evald, AVMBytesEncoding.base16)
            case AVMOp.not_ | AVMOp.bitwise_not | AVMOp.sqrt | AVMOp.bitlen:
                match arg_defns:
                    case [_UInt64ConstKey(value=x)]:
                        folded = fold_uint64_const_unary_op(op, x)
                        if folded is not None:
                            return self._const_uint64(folded)
                    case [_BytesConstKey(value=bv)] if op is AVMOp.bitlen:
                        bitlen_folded = fold_bytes_const_unary_op(op, bv)
                        if isinstance(bitlen_folded, int):
                            return self._const_uint64(bitlen_folded)
                    case [_IntrinsicKey(op=source_op) as comp] if op is AVMOp.not_:
                        # Negation-aware numbering: !(comparison) -> inverse comparison.
                        # e.g. !(a < b) gets the same key as (a >= b).
                        if inverse_op := _INVERSE_COMPARISONS.get(source_op):
                            inverse_key = _IntrinsicKey(
                                op=inverse_op,
                                immediates=comp.immediates,
                                arg_vns=comp.arg_vns,
                            )
                            return self._tables.lookup_or_assign_vp(inverse_key, intrinsic)
            case AVMOp.bitwise_not_bytes | AVMOp.btoi | AVMOp.bsqrt:
                match arg_defns:
                    case [_BytesConstKey(value=bv, encoding=enc)]:
                        match fold_bytes_const_unary_op(op, bv):
                            case int(v):
                                if intrinsic.types[0] == PrimitiveIRType.biguint:
                                    return self._const_biguint(v)
                                return self._const_uint64(v)
                            case bytes(result_bytes):
                                return self._const_bytes(result_bytes, chop_encoding(enc))
                            case other:
                                typing.assert_type(other, None)
                    case [
                        _IntrinsicKey(op=AVMOp.itob, immediates=(), arg_vns=(source_vn,))
                    ] if op is AVMOp.btoi:
                        # btoi(itob(x)) = x
                        return (source_vn,)
            case AVMOp.sha256 | AVMOp.sha3_256 | AVMOp.sha512_256 | AVMOp.keccak256:
                match arg_defns:
                    case [_BytesConstKey(value=bv)]:
                        digest = hash_eval_funcs[op](bv)
                        return self._const_bytes(digest, AVMBytesEncoding.base16)
            case AVMOp.setbit:
                match arg_defns:
                    case [
                        _UInt64ConstKey(value=source),
                        _UInt64ConstKey(value=index),
                        _UInt64ConstKey(value=value),
                    ]:
                        folded = fold_setbit_uint64(source, index, value)
                        if folded is not None:
                            return self._const_uint64(folded)
                    case [
                        _BytesConstKey(value=bv, encoding=enc),
                        _UInt64ConstKey(value=index),
                        _UInt64ConstKey(value=value),
                    ]:
                        folded_bytes = fold_setbit_bytes(bv, index, value)
                        if folded_bytes is not None:
                            return self._const_bytes(folded_bytes, chop_encoding(enc))
            case AVMOp.setbyte:
                match arg_defns:
                    case [
                        _BytesConstKey(value=bv, encoding=enc),
                        _UInt64ConstKey(value=index),
                        _UInt64ConstKey(value=value),
                    ]:
                        folded_bytes = fold_setbyte(bv, index, value)
                        if folded_bytes is not None:
                            return self._const_bytes(folded_bytes, chop_encoding(enc))
            case AVMOp.getbit:
                match arg_defns:
                    case [_BytesConstKey(value=bv), _UInt64ConstKey(value=index)]:
                        folded = fold_getbit_bytes(bv, index)
                        if folded is not None:
                            return self._const_uint64(folded)
            case AVMOp.getbyte:
                match arg_defns:
                    case [_BytesConstKey(value=bv), _UInt64ConstKey(value=index)]:
                        folded = fold_getbyte(bv, index)
                        if folded is not None:
                            return self._const_uint64(folded)
            case AVMOp.extract_uint16 | AVMOp.extract_uint32 | AVMOp.extract_uint64:
                match arg_defns:
                    case [_BytesConstKey(value=bv), _UInt64ConstKey(value=offset)]:
                        folded = fold_extract_uint_n(op, bv, offset)
                        if folded is not None:
                            return self._const_uint64(folded)
            case AVMOp.select:
                # arg layout: [false_branch, true_branch, selector]
                if arg_vns[0] == arg_vns[1]:
                    # select(x, x, _) → x
                    return (arg_vns[0],)
                if isinstance(arg_defns[2], _UInt64ConstKey):
                    # const selector → pick branch directly
                    return (arg_vns[1] if arg_defns[2].value else arg_vns[0],)
            case AVMOp.replace2:
                match arg_defns, intrinsic.immediates:
                    case [
                        [
                            _BytesConstKey(value=src_bytes, encoding=src_enc),
                            _BytesConstKey(value=repl_bytes, encoding=repl_enc),
                        ],
                        [int(start)],
                    ]:
                        folded_bytes = fold_replace2(src_bytes, start, repl_bytes)
                        if folded_bytes is not None:
                            return self._const_bytes(
                                folded_bytes, choose_encoding(src_enc, repl_enc)
                            )
            case AVMOp.replace3:
                match arg_defns:
                    case [
                        _BytesConstKey(value=src_bytes, encoding=src_enc),
                        _UInt64ConstKey(value=start),
                        _BytesConstKey(value=repl_bytes, encoding=repl_enc),
                    ]:
                        folded_bytes = fold_replace2(src_bytes, start, repl_bytes)
                        if folded_bytes is not None:
                            return self._const_bytes(
                                folded_bytes, choose_encoding(src_enc, repl_enc)
                            )
            case AVMOp.concat:
                match arg_defns:
                    case [
                        _BytesConstKey(value=first_byte_const, encoding=first_enc),
                        _BytesConstKey(value=second_byte_const, encoding=second_enc),
                    ]:
                        concat_result = first_byte_const + second_byte_const
                        if len(concat_result) <= algo_constants.MAX_BYTES_LENGTH:
                            return self._const_bytes(
                                concat_result,
                                choose_encoding(first_enc, second_enc, is_concat=True),
                            )
            case AVMOp.substring3:
                match arg_defns:
                    case [
                        _BytesConstKey(value=byte_arg, encoding=byte_enc),
                        _UInt64ConstKey(value=start_arg),
                        _UInt64ConstKey(value=end_arg),
                    ]:
                        if (
                            start_arg
                            <= end_arg
                            <= len(byte_arg)
                            <= algo_constants.MAX_BYTES_LENGTH
                        ):
                            substring_result = byte_arg[start_arg:end_arg]
                            return self._const_bytes(substring_result, chop_encoding(byte_enc))
            case AVMOp.substring:
                match arg_defns, intrinsic.immediates:
                    case [
                        [_BytesConstKey(value=byte_arg, encoding=byte_enc)],
                        [int(start_arg), int(end_arg)],
                    ]:
                        if (
                            start_arg
                            <= end_arg
                            <= len(byte_arg)
                            <= algo_constants.MAX_BYTES_LENGTH
                        ):
                            substring_result = byte_arg[start_arg:end_arg]
                            return self._const_bytes(substring_result, chop_encoding(byte_enc))
            case AVMOp.extract3:
                match arg_defns:
                    case [
                        _BytesConstKey(value=byte_arg, encoding=byte_enc),
                        _UInt64ConstKey(value=start_arg),
                        _UInt64ConstKey(value=length_arg),
                    ]:
                        end_arg = start_arg + length_arg
                        if end_arg <= len(byte_arg) <= algo_constants.MAX_BYTES_LENGTH:
                            extract_result = byte_arg[start_arg:end_arg]
                            return self._const_bytes(extract_result, chop_encoding(byte_enc))
            case AVMOp.extract:
                match arg_defns, intrinsic.immediates:
                    case [
                        [_BytesConstKey(value=byte_arg, encoding=byte_enc)],
                        [int(start_arg), int(length_arg)],
                    ]:
                        # immediate variant: L=0 means "extract to end".
                        byte_len = len(byte_arg)
                        end_arg = byte_len if length_arg == 0 else start_arg + length_arg
                        if start_arg <= end_arg <= byte_len <= algo_constants.MAX_BYTES_LENGTH:
                            extract_result = byte_arg[start_arg:end_arg]
                            return self._const_bytes(extract_result, chop_encoding(byte_enc))
            case AVMOp.extract_uint16 | AVMOp.extract_uint32 | AVMOp.extract_uint64:
                match arg_defns:
                    case [_BytesConstKey(value=bv), _UInt64ConstKey(value=offset)]:
                        folded = fold_extract_uint_n(op, bv, offset)
                        if folded is not None:
                            return self._const_uint64(folded)
            case AVMOp.addw:
                match arg_defns:
                    case [_UInt64ConstKey(value=addw_a), _UInt64ConstKey(value=addw_b)]:
                        return self._const_wide_math_result(fold_addw(addw_a, addw_b))
            case AVMOp.mulw:
                match arg_defns:
                    case [_UInt64ConstKey(value=mulw_a), _UInt64ConstKey(value=mulw_b)]:
                        return self._const_wide_math_result(fold_mulw(mulw_a, mulw_b))
            case AVMOp.expw:
                match arg_defns:
                    case [_UInt64ConstKey(value=expw_a), _UInt64ConstKey(value=expw_b)]:
                        expw_folded = fold_expw(expw_a, expw_b)
                        if expw_folded is not None:
                            return self._const_wide_math_result(expw_folded)
            case AVMOp.divw:
                match arg_defns:
                    case [
                        _UInt64ConstKey(value=hi),
                        _UInt64ConstKey(value=lo),
                        _UInt64ConstKey(value=divisor),
                    ]:
                        divw_folded = fold_divw(hi, lo, divisor)
                        if divw_folded is not None:
                            return self._const_uint64(divw_folded)
            case AVMOp.divmodw:
                match arg_defns:
                    case [
                        _UInt64ConstKey(value=h1),
                        _UInt64ConstKey(value=l1),
                        _UInt64ConstKey(value=h2),
                        _UInt64ConstKey(value=l2),
                    ]:
                        divmodw_folded = fold_divmodw(h1, l1, h2, l2)
                        if divmodw_folded is not None:
                            return self._const_wide_math_result(divmodw_folded)
        match arg_vns:
            case [vn1, vn2] if vn1 == vn2:
                match op:
                    case (
                        AVMOp.neq
                        | AVMOp.neq_bytes
                        | AVMOp.lt
                        | AVMOp.lt_bytes
                        | AVMOp.gt
                        | AVMOp.gt_bytes
                        | AVMOp.bitwise_xor
                        # | AVMOp.bitwise_xor_bytes - need length
                        | AVMOp.sub
                    ):
                        return self._const_uint64(0)
                    case AVMOp.sub_bytes:
                        return self._const_bytes(b"", AVMBytesEncoding.unknown)
                    case (
                        AVMOp.eq
                        | AVMOp.eq_bytes
                        | AVMOp.lte
                        | AVMOp.lte_bytes
                        | AVMOp.gte
                        | AVMOp.gte_bytes
                        # | AVMOp.div_floor - div by zero
                        # | AVMOp.div_floor_bytes - div by zero
                    ):
                        return self._const_uint64(1)
                    case (
                        AVMOp.bitwise_and
                        | AVMOp.bitwise_and_bytes
                        | AVMOp.bitwise_or
                        | AVMOp.bitwise_or_bytes
                    ):
                        return (vn1,)

        # One-const algebraic simplifications (uint64 binary ops).
        if len(arg_vns) == 2:
            a_def, b_def = arg_defns
            a_const = a_def.value if isinstance(a_def, _UInt64ConstKey) else None
            b_const = b_def.value if isinstance(b_def, _UInt64ConstKey) else None
            if a_const is not None or b_const is not None:
                # eq → !operand is shaped differently to other one-const folds.
                if op == AVMOp.eq:
                    if a_const == 0:
                        return self._tables.lookup_or_assign_vp(
                            _IntrinsicKey(op=AVMOp.not_, immediates=(), arg_vns=(arg_vns[1],)),
                            intrinsic,
                        )
                    if b_const == 0:
                        return self._tables.lookup_or_assign_vp(
                            _IntrinsicKey(op=AVMOp.not_, immediates=(), arg_vns=(arg_vns[0],)),
                            intrinsic,
                        )
                a, b = intrinsic.args
                match simplify_uint64_binary_op_one_const(op, a, b, a_const, b_const):
                    case int(v):
                        return self._const_uint64(v)
                    case BinarySimplification.LEFT:
                        return (arg_vns[0],)
                    case BinarySimplification.RIGHT:
                        return (arg_vns[1],)
                    case None:
                        pass
            a_bg = (
                int.from_bytes(a_def.value, "big")
                if isinstance(a_def, _BytesConstKey) and len(a_def.value) <= 64
                else None
            )
            b_bg = (
                int.from_bytes(b_def.value, "big")
                if isinstance(b_def, _BytesConstKey) and len(b_def.value) <= 64
                else None
            )
            if a_bg is not None or b_bg is not None:
                match simplify_bytes_binary_op_one_const(op, a_bg, b_bg):
                    case int(v):
                        return self._const_biguint(v)
                    case BinarySimplification.LEFT:
                        return (arg_vns[0],)
                    case BinarySimplification.RIGHT:
                        return (arg_vns[1],)
                    case None:
                        pass

        if op in _COMMUTATIVE_OPS:
            arg_vns = tuple(sorted(arg_vns))
        elif op in _MIRROR_OPS and arg_vns[0] > arg_vns[1]:
            arg_vns = (arg_vns[1], arg_vns[0])
            op = _MIRROR_OPS[op]
        key = _IntrinsicKey(op=op, immediates=tuple(intrinsic.immediates), arg_vns=arg_vns)
        vns = self._tables.lookup_or_assign_vp(key, intrinsic)
        return vns

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> tuple[VN, ...]:
        if not callsub.target.pure:
            return self._tables.fresh_vns(callsub)
        arg_vns = tuple(self._visit_value(a) for a in callsub.args)
        key = _CallSubKey(target_id=callsub.target.id, arg_vns=arg_vns)
        return self._tables.lookup_or_assign_vp(key, callsub)

    @typing.override
    def visit_new_slot(self, new_slot: models.NewSlot) -> tuple[VN, ...]:
        return self._tables.fresh_vns(new_slot)  # side-effecting

    @typing.override
    def visit_read_slot(self, read_slot: models.ReadSlot) -> tuple[VN, ...]:
        return self._tables.fresh_vns(read_slot)  # stateful, leave this up to repeated-reads

    @typing.override
    def visit_value_tuple(self, tup: models.ValueTuple) -> tuple[VN, ...]:
        # A ValueTuple just pairs up its constituent values for a multi-target
        # binding; the i-th target inherits the i-th value's VN directly.
        return tuple(self._visit_value(v) for v in tup.values)

    # -- Value subtypes --

    def _visit_value(self, val: models.Value) -> VN:
        # all Value sub-types have arity of 1
        (vn,) = val.accept(self)
        return vn

    @typing.override
    def visit_undefined(self, val: models.Undefined) -> tuple[VN, ...]:
        return self._tables.fresh_vns(val)

    @typing.override
    def visit_compiled_contract_reference(
        self, const: models.CompiledContractReference
    ) -> tuple[VN, ...]:
        return self._tables.fresh_vns(const)

    @typing.override
    def visit_compiled_logicsig_reference(
        self, const: models.CompiledLogicSigReference
    ) -> tuple[VN, ...]:
        return self._tables.fresh_vns(const)

    @typing.override
    def visit_register(self, reg: models.Register) -> tuple[VN, ...]:
        try:
            return (self._tables.register_vn[reg],)
        except KeyError:
            raise InternalError(
                f"SSA invariant violated: no dominating definition for {reg}"
            ) from None

    @typing.override
    def visit_uint64_constant(self, const: models.UInt64Constant) -> tuple[VN, ...]:
        return self._const_uint64(const.value)

    @typing.override
    def visit_biguint_constant(self, const: models.BigUIntConstant) -> tuple[VN, ...]:
        return self._const_biguint(const.value)

    @typing.override
    def visit_bytes_constant(self, const: models.BytesConstant) -> tuple[VN, ...]:
        return self._const_bytes(const.value, const.encoding)

    @typing.override
    def visit_address_constant(self, const: models.AddressConstant) -> tuple[VN, ...]:
        evald = Address.parse(const.value).public_key
        return self._const_bytes(evald, AVMBytesEncoding.base32)

    @typing.override
    def visit_method_constant(self, const: models.MethodConstant) -> tuple[VN, ...]:
        evald = method_selector_hash(const.value)
        return self._const_bytes(evald, AVMBytesEncoding.base16)

    @typing.override
    def visit_itxn_constant(self, const: models.ITxnConstant) -> tuple[VN, ...]:
        # not sure we should be messing with these, give it a fresh VN
        return self._tables.fresh_vns(const)

    @typing.override
    def visit_slot_constant(self, const: models.SlotConstant) -> tuple[VN, ...]:
        return self._const_uint64(const.value)

    @typing.override
    def visit_template_var(self, deploy_var: models.TemplateVar) -> tuple[VN, ...]:
        key = _TemplateVarKey(name=deploy_var.name)
        return self._tables.lookup_or_assign_const(key)


class GVNBlockVisitor(NoOpIRVisitor[None]):
    def __init__(
        self,
        tables: _GVNTables,
        *,
        phi_treatment: Mapping[models.Phi, _PhiTreatment],
    ):
        self.tables = tables
        # ``phi_treatment`` marks the phis whose redundancy claim is gated
        # on every arg already being numbered, matching the algorithm used
        # before optimistic iteration was introduced. Populated by the SCC
        # pre-pass (``_classify_phi_sccs``) for phis that demonstrably
        # cannot benefit from iteration; the cap-out fallback passes a map
        # of every phi → ``_PESSIMISTIC`` to apply the gate everywhere.
        self.phi_treatment = phi_treatment
        # phi table is per block because the through->block relationship is
        # effectively part of the identity
        self.phi_table = dict[frozenset[tuple[models.BasicBlock, VN | models.Register]], VN]()

    @cached_property
    def provider_vn_builder(self) -> _ProviderVNBuilder:
        return _ProviderVNBuilder(self.tables)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        vns = ass.source.accept(self.provider_vn_builder)
        for target, vn in zip(ass.targets, vns, strict=True):
            self.tables.set_register_vn(target, vn)

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        # Assign a VN to a phi node's register, under optimistic phi numbering:
        #   1. Args whose source register has not been numbered yet (back-edge args
        #      on iteration 1; not-yet-revisited registers on later iterations) are
        #      filtered from the "all args agree" check, so the phi can match a
        #      single forward-edge VN even before the cycle has been resolved.
        #   2. If all remaining (non-top) args share a single VN, the phi is
        #      redundant and inherits that VN.
        #   3. Otherwise, the phi is hashed (using the source register as a
        #      placeholder for un-numbered args, to preserve Register identity
        #      across different back-edge sources) and compared against other phis
        #      in the same block — congruent phis share a VN.
        #   4. Otherwise, the phi receives its persistent ``stable_phi_vn``, so the
        #      partition stops moving once every phi has been classified.

        if not phi.args:
            # A phi with no args is essentially undefined, and this can only occur in the entry
            # block. We don't treat Undefined as being a singleton, each instance is considered
            # unique for our purposes here - so treat no-arg phis the same.
            self.tables.set_register_vn(phi.register, self.tables.stable_phi_vn(phi))
            return

        real_vns = list[VN]()
        phi_key_entries = list[tuple[models.BasicBlock, VN | models.Register]]()
        any_top = False
        for arg in phi.args:
            existing_vn = self.tables.register_vn.get(arg.value)
            if existing_vn is None:
                # Optimistic top: the source register isn't numbered yet in this
                # walk. Use the register itself as the hash-table placeholder so
                # different un-numbered sources stay distinguishable.
                any_top = True
                phi_key_entries.append((arg.through, arg.value))
            else:
                real_vns.append(existing_vn)
                phi_key_entries.append((arg.through, existing_vn))
        phi_key = frozenset(phi_key_entries)

        # Compute the candidate VN for this iteration:
        #   - if all real args agree, the phi is redundant and inherits that VN.
        #     A monotonic-convergence guard pins to the stable VN if this would
        #     flip the phi between distinct redundant VNs across iterations
        #     (which can happen when its args sit in a cycle);
        #   - else if a prior phi in this block matches the key, share its VN;
        #   - else the phi is non-redundant and uses its persistent stable VN.
        # The guard is scoped to the redundancy branch only. Applying it to
        # the sibling-congruence branch would split block-local-congruent
        # cohorts onto distinct stable VNs, because `stable_phi_vn` is keyed
        # per-Phi — each cohort member has its own.
        # For phis the SCC pre-pass marked ``_PESSIMISTIC``, the redundancy
        # branch additionally requires that every arg was already numbered —
        # without iteration, an un-numbered back-edge can't be optimistically
        # equated with the forward args.
        candidate: VN | None = None
        can_be_redundant = real_vns and len(set(real_vns)) == 1
        if self.phi_treatment.get(phi) == _PESSIMISTIC and any_top:
            can_be_redundant = False
        if can_be_redundant:
            candidate = real_vns[0]
            prev_vn = self.tables.register_vn.get(phi.register)
            if prev_vn is not None and prev_vn != candidate:
                candidate = self.tables.stable_phi_vn(phi)
        if candidate is None:
            candidate = self.phi_table.get(phi_key)
        if candidate is None:
            candidate = self.tables.stable_phi_vn(phi)

        self.tables.set_register_vn(phi.register, candidate)
        self.phi_table.setdefault(phi_key, candidate)


def _process_blocks_pre_order(
    tables: _GVNTables,
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    block: models.BasicBlock,
    *,
    phi_treatment: Mapping[models.Phi, _PhiTreatment],
) -> None:
    visitor = GVNBlockVisitor(tables, phi_treatment=phi_treatment)
    for op in block.all_ops:
        op.accept(visitor)

    for child in dom_tree.get(block, []):
        _process_blocks_pre_order(tables, dom_tree, child, phi_treatment=phi_treatment)


# Safety bound on optimistic iterations. The fixed point is reached when every
# register's VN stops changing between consecutive walks. Each iteration can only
# downgrade a phi's classification (redundant -> non-redundant pins the stable VN
# permanently), so termination is guaranteed within a bounded number of iterations
# in practice — this cap exists only to protect against pathological cases.
# With the SCC pre-pass (``_classify_phi_sccs``) eliminating the chain-ratchet
# shape (a multi-member phi SCC with ≥ 2 distinct external-arg Registers, where
# convergence count was ``depth + 3``), the residual iteration count is bounded
# by SCC convergence depth, empirically ≤ 3 across the corpus.
_MAX_OPTIMISTIC_ITERATIONS: typing.Final = 5


def _classify_phi_sccs(
    subroutine: models.Subroutine,
    provisional_vn: Mapping[models.Register, VN],
) -> Mapping[models.Phi, _PhiTreatment]:
    """Classify phis whose SCC cannot collapse, so iteration is skipped on them.

    Builds the phi-only dependency graph (nodes = ``Phi`` instances, edges
    consumer → producer iff some arg of consumer has ``.value`` equal to the
    producer's register, with self-edges skipped) and finds SCCs. A
    multi-member SCC with ≥ 2 distinct external-arg VNs cannot reduce to a
    single VN — its members can only mint per-phi stable VNs, which the
    pessimistic guard produces in one walk instead of taking ``depth + 3``
    walks for the disagreement signal to propagate outward through the SCC.

    External-arg cardinality is counted by VN identity using ``provisional_vn``
    (the numbering produced by an all-pessimistic seed walk). Counting by VN
    rather than Register identity lets the criterion see through commutative
    canonicalisation, constant folding, and structural CSE — distinct
    Registers that GVN proves equivalent share a provisional VN and do not
    block their SCC's collapse.

    ``Phi`` uses identity hashing (``@attrs.define(eq=False)`` on
    ``src/puya/ir/models.py``), so the returned mapping is keyed by ``Phi``
    object identity.
    """
    reg_to_phi = {phi.register: phi for block in subroutine.body for phi in block.phis}
    if not reg_to_phi:
        return {}

    graph = nx.DiGraph()
    for phi in reg_to_phi.values():
        graph.add_node(phi)
        for arg in phi.args:
            if arg.value == phi.register:
                continue
            producer = reg_to_phi.get(arg.value)
            if producer is not None:
                graph.add_edge(phi, producer)

    result = dict[models.Phi, _PhiTreatment]()
    for scc in nx.strongly_connected_components(graph):
        if len(scc) <= 1:
            continue
        external_vns = set[VN]()
        for phi in scc:
            for arg in phi.args:
                if arg.value == phi.register:
                    continue
                producer = reg_to_phi.get(arg.value)
                if producer is None or producer not in scc:
                    vn = provisional_vn.get(arg.value)
                    if vn is not None:
                        external_vns.add(vn)
                    if len(external_vns) >= 2:
                        break
            if len(external_vns) >= 2:
                break
        if len(external_vns) >= 2:
            for phi in scc:
                result[phi] = _PESSIMISTIC
    return result


def _number_values(
    subroutine: models.Subroutine,
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    start: models.BasicBlock,
) -> _GVNTables:
    """Number every SSA definition via optimistic iteration to a fixed point.

    The dominator-tree walk is repeated until ``register_vn`` stops changing
    between iterations. On iteration 1 every back-edge phi argument is treated
    as the lattice top (filtered from the redundancy check); on later
    iterations those args take their previous-iteration VN, letting cyclic
    phi congruences surface naturally. Non-redundant phis pin a stable VN
    (see :meth:`_GVNTables.stable_phi_vn`) so the partition stops moving.

    ``_classify_phi_sccs`` runs first against an all-pessimistic seed walk,
    so external-arg VNs reflect structural CSE / commutative canonicalisation;
    multi-member phi SCCs whose externals have ≥ 2 distinct seed VNs use the
    pessimistic redundancy guard so iteration doesn't waste walks ratcheting
    through chain-shaped SCCs that can't collapse anyway.
    """
    seed_tables = _GVNTables()
    for param in subroutine.parameters:
        seed_tables.assign_register_fresh_vn(param)
    seed_treatment = {phi: _PESSIMISTIC for block in subroutine.body for phi in block.phis}
    _process_blocks_pre_order(seed_tables, dom_tree, start, phi_treatment=seed_treatment)

    phi_treatment = _classify_phi_sccs(subroutine, seed_tables.register_vn)
    tables = _GVNTables()
    for param in subroutine.parameters:
        tables.assign_register_fresh_vn(param)

    for iteration in range(_MAX_OPTIMISTIC_ITERATIONS):
        prev_register_vn = dict(tables.register_vn)
        _process_blocks_pre_order(tables, dom_tree, start, phi_treatment=phi_treatment)
        if tables.register_vn == prev_register_vn:
            logger.debug(f"GVN: {subroutine.id} converged after {iteration + 1} iteration(s)")
            return tables
    # Cap-out: an un-converged partition can contain optimistic merges that
    # would not have survived further iteration. Discard the in-progress
    # tables and re-number with a single pessimistic pass — un-numbered
    # back-edge args block phi redundancy, matching the algorithm used
    # before optimistic iteration was introduced. Forward CSE, trivially-
    # redundant phis, and constant materialisation still apply; only
    # cyclic phi congruences are missed.
    logger.debug(
        f"GVN: {subroutine.id} did not converge within"
        f" {_MAX_OPTIMISTIC_ITERATIONS} iterations;"
        f" falling back to pessimistic single-pass"
    )
    fallback_treatment = {phi: _PESSIMISTIC for block in subroutine.body for phi in block.phis}
    tables = _GVNTables()
    for param in subroutine.parameters:
        tables.assign_register_fresh_vn(param)
    _process_blocks_pre_order(tables, dom_tree, start, phi_treatment=fallback_treatment)
    return tables


def global_value_numbering(context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Run GVN on a subroutine.

    Flow: optimistic hash-based numbering (fixed-point iteration over the
    dominator tree) -> constant materialization -> dominance-based elimination.
    Cyclic phi congruence falls out of the iterated numbering.
    """
    start, dom_tree = compute_dominator_tree(subroutine)
    tables = _number_values(subroutine, dom_tree, start)
    ssa_reads = SSAReadTracker()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)
    folded = _materialize_constants(
        tables,
        subroutine,
        start,
        ssa_reads,
        expand_all_bytes=context.options.expand_all_bytes,
    )
    eliminated, equivalence_sets = _build_equivalence_sets(
        subroutine,
        tables,
        dom_tree,
        start,
        ssa_reads,
    )
    modified = folded or eliminated
    register_replacements = build_replacements(subroutine, equivalence_sets)

    if register_replacements:
        logger.debug(f"GVN: {len(register_replacements)} replacement(s) in {subroutine.id}")
        replaced = MemoryReplacer.apply(subroutine.body, replacements=register_replacements)
        if replaced > 0:
            modified = True

    return modified
