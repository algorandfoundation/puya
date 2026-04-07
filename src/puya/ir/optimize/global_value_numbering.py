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
from collections.abc import Collection, Mapping, Sequence, Set
from functools import cached_property

import attrs
import networkx as nx  # type: ignore[import-untyped]
from immutabledict import immutabledict

from puya import log
from puya.avm import AVMType
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
from puya.ir.visitor import NoOpIRVisitor, ValueProviderVisitor
from puya.ir.visitor_mem_replacer import MemoryReplacer
from puya.utils import lazy_setdefault, symmetric_mapping

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


_PhiArgVNs: typing.TypeAlias = immutabledict[models.BasicBlock, VN]
_ConstType: typing.TypeAlias = models.Constant | models.TemplateVar


@attrs.define
class _GVNTables:
    """Value numbering state, supporting scoped save/restore for dominator-tree walk.

    Scoped state (_register_vn, expr_table, _const_vn, comparison_exprs) is copied
    on child_scope() so that siblings in the dominator tree don't see each other's
    definitions.
    Global state (_vn_counter, _equivalences) is shared by reference across all scopes.
    """

    # --- Global: shared by reference across all scopes ---
    _vn_counter: itertools.count[int] = attrs.field(factory=itertools.count)
    _equivalences: dict[tuple[VN, AVMType], list[models.Register]] = attrs.field(factory=dict)
    # --- Scoped: copied on child_scope() ---
    _register_vn: dict[models.Register, VN] = attrs.field(factory=dict)
    provider_key_to_vns: dict[_ProviderKey, tuple[VN, ...]] = attrs.field(factory=dict)
    _const_vn: dict[_ConstType, VN] = attrs.field(factory=dict)
    comparison_exprs: dict[VN, _IntrinsicKey] = attrs.field(factory=dict)

    def child_scope(self) -> typing.Self:
        """Create a child scope for dominator-tree descent.

        Scoped dicts are shallow-copied; global state is shared by reference.
        """
        return attrs.evolve(
            self,
            register_vn=self._register_vn.copy(),
            provider_key_to_vns=self.provider_key_to_vns.copy(),
            const_vn=self._const_vn.copy(),
            comparison_exprs=self.comparison_exprs.copy(),
        )

    def _next_vn(self) -> VN:
        return next(self._vn_counter)

    def set_register_vn(self, reg: models.Register, vn: VN, *, replaceable: bool = True) -> None:
        """Assign a VN to a register.

        Use replaceable=False for constant copies where the register needs a VN
        for expression hashing but shouldn't participate in replacement.
        """
        if reg in self._register_vn:
            raise InternalError(
                f"register {reg} already has VN={self._register_vn[reg]}", reg.source_location
            )
        self._register_vn[reg] = vn
        if replaceable:
            maybe_avm_type = reg.ir_type.maybe_avm_type
            if not isinstance(maybe_avm_type, str):
                self._equivalences.setdefault((vn, maybe_avm_type), []).append(reg)

    def assign_register_fresh_vn(self, reg: models.Register) -> VN:
        vn = self._next_vn()
        self.set_register_vn(reg, vn)
        return vn

    def lookup_vn(self, value: models.Value) -> VN:
        """Get the VN for any Value (register or constant).

        If a register has not been numbered yet (e.g. a phi argument from a back edge),
        it is conservatively assigned a fresh VN - which is *not* stored.
        """
        if isinstance(value, models.Register):
            try:
                return self._register_vn[value]
            except KeyError:
                # Back-edge or otherwise not-yet-visited register: fresh VN
                return self._next_vn()
        # Constants: intern by value so identical constants share a VN.
        if isinstance(value, _ConstType):
            return lazy_setdefault(self._const_vn, value, lambda _: self._next_vn())
        return self._next_vn()

    @property
    def equivalence_sets(self) -> Collection[Sequence[models.Register]]:
        return self._equivalences.values()


