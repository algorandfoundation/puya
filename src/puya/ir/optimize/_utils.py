import contextlib
import typing
from collections import defaultdict
from collections.abc import Generator, Iterable, Mapping, Sequence, Set
from functools import cached_property

import attrs
import networkx as nx  # type: ignore[import-untyped]

from puya.errors import InternalError
from puya.ir import models
from puya.ir.register_read_collector import RegisterReadCollector
from puya.ir.visitor import IRTraverser
from puya.utils import unique

_AnyOp = models.Op | models.ControlOp | models.Phi


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


@attrs.frozen
class DomTree:
    root: models.BasicBlock
    tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]]

    def children(self, block: models.BasicBlock) -> Sequence[models.BasicBlock]:
        return self.tree.get(block, ())

    @cached_property
    def blocks(self) -> Sequence[models.BasicBlock]:
        """Every block reachable from entry (the root plus all it dominates)."""
        return unique((self.root, *(c for cs in self.tree.values() for c in cs)))


def compute_dominator_tree(
    subroutine: models.Subroutine,
) -> DomTree:
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
    return DomTree(start, dom_tree)


@attrs.frozen
class SSAReadTracker:
    _data: defaultdict[models.Register, set[_AnyOp]] = attrs.field(
        factory=lambda: defaultdict(set), init=False
    )

    def add(self, op: _AnyOp) -> None:
        for read_reg in self._register_reads(op):
            self._data[read_reg].add(op)

    def remove(self, op: _AnyOp) -> None:
        """Drop `op` from the tracker (e.g. after its block-level removal)."""
        for read_reg in self._register_reads(op):
            self._data[read_reg].discard(op)

    def get(self, reg: models.Register, *, copy: bool = False) -> Iterable[_AnyOp]:
        reads = self._data.get(reg)
        if reads is None:
            return ()
        if copy:
            return reads.copy()
        return reads

    def count(self, reg: models.Register) -> int:
        reads = self._data.get(reg)
        if reads is None:
            return 0
        return len(reads)

    def is_sole_usage(self, reg: models.Register, op: _AnyOp) -> bool:
        try:
            (sole_usage,) = self._data[reg]
        except (KeyError, ValueError):
            return False
        else:
            return sole_usage is op

    @contextlib.contextmanager
    def update(self, op: _AnyOp) -> Generator[None, None, None]:
        old_reads = self._register_reads(op)
        yield
        new_reads = self._register_reads(op)
        for removed_read in old_reads - new_reads:
            self._data[removed_read].remove(op)
        for added_read in new_reads - old_reads:
            self._data[added_read].add(op)

    @staticmethod
    def _register_reads(visitable: models.IRVisitable) -> Set[models.Register]:
        collector = RegisterReadCollector()
        visitable.accept(collector)
        return collector.used_registers
