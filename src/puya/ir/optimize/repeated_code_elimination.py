import typing
from collections.abc import Mapping, Sequence, Set

import attrs
import networkx as nx  # type: ignore[import-untyped]

from puya import log
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models
from puya.ir.optimize.assignments import copy_propagation
from puya.ir.optimize.dead_code_elimination import PURE_AVM_OPS
from puya.ir.visitor import NoOpIRVisitor
from puya.utils import EditSet

logger = log.get_logger(__name__)

type _KnownConsts = Mapping[object, Sequence[models.Register]]


def repeated_expression_elimination(
    context: CompileContext, subroutine: models.Subroutine
) -> bool:
    start, dom_tree = compute_dominator_tree(subroutine)
    modified = False
    while _recursive_rce(dom_tree, start, consts={}, asserted=set()):
        modified = True
        copy_propagation(context, subroutine)
    return modified


def _recursive_rce(
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    block: models.BasicBlock,
    consts: _KnownConsts,
    asserted: Set[models.Value],
) -> bool:
    modified, out_consts, out_asserted = RCEVisitor.apply_to(block, consts, asserted)
    for child in dom_tree.get(block, []):
        modified |= _recursive_rce(dom_tree, child, out_consts, out_asserted)
    return modified


def compute_dominator_tree(
    subroutine: models.Subroutine,
) -> tuple[models.BasicBlock, dict[models.BasicBlock, list[models.BasicBlock]]]:
    block_graph = nx.DiGraph()
    for block in subroutine.body:
        block_graph.add_node(block.id)
        for target in block.successors:
            block_graph.add_edge(block.id, target.id)
    start = subroutine.body[0]
    idom_ids = nx.immediate_dominators(block_graph, start.id)
    dom_tree_ids = dict[int, list[int]]()
    blocks_by_id = {b.id: b for b in subroutine.body}
    for block_id, idom_id in idom_ids.items():
        if block_id == idom_id:
            raise InternalError(
                f"cycle in immediate dominators at block ID = {block_id}",
                blocks_by_id[block_id].source_location,
            )
        dom_tree_ids.setdefault(idom_id, []).append(block_id)
    for child_id_list in dom_tree_ids.values():
        child_id_list.sort()
    dom_tree = {
        blocks_by_id[pid]: [blocks_by_id[c] for c in child_id_list]
        for pid, child_id_list in dom_tree_ids.items()
    }
    return start, dom_tree


@attrs.define(kw_only=True)
class RCEVisitor(NoOpIRVisitor[None]):
    consts: dict[object, Sequence[models.Register]]
    asserted: set[models.Value]
    edits: EditSet[models.Op] = attrs.field(factory=EditSet, init=False)
    op_index: int = attrs.field(default=0, init=False)

    _assignment: models.Assignment | None = None

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        self._assignment = ass
        ass.source.accept(self)
        self._assignment = None

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        # only consider ops with stack args because they're much more likely to
        # produce extra stack manipulations
        if self._assignment is not None and intrinsic.args and intrinsic.op.code in PURE_AVM_OPS:
            # can't use .freeze() as we want to exclude error_message for the key,
            # and evolving the intrinsic to remove the message is slow
            key = (
                models.Intrinsic,
                intrinsic.op,
                tuple(intrinsic.immediates),
                tuple(intrinsic.args),
            )
            self._cache_or_replace(self._assignment, key)

    @typing.override
    def visit_assert(self, assert_: models.Assert) -> None:
        assert_arg = assert_.condition
        if assert_arg in self.asserted:
            logger.debug(f"Removing redundant assert of {assert_arg}")
            self.edits.remove(self.op_index)
        else:
            self.asserted.add(assert_arg)

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> None:
        if self._assignment is not None:
            key = read.freeze()
            self._cache_or_replace(self._assignment, key)

    @typing.override
    def visit_replace_value(self, write: models.ReplaceValue) -> None:
        if self._assignment is not None:
            key = write.freeze()
            self._cache_or_replace(self._assignment, key)

    @typing.override
    def visit_bytes_encode(self, encode: models.BytesEncode) -> None:
        if self._assignment is not None:
            key = encode.freeze()
            self._cache_or_replace(self._assignment, key)

    @typing.override
    def visit_decode_bytes(self, decode: models.DecodeBytes) -> None:
        if self._assignment is not None:
            key = decode.freeze()
            self._cache_or_replace(self._assignment, key)

    def _cache_or_replace(self, ass: models.Assignment, key: object) -> None:
        existing = self.consts.get(key)
        if existing is None:
            self.consts[key] = ass.targets
            return
        logger.debug(
            f"Replacing redundant declaration {ass} with copy of existing registers {existing}"
        )
        source = models.ValueTuple(values=existing, source_location=ass.source_location)
        replacement = models.Assignment(
            targets=ass.targets, source=source, source_location=ass.source_location
        )
        self.edits.add_edit(self.op_index, 1, (replacement,))

    @classmethod
    def apply_to(
        cls, block: models.BasicBlock, consts: _KnownConsts, asserted: Set[models.Value]
    ) -> tuple[bool, _KnownConsts, Set[models.Value]]:
        visitor = cls(consts=dict(consts), asserted=set(asserted))
        for index, op in enumerate(block.ops):
            visitor.op_index = index
            op.accept(visitor)
        return visitor.edits.apply(block.ops), visitor.consts, visitor.asserted