def build_replacements(
    subroutine: models.Subroutine, equivalence_sets: Collection[Sequence[models.Register]]
) -> tuple[set[models.Register], dict[models.Register, models.Register]]:
    """Build the final replacement map with preferred register names.

    Returns (eliminated, register_map) where:
    - eliminated: registers whose definitions (phi or assignment) should be
      removed from the IR.
    - register_map: register replacement/renaming map for MemoryReplacer.
      Includes both eliminations (redundant -> representative) and renames
      (old representative -> preferred name).
    """
    eliminated = set[models.Register]()
    register_map = dict[models.Register, models.Register]()

    for equivalence_set in equivalence_sets:
        if len(equivalence_set) < 2:
            continue

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

        for idx, reg in enumerate(equivalence_set):
            if reg is not replacement:
                register_map[reg] = replacement
                if idx == 0:
                    # The first element is the dominating definition — its definition is
                    # always kept (never eliminated). If it's not the preferred name, its
                    # target gets renamed via register_map.
                    eliminated.add(replacement)
                else:
                    eliminated.add(reg)

    for target in register_map.values():
        if target in register_map:
            raise InternalError(
                f"GVN: replacement chain detected:"
                f" {target.local_id} -> {register_map[target].local_id}"
            )

    return eliminated, register_map


@attrs.frozen
class _ProviderKeyBuilder(ValueProviderVisitor[_ProviderKey | None]):
    """Build a canonical, hashable value expression for a ValueProvider.

    Returns None for side-effecting or unrecognised operations (they get a fresh VN).
    """

    _tables: _GVNTables

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> _ProviderKey | None:
        return _ExtractKey(
            base_vn=self._tables.lookup_vn(read.base),
            base_type=read.base_type,
            index_vns=self._index_vns(read.indexes),
            check_bounds=read.check_bounds,
        )

    @typing.override
    def visit_replace_value(self, write: models.ReplaceValue) -> _ProviderKey | None:
        return _ReplaceKey(
            base_vn=self._tables.lookup_vn(write.base),
            base_type=write.base_type,
            index_vns=self._index_vns(write.indexes),
            value_vn=self._tables.lookup_vn(write.value),
        )

    @typing.override
    def visit_array_concat(self, concat: models.ArrayConcat) -> _ProviderKey:
        return _ArrayConcatKey(
            base_vn=self._tables.lookup_vn(concat.base),
            base_type=concat.base_type,
            items_vn=self._tables.lookup_vn(concat.items),
            item_encoding=concat.item_encoding,
        )

    def _index_vns(self, indexes: tuple[int | models.Value, ...]) -> tuple[_IndexVN, ...]:
        """Compute VNs for aggregate indexes, tagging static ints vs dynamic VNs."""
        return tuple(
            (
                _IndexVN(kind="value", index=self._tables.lookup_vn(idx))
                if isinstance(idx, models.Value)
                else _IndexVN(kind="static", index=idx)
            )
            for idx in indexes
        )

    @typing.override
    def visit_array_length(self, length: models.ArrayLength) -> _ProviderKey | None:
        # Only pure when the base is a stack value, not a slot reference.
        if isinstance(length.base_type, types.SlotType):
            return None
        return _ArrayLengthKey(
            base_vn=self._tables.lookup_vn(length.base),
            base_type=length.base_type,
        )

    @typing.override
    def visit_array_pop(self, pop: models.ArrayPop) -> _ProviderKey:
        return _ArrayPopKey(
            base_vn=self._tables.lookup_vn(pop.base),
            base_type=pop.base_type,
        )

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> None:
        return None  # stateful, leave this up to repeated-reads

    @typing.override
    def visit_bytes_encode(self, encode: models.BytesEncode) -> _ProviderKey | None:
        return _EncodeKey(
            encoding=encode.encoding,
            value_vns=tuple(self._tables.lookup_vn(v) for v in encode.values),
            values_type=encode.values_type,
        )

    @typing.override
    def visit_decode_bytes(self, decode: models.DecodeBytes) -> _ProviderKey | None:
        return _DecodeKey(
            encoding=decode.encoding,
            value_vn=self._tables.lookup_vn(decode.value),
            ir_type=decode.ir_type,
        )

    @typing.override
    def visit_inner_transaction_field(self, intrinsic: models.InnerTransactionField) -> None:
        return None  # stateful - implicitly depends on the most recent itxn_submit

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> _ProviderKey | None:
        op = intrinsic.op
        if op.code not in PURE_AVM_OPS:
            return None
        args = intrinsic.args
        if not args:
            # TODO: handle no-args by keeping the definition but assigning same VN,
            #       and then using that VN in comparison / algebraic identities
            return None
        arg_vns = tuple(self._tables.lookup_vn(a) for a in args)
        # Negation-aware numbering: !(comparison) -> inverse comparison.
        # e.g. !(a < b) gets the same key as (a >= b).
        if op == AVMOp.not_:
            (vn,) = arg_vns
            comp = self._tables.comparison_exprs.get(vn)
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
        return _IntrinsicKey(op=op_key, immediates=tuple(intrinsic.immediates), arg_vns=arg_vns)

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> _ProviderKey | None:
        if not callsub.target.pure:
            return None
        arg_vns = tuple(self._tables.lookup_vn(a) for a in callsub.args)
        return _CallSubKey(target_id=callsub.target.id, arg_vns=arg_vns)

    @typing.override
    def visit_new_slot(self, new_slot: models.NewSlot) -> None:
        return None  # side-effecting

    @typing.override
    def visit_read_slot(self, read_slot: models.ReadSlot) -> None:
        return None  # stateful, leave this up to repeated-reads

    @typing.override
    def visit_value_tuple(self, tup: models.ValueTuple) -> None:
        return None  # catch these on the next pass

    # -- Value subtypes: should be handled specially before reaching the visitor --

    @typing.override
    def visit_register(self, reg: models.Register) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_undefined(self, val: models.Undefined) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_uint64_constant(self, const: models.UInt64Constant) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_biguint_constant(self, const: models.BigUIntConstant) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_bytes_constant(self, const: models.BytesConstant) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_address_constant(self, const: models.AddressConstant) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_method_constant(self, const: models.MethodConstant) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_itxn_constant(self, const: models.ITxnConstant) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_slot_constant(self, const: models.SlotConstant) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_template_var(self, deploy_var: models.TemplateVar) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_compiled_contract_reference(
        self, const: models.CompiledContractReference
    ) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")

    @typing.override
    def visit_compiled_logicsig_reference(
        self, const: models.CompiledLogicSigReference
    ) -> typing.Never:
        raise InternalError("shouldn't get here, Value should be handled specially")


