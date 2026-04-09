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

TODO:
    - algebraic identities
    - const intrinsic results
    - byte constant equivalences
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


@attrs.frozen(kw_only=True)
class _ConstKey:
    """Base class for canonical "constant" keys used in the GVN expression table."""


@attrs.frozen(kw_only=True)
class _UInt64ConstKey(_ConstKey):
    value: int


@attrs.frozen(kw_only=True)
class _BytesConstKey(_ConstKey):
    value: bytes


@attrs.frozen(kw_only=True)
class _TemplateVarKey(_ConstKey):
    name: str


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
    register_vn: dict[models.Register, VN] = attrs.field(factory=dict)
    provider_key_to_vns: dict[_ProviderKey, tuple[VN, ...]] = attrs.field(factory=dict)
    const_vn: dict[_ConstKey, VN] = attrs.field(factory=dict)
    comparison_exprs: dict[VN, _IntrinsicKey] = attrs.field(factory=dict)

    def next_vn(self) -> VN:
        return next(self._vn_counter)

    def set_register_vn(self, reg: models.Register, vn: VN) -> None:
        """Assign a VN to a register.

        Use replaceable=False for constant copies where the register needs a VN
        for expression hashing but shouldn't participate in replacement.
        """
        if reg in self.register_vn:
            raise InternalError(
                f"register {reg} already has VN={self.register_vn[reg]}", reg.source_location
            )
        self.register_vn[reg] = vn

    def assign_register_fresh_vn(self, reg: models.Register) -> VN:
        vn = self.next_vn()
        self.set_register_vn(reg, vn)
        return vn


_MaybeAVMType: typing.TypeAlias = AVMType | str


