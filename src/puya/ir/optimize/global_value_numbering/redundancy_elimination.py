import typing
from collections import defaultdict
from collections.abc import Collection, Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir import models
from puya.ir.optimize._utils import DomTree, SSAReadTracker
from puya.ir.optimize.global_value_numbering.tables import VN, GVNTables
from puya.ir.visitor_mem_replacer import MemoryReplacer
from puya.utils import is_list_of

__all__ = [
    "eliminate_redundant_computations",
]

logger = log.get_logger(__name__)


MaybeAVMType: typing.TypeAlias = AVMType | str
VNRepresentativeMap: typing.TypeAlias = dict[tuple[VN, MaybeAVMType], models.Register]


def eliminate_redundant_computations(
    subroutine: models.Subroutine, tables: GVNTables, dom_tree: DomTree, ssa_reads: SSAReadTracker
) -> bool:
    """Replace each redundant computation with a dominating equivalent (same VN)."""
    builder = RedundancyEliminator(tables, dom_tree, ssa_reads)
    modified = builder.run(subroutine)
    return modified


@attrs.frozen
class RedundancyEliminator:
    tables: GVNTables
    dom_tree: DomTree
    ssa_reads: SSAReadTracker
    # Keyed by (VN, AVMType): the first register seen on a dominator path is the rep;
    # later same-key registers are appended and can be replaced by it.
    all_sets: defaultdict[models.Register, list[models.Register]] = attrs.field(
        factory=lambda: defaultdict(list), init=False
    )

    def run(self, subroutine: models.Subroutine) -> bool:
        # Seed with parameters — they dominate all blocks
        initial_scope = VNRepresentativeMap()
        for param in subroutine.parameters:
            keep_param = self._keep_defn(param, initial_scope)
            assert keep_param
        modified = self._walk(self.dom_tree.root, initial_scope)
        equivalence_sets = [s for s in self.all_sets.values() if len(s) > 1]
        register_replacements = build_replacements(subroutine, equivalence_sets)
        if register_replacements:
            logger.debug(f"GVN: {len(register_replacements)} replacement(s) in {subroutine.id}")
            replaced = MemoryReplacer.apply(subroutine.body, replacements=register_replacements)
            if replaced > 0:
                modified = True
        return modified

    def _keep_defn(
        self, reg: models.Register, vn_to_rep: VNRepresentativeMap, *, force_new_rep: bool = False
    ) -> bool:
        vn = self.tables.register_vn[reg]
        key = (vn, reg.ir_type.maybe_avm_type)
        if force_new_rep:
            rep = vn_to_rep[key] = reg
        else:
            rep = vn_to_rep.setdefault(key, reg)
        self.all_sets[rep].append(reg)
        return rep == reg

    def _walk(self, block: models.BasicBlock, vn_to_rep: VNRepresentativeMap) -> bool:
        modified = False
        scope = dict(vn_to_rep)
        phis = []
        for phi in block.phis:
            if self._keep_defn(phi.register, scope):
                phis.append(phi)
            else:
                modified = True
                self.ssa_reads.remove(phi)
        block.phis[:] = phis

        ops = []
        for op in block.ops:
            ops.append(op)
            if isinstance(op, models.Assignment):
                match op.source:
                    case models.Constant():
                        pass
                    case models.ValueTuple(values=values) if is_list_of(values, models.Constant):  # type: ignore[type-abstract]
                        pass
                    case models.Intrinsic(args=[]):
                        # no-arg intrinsic: never matches an external rep, so always
                        # kept (fresh rep per target)
                        for target in op.targets:
                            self._keep_defn(target, scope, force_new_rep=True)
                    case _:
                        # All-or-nothing: drop only if EVERY target has an external
                        # dominating rep. Partial folding would rewrite only some LHS
                        # targets, duplicating Assignment targets and violating SSA.
                        target_keys = [
                            (self.tables.register_vn[t], t.ir_type.maybe_avm_type)
                            for t in op.targets
                        ]
                        all_in_scope = all(k in scope for k in target_keys)
                        # Keeping: register only novel targets as fresh reps, so a same-VN
                        # sibling later in this op resolves against that fresh rep rather than
                        # being marked its replacement.
                        for target, key in zip(op.targets, target_keys, strict=True):
                            if all_in_scope or key not in scope:
                                self._keep_defn(target, scope)
                        if all_in_scope:
                            ops.pop()
                            modified = True
                            self.ssa_reads.remove(op)
        block.ops[:] = ops
        for child in self.dom_tree.children(block):
            modified |= self._walk(child, scope)
        return modified


def build_replacements(
    subroutine: models.Subroutine, equivalence_sets: Collection[Sequence[models.Register]]
) -> dict[models.Register, models.Register]:
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