class GVNBlockVisitor(NoOpIRVisitor[None]):
    def __init__(self, tables: _GVNTables):
        self.tables = tables
        self.phi_table = dict[_PhiArgVNs, VN]()

    @cached_property
    def provider_key_builder(self) -> _ProviderKeyBuilder:
        return _ProviderKeyBuilder(self.tables)

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        """Assign a VN to a phi node's register.

        Redundant phis (all args same VN) get the common VN.
        Non-redundant phis are hashed to detect congruent phis at the same block.
        """
        if not phi.args:
            self.tables.assign_register_fresh_vn(phi.register)
            return

        phi_arg_vns = _PhiArgVNs(
            (arg.through, self.tables.lookup_vn(arg.value)) for arg in phi.args
        )

        unique_vns = set(phi_arg_vns.values())
        if len(unique_vns) == 1:
            # Redundant phi: all arguments have the same VN
            (the_vn,) = unique_vns
            self.tables.set_register_vn(phi.register, the_vn)
            logger.debug(f"GVN: redundant phi {phi.register.local_id} (VN={the_vn})")
        else:
            # Non-redundant phi: hash by arg VNs to detect congruent phis at the same block
            existing_vn = self.phi_table.get(phi_arg_vns)
            if existing_vn is not None:
                self.tables.set_register_vn(phi.register, existing_vn)
                logger.debug(f"GVN: congruent phi {phi.register.local_id} (VN={existing_vn})")
            else:
                self.phi_table[phi_arg_vns] = self.tables.assign_register_fresh_vn(phi.register)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        """Assign VNs to an assignment's target registers.

        If the source is a register (copy), propagate its VN.
        If the source is a pure expression and a matching VN already exists,
        the target joins the existing VN's equivalence set.
        Otherwise, assign a fresh VN.
        """
        source = ass.source
        # Copy assignment: propagate VN directly
        if isinstance(source, models.Value):
            (target,) = ass.targets
            vn = self.tables.lookup_vn(source)
            # Copies from constants don't participate in replacement —
            # constant propagation handles those.
            self.tables.set_register_vn(
                target, vn, replaceable=isinstance(source, models.Register)
            )
        else:
            provider_key = source.accept(self.provider_key_builder)
            if provider_key is None:
                # Not a pure expression — fresh VN per target
                for reg in ass.targets:
                    self.tables.assign_register_fresh_vn(reg)
            else:
                existing_vns = self.tables.provider_key_to_vns.get(provider_key)
                if existing_vns is None:
                    target_vns = tuple(
                        self.tables.assign_register_fresh_vn(r) for r in ass.targets
                    )
                    self.tables.provider_key_to_vns[provider_key] = target_vns
                else:
                    for target, existing_vn in zip(ass.targets, existing_vns, strict=True):
                        logger.debug(f"GVN: redundant expr {target.local_id} (VN={existing_vn})")
                        self.tables.set_register_vn(target, existing_vn)

                # Track comparison expressions for negation-aware numbering.
                # Single-target only — comparisons always produce one result.
                if (
                    isinstance(provider_key, _IntrinsicKey)
                    and provider_key.op in _INVERSE_COMPARISONS
                ):
                    (target,) = ass.targets
                    vn = self.tables.lookup_vn(target)
                    self.tables.comparison_exprs[vn] = provider_key