def _build_equivalence_sets(
    subroutine: models.Subroutine,
    tables: _GVNTables,
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    start: models.BasicBlock,
) -> tuple[bool, Collection[Sequence[models.Register]]]:
    """Walk the dominator tree to build equivalence sets respecting dominance.

    Each (VN, AVMType) pair tracks the first register on each dominator path.
    Later registers with the same key are appended — they can safely be replaced
    by the dominating first register.
    """
    modified = False

    all_sets = defaultdict[models.Register, list[models.Register]](list)
    vn_to_uint64_const = {
        vn: const.value
        for const, vn in tables.const_vn.items()
        if isinstance(const, _UInt64ConstKey)
    }

    def _process(
        reg: models.Register,
        vn_to_rep: dict[tuple[VN, _MaybeAVMType], models.Register],
    ) -> None:
        vn = tables.register_vn[reg]
        key = (vn, reg.ir_type.maybe_avm_type)
        rep = vn_to_rep.setdefault(key, reg)
        all_sets[rep].append(reg)

    # Seed with parameters — they dominate all blocks
    initial_scope = dict[tuple[VN, _MaybeAVMType], models.Register]()
    for param in subroutine.parameters:
        _process(param, initial_scope)

    def _walk(
        block: models.BasicBlock,
        vn_to_rep: Mapping[tuple[VN, _MaybeAVMType], models.Register],
        asserted_: Set[VN | models.Value],
    ) -> None:
        nonlocal modified

        scope = dict(vn_to_rep)
        asserted = set(asserted_)
        # TODO: maybe remove redundant definitions as we go?
        for phi in block.phis:
            _process(phi.register, scope)
        for op in block.ops.copy():
            if isinstance(op, models.Assert):
                if isinstance(op.condition, models.Register):
                    condition_vn = tables.register_vn[op.condition]
                    if not set_add(asserted, condition_vn):
                        modified = True
                        block.ops.remove(op)
                        logger.debug(f"removing redundant assert of {op.condition}")
            elif isinstance(op, models.Assignment):
                if len(op.targets) == 1 and not isinstance(op.source, models.Constant):
                    (target,) = op.targets
                    target_vn = tables.register_vn[target]
                    maybe_uint64_const = vn_to_uint64_const.get(target_vn)
                    if maybe_uint64_const is not None:
                        modified = True
                        op.source = models.UInt64Constant(
                            value=maybe_uint64_const, source_location=op.source.source_location
                        )
                        continue

                match op.source:
                    case models.Register():
                        replaceable = True
                    case models.Value():
                        replaceable = False
                    case models.Intrinsic(args=[]):
                        replaceable = False
                    case _:
                        replaceable = True
                if replaceable:
                    for target in op.targets:
                        _process(target, scope)
        for child in dom_tree.get(block, []):
            _walk(child, scope, asserted)

    _walk(start, initial_scope, set())
    return modified, [s for s in all_sets.values() if len(s) > 1]


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
class _ProviderVNBuilder(ValueProviderVisitor[tuple[VN, ...]]):
    """Number a ValueProvider: build a canonical key, look up or assign VNs.

    Returns the VN tuple for pure expressions (either existing or freshly assigned),
    or None for side-effecting or unrecognised operations.
    """

    _tables: _GVNTables

    def _lookup_or_assign(self, key: _ProviderKey, source: models.ValueProvider) -> tuple[VN, ...]:
        try:
            return self._tables.provider_key_to_vns[key]
        except KeyError:
            pass
        vns = self._fresh_vns(source)
        self._tables.provider_key_to_vns[key] = vns
        return vns

    def _fresh_vns(self, vp: models.ValueProvider) -> tuple[VN, ...]:
        vns = tuple(self._tables.next_vn() for _ in vp.types)
        return vns

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
        return self._lookup_or_assign(key, read)

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
        return self._lookup_or_assign(key, write)

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
        return self._lookup_or_assign(key, concat)

    @typing.override
    def visit_array_length(self, length: models.ArrayLength) -> tuple[VN, ...]:
        if isinstance(length.base_type, types.SlotType):
            return self._fresh_vns(length)
        base_vn = self._visit_value(length.base)
        key = _ArrayLengthKey(
            base_vn=base_vn,
            base_type=length.base_type,
        )
        return self._lookup_or_assign(key, length)

    @typing.override
    def visit_array_pop(self, pop: models.ArrayPop) -> tuple[VN, ...]:
        base_vn = self._visit_value(pop.base)
        key = _ArrayPopKey(
            base_vn=base_vn,
            base_type=pop.base_type,
        )
        return self._lookup_or_assign(key, pop)

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> tuple[VN, ...]:
        return self._fresh_vns(read)  # stateful, leave this up to repeated-reads

    @typing.override
    def visit_bytes_encode(self, encode: models.BytesEncode) -> tuple[VN, ...]:
        value_vns = tuple(self._visit_value(v) for v in encode.values)
        key = _EncodeKey(
            encoding=encode.encoding,
            value_vns=value_vns,
            values_type=encode.values_type,
        )
        return self._lookup_or_assign(key, encode)

    @typing.override
    def visit_decode_bytes(self, decode: models.DecodeBytes) -> tuple[VN, ...]:
        value_vn = self._visit_value(decode.value)
        key = _DecodeKey(
            encoding=decode.encoding,
            value_vn=value_vn,
            ir_type=decode.ir_type,
        )
        return self._lookup_or_assign(key, decode)

    @typing.override
    def visit_inner_transaction_field(
        self, intrinsic: models.InnerTransactionField
    ) -> tuple[VN, ...]:
        # stateful - implicitly depends on the most recent itxn_submit
        return self._fresh_vns(intrinsic)

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> tuple[VN, ...]:
        match intrinsic:
            case models.Intrinsic(op=AVMOp.itob, args=[models.UInt64Constant(value=itob_arg)]):
                bytes_const_evald = itob_arg.to_bytes(8, byteorder="big", signed=False)
                bytes_const_key = _BytesConstKey(value=bytes_const_evald)
                return self._const_vn(bytes_const_key)
            case models.Intrinsic(op=AVMOp.bzero, args=[models.UInt64Constant(value=bzero_arg)]):
                if bzero_arg <= 64:
                    bytes_const_evald = b"\x00" * bzero_arg
                    bytes_const_key = _BytesConstKey(value=bytes_const_evald)
                    return self._const_vn(bytes_const_key)
            case models.Intrinsic(op=AVMOp.global_, immediates=["ZeroAddress"]):
                bytes_const_evald = Address.parse(algo_constants.ZERO_ADDRESS).public_key
                bytes_const_key = _BytesConstKey(value=bytes_const_evald)
                return self._const_vn(bytes_const_key)

        op = intrinsic.op
        if op.code not in PURE_AVM_OPS:
            return self._fresh_vns(intrinsic)
        args = intrinsic.args
        arg_vns = tuple(self._visit_value(a) for a in args)
        # Negation-aware numbering: !(comparison) -> inverse comparison.
        # e.g. !(a < b) gets the same key as (a >= b).
        if op == AVMOp.not_:
            (vn,) = arg_vns
            comp = self._tables.comparison_exprs.get(vn)
            if comp is not None:
                inverse_op = _INVERSE_COMPARISONS.get(comp.op)
                if inverse_op is not None:
                    inverse_key = _IntrinsicKey(
                        op=inverse_op,
                        immediates=comp.immediates,
                        arg_vns=comp.arg_vns,
                    )
                    return self._lookup_or_assign(inverse_key, intrinsic)

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
                        | AVMOp.bitwise_xor_bytes
                        | AVMOp.sub
                        | AVMOp.sub_bytes
                    ):
                        const_key = _UInt64ConstKey(value=0)
                        return self._const_vn(const_key)
                    case (
                        AVMOp.eq
                        | AVMOp.eq_bytes
                        | AVMOp.lte
                        | AVMOp.lte_bytes
                        | AVMOp.gte
                        | AVMOp.gte_bytes
                        | AVMOp.div_floor
                        | AVMOp.div_floor_bytes
                    ):
                        const_key = _UInt64ConstKey(value=1)
                        return self._const_vn(const_key)
                    case (
                        AVMOp.bitwise_and
                        | AVMOp.bitwise_and_bytes
                        | AVMOp.bitwise_or
                        | AVMOp.bitwise_or_bytes
                    ):
                        return (vn1,)

        op_key = op
        if op in _COMMUTATIVE_OPS:
            arg_vns = tuple(sorted(arg_vns))
        elif op in _MIRROR_OPS and arg_vns[0] > arg_vns[1]:
            arg_vns = (arg_vns[1], arg_vns[0])
            op_key = _MIRROR_OPS[op]
        key = _IntrinsicKey(op=op_key, immediates=tuple(intrinsic.immediates), arg_vns=arg_vns)
        vns = self._lookup_or_assign(key, intrinsic)
        # Track comparison expressions for negation-aware numbering
        if op_key in _INVERSE_COMPARISONS:
            (result_vn,) = vns
            self._tables.comparison_exprs[result_vn] = key
        return vns

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> tuple[VN, ...]:
        if not callsub.target.pure:
            return self._fresh_vns(callsub)
        arg_vns = tuple(self._visit_value(a) for a in callsub.args)
        key = _CallSubKey(target_id=callsub.target.id, arg_vns=arg_vns)
        return self._lookup_or_assign(key, callsub)

    @typing.override
    def visit_new_slot(self, new_slot: models.NewSlot) -> tuple[VN, ...]:
        return self._fresh_vns(new_slot)  # side-effecting

    @typing.override
    def visit_read_slot(self, read_slot: models.ReadSlot) -> tuple[VN, ...]:
        return self._fresh_vns(read_slot)  # stateful, leave this up to repeated-reads

    @typing.override
    def visit_value_tuple(self, tup: models.ValueTuple) -> tuple[VN, ...]:
        return self._fresh_vns(tup)  # catch these on the next pass

    # -- Value subtypes --

    def _visit_value(self, val: models.Value) -> VN:
        # all Value sub-types have arity of 1
        (vn,) = val.accept(self)
        return vn

    @typing.override
    def visit_undefined(self, val: models.Undefined) -> tuple[VN, ...]:
        return self._fresh_vns(val)

    @typing.override
    def visit_compiled_contract_reference(
        self, const: models.CompiledContractReference
    ) -> tuple[VN, ...]:
        return self._fresh_vns(const)

    @typing.override
    def visit_compiled_logicsig_reference(
        self, const: models.CompiledLogicSigReference
    ) -> tuple[VN, ...]:
        return self._fresh_vns(const)

    @typing.override
    def visit_register(self, reg: models.Register) -> tuple[VN, ...]:
        try:
            return (self._tables.register_vn[reg],)
        except KeyError:
            raise InternalError(
                f"SSA invariant violated: no dominating definition for {reg}"
            ) from None

    def _const_vn(self, const: _ConstKey) -> tuple[VN, ...]:
        vn = lazy_setdefault(self._tables.const_vn, const, lambda _: self._tables.next_vn())
        return (vn,)

    @typing.override
    def visit_uint64_constant(self, const: models.UInt64Constant) -> tuple[VN, ...]:
        key = _UInt64ConstKey(value=const.value)
        return self._const_vn(key)

    @typing.override
    def visit_biguint_constant(self, const: models.BigUIntConstant) -> tuple[VN, ...]:
        evald = biguint_bytes_eval(const.value)
        key = _BytesConstKey(value=evald)
        return self._const_vn(key)

    @typing.override
    def visit_bytes_constant(self, const: models.BytesConstant) -> tuple[VN, ...]:
        key = _BytesConstKey(value=const.value)
        return self._const_vn(key)

    @typing.override
    def visit_address_constant(self, const: models.AddressConstant) -> tuple[VN, ...]:
        evald = Address.parse(const.value).public_key
        key = _BytesConstKey(value=evald)
        return self._const_vn(key)

    @typing.override
    def visit_method_constant(self, const: models.MethodConstant) -> tuple[VN, ...]:
        evald = method_selector_hash(const.value)
        key = _BytesConstKey(value=evald)
        return self._const_vn(key)

    @typing.override
    def visit_itxn_constant(self, const: models.ITxnConstant) -> tuple[VN, ...]:
        # not sure we should be messing with these, give it a fresh VN
        return self._fresh_vns(const)

    @typing.override
    def visit_slot_constant(self, const: models.SlotConstant) -> tuple[VN, ...]:
        key = _UInt64ConstKey(value=const.value)
        return self._const_vn(key)

    @typing.override
    def visit_template_var(self, deploy_var: models.TemplateVar) -> tuple[VN, ...]:
        key = _TemplateVarKey(name=deploy_var.name)
        return self._const_vn(key)


