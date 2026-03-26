import typing
from collections.abc import Sequence

import networkx as nx  # type: ignore[import-untyped]

from puya.errors import InternalError
from puya.ir import models
from puya.ir.visitor import IRTraverser


def get_definition(
    subroutine: models.Subroutine, register: models.Register, *, should_exist: bool = True
) -> models.Assignment | models.Phi | None:
    if register in subroutine.parameters:
        return None
    for block in subroutine.body:
        for phi in block.phis:
            if phi.register == register:
                return phi
        for op in block.ops:
            if isinstance(op, models.Assignment) and register in op.targets:
                return op
    if should_exist:
        raise InternalError(f"Register is not defined: {register}", subroutine.source_location)
    return None


class _HighLevelOpError(Exception):
    pass


class HasHighLevelOps(IRTraverser):
    @classmethod
    def check(cls, body: Sequence[models.BasicBlock]) -> bool:
        try:
            HasHighLevelOps().visit_all_blocks(body)
        except _HighLevelOpError:
            return True
        return False

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_box_write(self, write: models.BoxWrite) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_array_length(self, length: models.ArrayLength) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_array_pop(self, pop: models.ArrayPop) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_array_concat(self, concat: models.ArrayConcat) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_replace_value(self, write: models.ReplaceValue) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_bytes_encode(self, encode: models.BytesEncode) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_decode_bytes(self, decode: models.DecodeBytes) -> None:
        raise _HighLevelOpError


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