def _process_blocks_pre_order(
    tables: _GVNTables,
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    block: models.BasicBlock,
) -> None:
    """Process a single block in the dominator-tree preorder walk.

    Creates a child scope so entries added in this block are visible to
    dominated children but not to siblings.
    """
    visitor = GVNBlockVisitor(tables)
    for op in block.all_ops:
        op.accept(visitor)

    for child in dom_tree.get(block, []):
        _process_blocks_pre_order(tables.child_scope(), dom_tree, child)


def _refine_phi_congruence(
    subroutine: models.Subroutine,
    eliminated: set[models.Register],
    register_map: dict[models.Register, models.Register],
) -> None:
    """Find phi-cycle equivalences that hash-based numbering missed.

    Resolves phi args through the replacement map (from build_replacements),
    builds a dependency graph of the remaining phis, finds SCCs, and checks
    if all phis in an SCC resolve to the same single external register.

    This catches patterns like:
        x = phi(a, y)
        y = phi(b, x)
    where a and b resolve to the same representative — hash-based GVN assigns
    x and y different VNs (due to back-edge conservatism), but SCC analysis
    reveals they're equal.

    Analogous to how copy_propagation resolves phi args through its replacement
    map to find trivially redundant phis.
    """
    # Collect phis not already handled by build_replacements
    phi_by_register = dict[models.Register, models.Phi]()
    for block in subroutine.body:
        for phi in block.phis:
            if phi.register not in register_map:
                phi_by_register[phi.register] = phi

    if not phi_by_register:
        return

    graph = nx.DiGraph()
    for phi in phi_by_register.values():
        for arg in phi.args:
            resolved = register_map.get(arg.value, arg.value)
            if resolved in phi_by_register:
                graph.add_edge(phi.register, resolved)

    for scc_set in nx.strongly_connected_components(graph):
        if len(scc_set) <= 1:
            continue

        external_regs = set[models.Register]()
        for reg in scc_set:
            phi = phi_by_register[reg]
            for arg in phi.args:
                resolved = register_map.get(arg.value, arg.value)
                if resolved not in scc_set:
                    external_regs.add(resolved)

        if len(external_regs) != 1:
            continue

        (target,) = external_regs
        for reg in sorted(scc_set, key=lambda r: r.local_id):
            if reg.ir_type.maybe_avm_type != target.ir_type.maybe_avm_type:
                continue
            eliminated.add(reg)
            register_map[reg] = target
            logger.debug(f"GVN: SCC phi congruence {reg.local_id} -> {target.local_id}")


def global_value_numbering(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Run GVN on a subroutine.

    Flow: hash-based numbering -> SCC phi congruence -> eliminate.
    """
    tables = _GVNTables()
    for param in subroutine.parameters:
        tables.assign_register_fresh_vn(param)

    start, dom_tree = compute_dominator_tree(subroutine)
    _process_blocks_pre_order(tables, dom_tree, start)
    eliminated, register_map = build_replacements(subroutine, tables.equivalence_sets)

    _refine_phi_congruence(subroutine, eliminated, register_map)

    if not register_map:
        return False

    logger.debug(f"GVN: {len(register_map)} replacement(s) in {subroutine.id}")
    replacer = MemoryReplacer(replacements=register_map)
    for block in subroutine.body:
        phis = []
        for phi in block.phis:
            if phi.register not in eliminated:
                phi.accept(replacer)
                phis.append(phi)
        block.phis[:] = phis
        ops = []
        for op in block.ops:
            if not (isinstance(op, models.Assignment) and eliminated.issuperset(op.targets)):
                op.accept(replacer)
                ops.append(op)
        block.ops[:] = ops
        if block.terminator is not None:
            block.terminator.accept(replacer)
    return True