class GVNBlockVisitor(NoOpIRVisitor[None]):
    def __init__(self, tables: _GVNTables):
        self.tables = tables
        self.phi_table = dict[frozenset[tuple[models.BasicBlock, VN | models.Register]], VN]()

    @cached_property
    def provider_vn_builder(self) -> _ProviderVNBuilder:
        return _ProviderVNBuilder(self.tables)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        """Assign VNs to an assignment's target registers.

        If the source is a register (copy), propagate its VN.
        If the source is a pure expression, the builder looks up or assigns VNs.
        Otherwise, assign a fresh VN.
        """
        source = ass.source
        vns = source.accept(self.provider_vn_builder)
        for target, vn in zip(ass.targets, vns, strict=True):
            self.tables.set_register_vn(target, vn)

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        """Assign a VN to a phi node's register.

        Redundant phis (all args same VN) get the common VN.
        Non-redundant phis are hashed to detect congruent phis at the same block.
        """
        # A phi with no args is essentially undefined, and this can only occur in the entry block.
        # We don't treat Undefined as being a singleton, each instance is considered unique for our
        # purposes here - so treat no-arg phis the same.
        if not phi.args:
            self.tables.assign_register_fresh_vn(phi.register)
            return

        # If a register has not been numbered yet (e.g. a phi argument from a back edge),
        # it will not be in the map - in which case to avoid issues, we just use the register
        # itself as the "VN" here in the phis of this block only.
        # This approach is less powerful than if we could somehow assign the "true VN" for
        # each register now without issue, but it is more powerful than the following alternatives:
        # - Ignoring phis with args without a VN yet.
        # - Assigning a register a new VN each time it's seen in a phi arg without caching.
        # Due to the definition of Register equality, it's equivalent to assigning each un-numbered
        # phi-arg register a unique VN within the phis of that block, but without the additional
        # bookkeeping required to do so.
        vns_dict = {
            arg.through: self.tables.register_vn.get(arg.value, arg.value) for arg in phi.args
        }
        match unique(vns_dict.values()):
            case [VN() as unique_vn]:
                self.tables.set_register_vn(phi.register, unique_vn)
                logger.debug(f"GVN: redundant phi {phi.register.local_id} (VN={unique_vn})")
            case _:
                # TODO: handle single Register? for now just give it a VN and move on
                phi_arg_vns = frozenset(vns_dict.items())
                existing_vn = self.phi_table.get(phi_arg_vns)
                if existing_vn is not None:
                    self.tables.set_register_vn(phi.register, existing_vn)
                    logger.debug(f"GVN: congruent phi {phi.register.local_id} (VN={existing_vn})")
                else:
                    self.phi_table[phi_arg_vns] = self.tables.assign_register_fresh_vn(
                        phi.register
                    )


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
        _process_blocks_pre_order(tables, dom_tree, child)


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


