"""Hash-based value numbering with optimistic phi handling.

Assigns a canonical value number (VN) to every SSA definition via a pre-order
dominator-tree walk; equal expressions over equal operand VNs share a VN. Phi cycles
converge via optimistic iteration: un-numbered back-edge args start as the lattice
top and the walk re-runs with refined VNs until the register partition is stable.

References:
    - Briggs, Cooper, Simpson. "Value Numbering." SP&E, 1997.
    - Cooper & Simpson. "SCC-Based Value Numbering." Rice CS-TR95-261.
"""

import typing
from collections.abc import Mapping, Set
from functools import cached_property

import attrs
import networkx as nx  # type: ignore[import-untyped]

from puya import algo_constants, log
from puya.errors import InternalError
from puya.ir import (
    models,
    types_ as types,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._intrinsics import PURE_AVM_OPS
from puya.ir.optimize._utils import DomTree
from puya.ir.optimize.global_value_numbering.intrinsic_folder import IntrinsicFolder
from puya.ir.optimize.global_value_numbering.tables import (
    VN,
    ArrayConcatKey,
    ArrayLengthKey,
    ArrayPopKey,
    CallSubKey,
    DecodeKey,
    EncodeKey,
    ExtractKey,
    GVNTables,
    IndexVN,
    ReplaceKey,
    TemplateVarKey,
)
from puya.ir.types_ import AVMBytesEncoding, PrimitiveIRType
from puya.ir.visitor import NoOpIRVisitor, ValueProviderVisitor
from puya.utils import Address, method_selector_hash

__all__ = [
    "number_values",
]

logger = log.get_logger(__name__)


def number_values(subroutine: models.Subroutine, dom_tree: DomTree) -> GVNTables:
    """Number every SSA def via optimistic iteration to a fixed point."""

    # Re-walks the dominator tree until `register_vn` stops changing: iteration 1
    # treats un-numbered back-edge args as top, later iterations use the previous VNs so
    # cyclic phi congruences surface, and non-redundant phis pin a stable VN so it
    # converges. A pessimistic walk (all phis non-collapsing) produces provisional VNs for
    # find_non_collapsing_phis, whose flagged SCCs then skip iteration.

    reg_to_phi = {phi.register: phi for block in dom_tree.blocks for phi in block.phis}
    pessimistic_tables = GVNTables(subroutine)
    process_blocks_pre_order(
        pessimistic_tables, dom_tree, dom_tree.root, non_collapsing_phis=set(reg_to_phi.values())
    )
    if not reg_to_phi:
        # No phis -> no back-edges; one dominator pre-order walk numbers every def before
        # its uses, so the optimistic re-iteration below would just reproduce these VNs
        return pessimistic_tables

    # Termination: each iteration only downgrades phis (redundant -> stable VN,
    # permanently), so it converges; the SCC pre-pass stops large phi chains from
    # growing the iteration count linearly, so <= 3 in practice. 10 is a safe bound.
    max_iterations = 10

    non_collapsing_phis = find_non_collapsing_phis(reg_to_phi, pessimistic_tables.register_vn)
    tables = GVNTables(subroutine)
    for iteration in range(max_iterations):
        prev_register_vn = dict(tables.register_vn)
        process_blocks_pre_order(
            tables, dom_tree, dom_tree.root, non_collapsing_phis=non_collapsing_phis
        )
        if tables.register_vn == prev_register_vn:
            logger.debug(f"GVN: {subroutine.id} converged after {iteration + 1} iteration(s)")
            return tables

    # We could potentially return the most recent `tables` value here?
    # But the problem is we have no way of testing that, because this limit here is
    # empirically unreachable thus far. Safer to fall back to pure pessimistic phi merging
    # than to have an untested optimisation pathway
    logger.warning(
        f"GVN: {subroutine.id} failed to converge after {max_iterations} iterations",
        location=subroutine.source_location,
    )
    return pessimistic_tables


def process_blocks_pre_order(
    tables: GVNTables,
    dom_tree: DomTree,
    block: models.BasicBlock,
    *,
    non_collapsing_phis: Set[models.Phi],
) -> None:
    visitor = GVNBlockVisitor(tables, non_collapsing_phis=non_collapsing_phis)
    for op in block.all_ops:
        op.accept(visitor)

    for child in dom_tree.children(block):
        process_blocks_pre_order(tables, dom_tree, child, non_collapsing_phis=non_collapsing_phis)


def find_non_collapsing_phis(
    reg_to_phi: Mapping[models.Register, models.Phi],
    provisional_vn: Mapping[models.Register, VN],
) -> Set[models.Phi]:
    # A multi-member SCC with >= 2 distinct external-arg VNs can never collapse,
    # by flagging it here, we prevent large phi chains from having a linear growth
    # effect on the total number of iterations.
    # External cardinality is counted by VN, not Register, so canonicalisation and
    # folding don't  block collapse
    assert reg_to_phi, "didn't expect to be called with no phis"

    graph = nx.DiGraph()
    for phi in reg_to_phi.values():
        graph.add_node(phi)
        for arg in phi.non_self_args:
            producer = reg_to_phi.get(arg.value)
            if producer is not None:
                graph.add_edge(phi, producer)

    result = set[models.Phi]()
    for scc in nx.strongly_connected_components(graph):
        if has_multiple_external_vns(scc, reg_to_phi, provisional_vn):
            result.update(scc)
    return result


def has_multiple_external_vns(
    scc: Set[models.Phi],
    reg_to_phi: Mapping[models.Register, models.Phi],
    provisional_vn: Mapping[models.Register, VN],
) -> bool:
    if len(scc) <= 1:
        return False
    external_vn: VN | None = None
    for phi in scc:
        for arg in phi.non_self_args:
            producer = reg_to_phi.get(arg.value)
            if producer not in scc:
                vn = provisional_vn[arg.value]
                if external_vn is None:
                    external_vn = vn
                elif vn != external_vn:
                    return True
    return False


@attrs.frozen
class ProviderVNBuilder(ValueProviderVisitor[tuple[VN, ...]]):
    # Numbers a ValueProvider: build a canonical key, then look up or assign its VNs.
    # Pure expressions reuse or get a structural VN; side-effecting or opaque providers
    # get fresh VNs so they're never equated.

    _tables: GVNTables

    @cached_property
    def _folder(self) -> IntrinsicFolder:
        return IntrinsicFolder(self._tables)

    def _index_vns(self, indexes: tuple[int | models.Value, ...]) -> tuple[IndexVN, ...]:
        return tuple(
            (
                IndexVN(kind="value", index=self._visit_value(idx))
                if isinstance(idx, models.Value)
                else IndexVN(kind="static", index=idx)
            )
            for idx in indexes
        )

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> tuple[VN, ...]:
        key = ExtractKey(
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
        key = ReplaceKey(
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
        key = ArrayConcatKey(
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
        key = ArrayLengthKey(
            base_vn=base_vn,
            base_type=length.base_type,
        )
        return self._tables.lookup_or_assign_vp(key, length)

    @typing.override
    def visit_array_pop(self, pop: models.ArrayPop) -> tuple[VN, ...]:
        base_vn = self._visit_value(pop.base)
        key = ArrayPopKey(
            base_vn=base_vn,
            base_type=pop.base_type,
        )
        return self._tables.lookup_or_assign_vp(key, pop)

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> tuple[VN, ...]:
        return self._tables.fresh_vns(read)  # stateful

    @typing.override
    def visit_bytes_encode(self, encode: models.BytesEncode) -> tuple[VN, ...]:
        value_vns = tuple(self._visit_value(v) for v in encode.values)
        key = EncodeKey(
            encoding=encode.encoding,
            value_vns=value_vns,
            values_type=encode.values_type,
        )
        return self._tables.lookup_or_assign_vp(key, encode)

    @typing.override
    def visit_decode_bytes(self, decode: models.DecodeBytes) -> tuple[VN, ...]:
        value_vn = self._visit_value(decode.value)
        key = DecodeKey(
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
        if intrinsic.op.code in PURE_AVM_OPS:
            arg_vns = tuple(self._visit_value(a) for a in intrinsic.args)
            return self._folder.number(intrinsic, arg_vns)

        match intrinsic:
            # global is impure in general, but ZeroAddress is constant
            case models.Intrinsic(op=AVMOp.global_, immediates=["ZeroAddress"]):
                folded_bytes = Address.parse(algo_constants.ZERO_ADDRESS).public_key
                return self._tables.const_bytes(folded_bytes, AVMBytesEncoding.base32)
            case _:
                return self._tables.fresh_vns(intrinsic)

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> tuple[VN, ...]:
        if not callsub.target.pure:
            return self._tables.fresh_vns(callsub)
        arg_vns = tuple(self._visit_value(a) for a in callsub.args)
        key = CallSubKey(target_id=callsub.target.id, arg_vns=arg_vns)
        return self._tables.lookup_or_assign_vp(key, callsub)

    @typing.override
    def visit_new_slot(self, new_slot: models.NewSlot) -> tuple[VN, ...]:
        return self._tables.fresh_vns(new_slot)  # side-effecting

    @typing.override
    def visit_read_slot(self, read_slot: models.ReadSlot) -> tuple[VN, ...]:
        return self._tables.fresh_vns(read_slot)  # stateful

    @typing.override
    def visit_value_tuple(self, tup: models.ValueTuple) -> tuple[VN, ...]:
        return tuple(self._visit_value(v) for v in tup.values)

    # -- Value subtypes --

    def _visit_value(self, val: models.Value) -> VN:
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
        if const.ir_type == PrimitiveIRType.bool:
            assert const.value in (0, 1)
            return self._tables.const_bool(const.value)
        return self._tables.const_uint64(const.value)

    @typing.override
    def visit_biguint_constant(self, const: models.BigUIntConstant) -> tuple[VN, ...]:
        return self._tables.const_biguint(const.value)

    @typing.override
    def visit_bytes_constant(self, const: models.BytesConstant) -> tuple[VN, ...]:
        return self._tables.const_bytes(const.value, const.encoding)

    @typing.override
    def visit_address_constant(self, const: models.AddressConstant) -> tuple[VN, ...]:
        evald = Address.parse(const.value).public_key
        return self._tables.const_bytes(evald, AVMBytesEncoding.base32)

    @typing.override
    def visit_method_constant(self, const: models.MethodConstant) -> tuple[VN, ...]:
        evald = method_selector_hash(const.value)
        return self._tables.const_bytes(evald, AVMBytesEncoding.base16)

    @typing.override
    def visit_itxn_constant(self, const: models.ITxnConstant) -> tuple[VN, ...]:
        # itxn constants aren't value-numbered — fresh VN
        return self._tables.fresh_vns(const)

    @typing.override
    def visit_slot_constant(self, const: models.SlotConstant) -> tuple[VN, ...]:
        return self._tables.const_uint64(const.value)

    @typing.override
    def visit_template_var(self, deploy_var: models.TemplateVar) -> tuple[VN, ...]:
        key = TemplateVarKey(name=deploy_var.name)
        return self._tables.lookup_or_assign_const(key)


class GVNBlockVisitor(NoOpIRVisitor[None]):
    def __init__(
        self,
        tables: GVNTables,
        *,
        non_collapsing_phis: Set[models.Phi],
    ):
        self.tables = tables
        # Phis in SCCs that demonstrably can't collapse to one VN (from
        # find_non_collapsing_phis); their redundancy check needs every non-self arg
        # already numbered. The seed walk passes the full set to bootstrap that.
        self.non_collapsing_phis = non_collapsing_phis
        # per-block: the (through -> block) relationship is part of phi identity
        self.phi_table = dict[frozenset[tuple[models.BasicBlock, VN | models.Register]], VN]()

    @cached_property
    def provider_vn_builder(self) -> ProviderVNBuilder:
        return ProviderVNBuilder(self.tables)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        vns = ass.source.accept(self.provider_vn_builder)
        for target, vn in zip(ass.targets, vns, strict=True):
            self.tables.set_register_vn(target, vn)

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        # Optimistic phi numbering. Self-args (arg.value == phi.register) are pre-
        # filtered (non_self_args): at convergence a self-arg's VN equals the phi's
        # own, so it can't disprove redundancy, and keying on its Register would
        # over-distinguish congruent sibling phis. Then, in order:
        #   1. args not yet numbered (back-edges on iter 1) count as top, skipped from
        #      the "all agree" check, so a phi can match a forward VN pre-convergence;
        #   2. all remaining agree -> redundant, inherit that VN;
        #   3. else a block-congruent phi (same key) -> share its VN;
        #   4. else the phi's persistent stable VN.

        if not phi.args:
            # no-arg phi (entry block only): like Undefined, treated as unique — its
            # own stable VN
            self.tables.set_register_vn(phi.register, self.tables.stable_phi_vn(phi))
            return

        real_vns = set[VN]()
        phi_key_entries = list[tuple[models.BasicBlock, VN | models.Register]]()
        any_top = False
        for arg in phi.non_self_args:
            existing_vn = self.tables.register_vn.get(arg.value)
            if existing_vn is None:
                # not numbered yet this walk — optimistic top. Key on the Register so
                # distinct un-numbered back-edges stay distinguishable.
                any_top = True
                phi_key_entries.append((arg.through, arg.value))
            else:
                real_vns.add(existing_vn)
                phi_key_entries.append((arg.through, existing_vn))
        phi_key = frozenset(phi_key_entries)

        # Candidate VN: if all real args agree -> redundant, inherit it; but a guard
        # pins the stable VN instead if that would flip the phi between distinct
        # redundant VNs across iterations (args in a cycle). The guard is redundancy-
        # branch only: applying it to sibling-congruence would split congruent cohorts
        # (stable_phi_vn is per-phi). For non-collapsing phis, redundancy also requires
        # every non-self arg already numbered — no iteration to propagate disagreement.
        candidate: VN | None = None
        if len(real_vns) == 1 and not (phi in self.non_collapsing_phis and any_top):
            (candidate,) = real_vns
            prev_vn = self.tables.register_vn.get(phi.register)
            if prev_vn is not None and prev_vn != candidate:
                candidate = self.tables.stable_phi_vn(phi)
        if candidate is None:
            candidate = self.phi_table.get(phi_key)
        if candidate is None:
            candidate = self.tables.stable_phi_vn(phi)

        self.tables.set_register_vn(phi.register, candidate)
        self.phi_table.setdefault(phi_key, candidate)