def _number_values(
    subroutine: models.Subroutine,
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    start: models.BasicBlock,
) -> _GVNTables:
    tables = _GVNTables()
    for param in subroutine.parameters:
        tables.assign_register_fresh_vn(param)
    _process_blocks_pre_order(tables, dom_tree, start)
    return tables


def global_value_numbering(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Run GVN on a subroutine.

    Flow: hash-based numbering -> SCC phi congruence -> eliminate.
    """
    start, dom_tree = compute_dominator_tree(subroutine)
    tables = _number_values(subroutine, dom_tree, start)
    modified, equivalence_sets = _build_equivalence_sets(subroutine, tables, dom_tree, start)
    eliminated, register_map = build_replacements(subroutine, equivalence_sets)

    _refine_phi_congruence(subroutine, eliminated, register_map)

    if register_map:
        logger.debug(f"GVN: {len(register_map)} replacement(s) in {subroutine.id}")
        replacer = MemoryReplacer(replacements=register_map)
        for block in subroutine.body:
            phis = []
            for phi in block.phis:
                if phi.register in eliminated:
                    modified = True
                else:
                    phi.accept(replacer)
                    phis.append(phi)
            block.phis[:] = phis
            ops = []
            for op in block.ops:
                if isinstance(op, models.Assignment) and eliminated.issuperset(op.targets):
                    modified = True
                else:
                    op.accept(replacer)
                    ops.append(op)
            block.ops[:] = ops
            if block.terminator is not None:
                block.terminator.accept(replacer)
        if replacer.replaced:
            modified = True

    return modified
