import functools
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from functools import cached_property
from itertools import chain

import attrs
import networkx as nx  # type: ignore[import-untyped]

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.mir import models as mir
from puya.mir.context import ProgramMIRContext
from puya.mir.stack import Stack
from puya.mir.vla import VariableLifetimeAnalysis
from puya.utils import attrs_extend, unique

logger = log.get_logger(__name__)


def x_stack_allocation(_ctx: ProgramMIRContext, sub: mir.MemorySubroutine) -> None:
    """
    This pass allocates variables to the transfer region of the stack 'x-stack', which is used to
    transfer variables between blocks.

    1. Construct block and edge set information
        a. Block Records contain liveness information from blocks
        b. Edge Sets formed from Block Records and CFG
        c. Edge Set Groups are connected components of edge sets

    2. Determine x-stack candidates
        * live-out from every out-block (intersection of live_out)
        * live-in to at least one in-block, with at most one in-block where the local isn't live-in

    3. Determine variables to exclude from the x-stack
        * unschedulable locals - locals that are stores/loads but not candidates
        * transit mismatches - x_stack_in and x_stack_out disagree
        * expensive transits - variables that would require a lot of shuffling

    4. Order x-stacks
        a. Calculate a ranking of variables to reduce stack shuffles
        b. Determine x-stack for each edge set. Candidates - excluded_locals, ordered by ranking

    5. Apply x-stack to each block
        a. Drop variables that are not live-in on block entry, except those a stack-consuming
           terminator will clean up anyway
        b. Replace existing AbstractLoad and AbstractStore nodes that correspond with x_stack_in
           and x_stack_out variables; load only transiting locals are copied
        c. Shuffle any other variables that are on the x_stack so they conform to x_stack_out
    """
    # this is basically baileys algorithm
    vla = VariableLifetimeAnalysis(sub)
    edge_sets = _build_edge_sets(sub, vla)
    if not edge_sets:
        return
    logger.debug(f"Found {len(edge_sets)} edge set/s for {sub.signature.name}")

    records = _records_from_edge_sets(edge_sets)
    edge_set_groups = _group_connected_edge_sets(edge_sets)
    _schedule_edge_sets(records, edge_set_groups)

    for edge_set in edge_sets:
        x_stack_out = edge_set.out_blocks[0].block.x_stack_out
        if not x_stack_out:
            continue
        x_stack = ", ".join(x_stack_out)
        for out_block in edge_set.out_blocks:
            for in_block in edge_set.in_blocks:
                logger.debug(
                    f"shared x-stack for {out_block.block} -> {in_block.block}: {x_stack}"
                )
    _add_x_stack_ops(sub, edge_sets)


@attrs.define(eq=False)
class _BlockRecord:
    block: mir.MemoryBasicBlock
    local_id_stores: frozenset[str]
    local_id_loads: frozenset[str]
    live_in: frozenset[str]
    live_out: frozenset[str]
    # a block can belong to up to two edge sets, once as an in block and once as an out block
    edge_set_in: "_EdgeSet | None" = attrs.field(default=None, repr=False)
    edge_set_out: "_EdgeSet | None" = attrs.field(default=None, repr=False)

    @staticmethod
    def by_index(block: "_BlockRecord") -> int:
        return block.block.id

    @property
    def x_stack_in_candidates(self) -> frozenset[str]:
        return self.edge_set_in.x_stack_candidates if self.edge_set_in else frozenset()

    @property
    def x_stack_out_candidates(self) -> frozenset[str]:
        return self.edge_set_out.x_stack_candidates if self.edge_set_out else frozenset()

    @property
    def unschedulable_locals(self) -> frozenset[str]:
        return (self.local_id_stores - self.x_stack_out_candidates) | (
            self.local_id_loads - self.x_stack_in_candidates
        )

    @property
    def transit_mismatches(self) -> frozenset[str]:
        x_in = self.x_stack_in_candidates
        x_out = self.x_stack_out_candidates
        if not x_in and not x_out:
            return frozenset()
        # Defined before us and consumed after us (we may read them but not modify them)
        transit_eligible = (x_in & x_out) - self.local_id_stores
        # Input values that should be consumed if used from the x-stack
        effective_loads = self.local_id_loads - transit_eligible
        # Input values that we will have to drop
        droppable = x_in - x_out - self.live_in
        return frozenset((x_in - effective_loads - droppable) ^ (x_out - self.local_id_stores))


def _is_local_used_enough(local_id: str, in_blocks: frozenset[_BlockRecord]) -> bool:
    consuming = frozenset(b for b in in_blocks if local_id in b.live_in)
    return len(in_blocks) - len(consuming) <= 1


@attrs.define(eq=False)
class _EdgeSet:
    out_blocks: Sequence[_BlockRecord] = attrs.field(
        converter=tuple[_BlockRecord, ...], validator=attrs.validators.min_len(1)
    )
    in_blocks: Sequence[_BlockRecord] = attrs.field(
        converter=tuple[_BlockRecord, ...], validator=attrs.validators.min_len(1)
    )

    @property
    def all_blocks(self) -> Iterable[_BlockRecord]:
        yield from self.out_blocks
        yield from self.in_blocks

    @property
    def sort_id(self) -> int:
        return self.out_blocks[0].block.id

    @cached_property
    def x_stack_candidates(self) -> frozenset[str]:
        """Locals admissible on the x-stack: live-out everywhere, live-in enough times."""
        out_intersection = frozenset(self.out_blocks[0].live_out).intersection(
            *(out_block.live_out for out_block in self.out_blocks[1:])
        )
        in_blocks = frozenset(self.in_blocks)
        return frozenset(
            local_id for local_id in out_intersection if _is_local_used_enough(local_id, in_blocks)
        )

    @cached_property
    def stable_locals(self) -> frozenset[str]:
        """Subset of x_stack_candidates with consistent positions across all blocks."""

        def last_stored_order(block: mir.MemoryBasicBlock) -> Sequence[str]:
            return unique(
                op.local_id
                for op in reversed(block.ops)
                if isinstance(op, mir.AbstractStore) and op.local_id in candidates_for_lcs
            )

        def first_loaded_order(block: mir.MemoryBasicBlock) -> Sequence[str]:
            return unique(
                op.local_id
                for op in block.ops
                if isinstance(op, mir.AbstractLoad) and op.local_id in candidates_for_lcs
            )

        live_sets = chain(
            (out_block.live_in for out_block in self.out_blocks),
            (in_block.live_out for in_block in self.in_blocks),
        )
        live_beyond = frozenset[str](live_var for live_set in live_sets for live_var in live_set)
        candidates_for_lcs = self.x_stack_candidates & live_beyond
        ordered_candidates = [
            *(last_stored_order(out_block.block) for out_block in self.out_blocks),
            *(first_loaded_order(in_block.block) for in_block in self.in_blocks),
        ]
        return frozenset(_find_longest_common_subsequence(ordered_candidates))

    def __attrs_post_init__(self) -> None:
        for block in self.out_blocks:
            assert block.edge_set_out is None
            block.edge_set_out = self
        for block in self.in_blocks:
            assert block.edge_set_in is None
            block.edge_set_in = self


def _build_edge_sets(
    sub: mir.MemorySubroutine, vla: VariableLifetimeAnalysis
) -> Sequence[_EdgeSet]:
    block_name_records = dict[str, _BlockRecord]()
    for block in sub.body:
        local_id_stores = set[str]()
        local_id_loads = set[str]()
        for op in block.ops:
            if isinstance(op, mir.AbstractStore):
                assert (
                    op.local_id not in local_id_stores
                ), f">1 AbstractStore in {block.block_name}"
                local_id_stores.add(op.local_id)
            elif isinstance(op, mir.AbstractLoad):
                assert op.local_id not in local_id_loads, f">1 AbstractLoad in {block.block_name}"
                local_id_loads.add(op.local_id)
        block_name_records[block.block_name] = _BlockRecord(
            block=block,
            local_id_stores=frozenset(local_id_stores),
            local_id_loads=frozenset(local_id_loads),
            live_in=frozenset(vla.get_live_in_variables(block.ops[0])),
            live_out=frozenset(vla.get_live_out_variables(block.ops[-1])),
        )

    # given blocks 1-8
    # edges: 1->5, 2->4, 2->5, 2->6, 3->5, 7->6, 7->8
    #
    # e.g  1  2  3   7
    #       \/|\/   / \
    #      / \|/ \ /   \
    #     4   5   6     8
    #
    # 1, 2, 3 and 7 form the out_blocks of an edge set
    # 4, 5, 6 and 8 are the in_blocks of the same edge set

    graph = nx.Graph()
    for out_block in block_name_records.values():
        for in_block_name in out_block.block.successors:
            graph.add_edge(("out", out_block), ("in", block_name_records[in_block_name]))

    edge_sets = [
        _EdgeSet(
            out_blocks=_unique_ordered_blocks(n for tag, n in component if tag == "out"),
            in_blocks=_unique_ordered_blocks(n for tag, n in component if tag == "in"),
        )
        for component in nx.connected_components(graph)
    ]
    return sorted(edge_sets, key=lambda s: s.sort_id)


def _records_from_edge_sets(edge_sets: Sequence[_EdgeSet]) -> Sequence[_BlockRecord]:
    return _unique_ordered_blocks(
        record for edge_set in edge_sets for record in edge_set.all_blocks
    )


def _unique_ordered_blocks(blocks: Iterable[_BlockRecord]) -> list[_BlockRecord]:
    return sorted(set(blocks), key=_BlockRecord.by_index)


@attrs.define
class _EdgeSetGroup:
    edge_sets: tuple[_EdgeSet, ...] = attrs.field(converter=tuple[_EdgeSet, ...])

    @cached_property
    def blocks(self) -> frozenset[_BlockRecord]:
        return frozenset(block for edge_set in self.edge_sets for block in edge_set.all_blocks)

    @cached_property
    def penalty_blocks(self) -> frozenset[_BlockRecord]:
        """
        These blocks store a stable local which affect the group's
        x_stack ordering, so transiting through them has a penalty
        """
        return frozenset(
            block
            for edge_set in self.edge_sets
            for block in edge_set.all_blocks
            if edge_set.stable_locals & block.local_id_stores
        )

    @cached_property
    def _multi_use_locals(self) -> frozenset[str]:
        store_counts = Counter[str]()
        load_counts = Counter[str]()
        for block in self.blocks:
            store_counts.update(block.local_id_stores)
            load_counts.update(block.local_id_loads)
        return frozenset(
            local_id
            for local_id in store_counts.keys() | load_counts.keys()
            if store_counts[local_id] > 1 or load_counts[local_id] > 1
        )

    def is_multi_use(self, local_id: str) -> bool:
        return local_id in self._multi_use_locals

    def transit_cost(self, local_id: str) -> int:
        """Returns how many penalty blocks the local_id transits"""
        candidate_blocks = {
            block
            for edge_set in self.edge_sets
            if local_id in edge_set.x_stack_candidates
            for block in edge_set.all_blocks
            if block in self.penalty_blocks
        }
        return sum(
            1
            for block in candidate_blocks
            if local_id not in block.local_id_stores and local_id not in block.local_id_loads
        )

    def expensive_transits(self) -> frozenset[str]:
        non_stable_locals = frozenset(
            local_id
            for edge_set in self.edge_sets
            for local_id in edge_set.x_stack_candidates
            if local_id not in edge_set.stable_locals
        )
        return frozenset(
            local_id
            for local_id in non_stable_locals
            if not self.is_multi_use(local_id)
            and self.transit_cost(local_id) >= _MAX_TRANSIT_BLOCKS
        )

    def ranked_locals(self) -> Sequence[str]:
        """
        Order x_stack_candidates across the group so locals stored later in predecessors
        and loaded earlier in successors land shallower, with transient locals near the top.
        """
        # collect per-local observations
        last_store_position = dict[str, tuple[int, int]]()
        last_store_local_per_block = dict[_BlockRecord, str]()

        # 0 = top of x-stack, increasing values = deeper; lower averages prefer the shallow end
        position_from_top = defaultdict[str, list[int]](list)
        edge_sets_per_local = defaultdict[str, list[_EdgeSet]](list)
        for edge_set in self.edge_sets:
            for out_block in edge_set.out_blocks:
                stored_locals = []
                for op_idx, op in enumerate(out_block.block.ops):
                    if isinstance(op, mir.AbstractStore):
                        stored_locals.append(op.local_id)
                        key = (out_block.block.id, op_idx)
                        last_store_position[op.local_id] = max(
                            key, last_store_position.get(op.local_id, key)
                        )
                if stored_locals:
                    last_store_local_per_block[out_block] = stored_locals[-1]
                for top_idx, local_id in enumerate(reversed(stored_locals)):
                    position_from_top[local_id].append(top_idx)
            for in_block in edge_set.in_blocks:
                loaded_locals = [
                    op.local_id for op in in_block.block.ops if isinstance(op, mir.AbstractLoad)
                ]
                for top_idx, local_id in enumerate(loaded_locals):
                    position_from_top[local_id].append(top_idx)
            for local_id in edge_set.x_stack_candidates:
                edge_sets_per_local[local_id].append(edge_set)

        # detect solo transients
        def is_last_transient(local_id: str, edge_set: _EdgeSet) -> bool:
            storing_blocks = [
                block for block in edge_set.out_blocks if local_id in block.local_id_stores
            ]
            return bool(storing_blocks) and all(
                last_store_local_per_block[block] == local_id for block in storing_blocks
            )

        solo_transients = {
            local_id
            for local_id, es_list in edge_sets_per_local.items()
            if len(es_list) == 1 and is_last_transient(local_id, es_list[0])
        }

        # used to rank x-stack
        def shallowness_rank(local_id: str) -> tuple[bool, float, tuple[int, int], str]:
            is_solo = local_id in solo_transients
            scores = position_from_top.get(local_id, ())
            # pure-transit locals (no store/load evidence) sink to the bottom
            avg_depth_from_top = sum(scores) / len(scores) if scores else float("inf")
            # negated so shallower observations sort later and land on top of the x-stack
            shallowness = -avg_depth_from_top
            # ties broken by latest-stored, then local_id for determinism
            store_pos = last_store_position.get(local_id, (-1, -1))
            return is_solo, shallowness, store_pos, local_id

        return sorted(edge_sets_per_local, key=shallowness_rank)


def _schedule_edge_sets(
    records: Sequence[_BlockRecord], edge_set_groups: Sequence[_EdgeSetGroup]
) -> None:
    excluded_locals = {
        local_id
        for record in records
        for local_id in record.unschedulable_locals | record.transit_mismatches
    }
    # Heuristic: exclude locals transiting through multiple blocks that may have a strict x-stack
    # ordering (penalty blocks). See _MAX_TRANSIT_BLOCKS
    excluded_locals.update(
        local_id for group in edge_set_groups for local_id in group.expensive_transits()
    )

    all_x_stack_local_ids = set[str]()
    for group in edge_set_groups:
        ranked = group.ranked_locals()
        for edge_set in group.edge_sets:
            x_stack = tuple(
                local_id
                for local_id in ranked
                if local_id in edge_set.x_stack_candidates and local_id not in excluded_locals
            )
            all_x_stack_local_ids.update(x_stack)
            for out_record in edge_set.out_blocks:
                out_record.block.x_stack_out = x_stack
            for in_record in edge_set.in_blocks:
                in_record.block.x_stack_in = x_stack

    if all_x_stack_local_ids:
        logger.debug(f"Allocated to x-stack: {', '.join(sorted(all_x_stack_local_ids))}")


def _find_longest_common_subsequence(candidates: Sequence[Sequence[str]]) -> Sequence[str]:
    @functools.cache
    def lcs(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
        if not left or not right:
            return ()
        if left[-1] == right[-1]:
            return (*lcs(left[:-1], right[:-1]), left[-1])
        return max(lcs(left[:-1], right), lcs(left, right[:-1]), key=_len_and_value)

    shared, *others = sorted({tuple(candidate) for candidate in candidates}, key=_len_and_value)
    for other in others:
        shared = lcs(shared, other)
    return shared


def _len_and_value(value: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
    return len(value), value


# live-through locals are demoted when they would transit at least this many penalty blocks
# current threshold chosen empirically via poe size_diff
# | _MAX_TRANSIT_BLOCKS | O1 bytes | O2 bytes | O1 ops | O2 ops |
# |---------------------|----------|----------|--------|--------|
# | 0                   | 0        | 0        | 0      | 0      |
# | 1                   | -103     | -130     | -58    | -67    |
# | 2                   | -153     | -227     | -94    | -118   |
# | 3                   | -128     | -216     | -78    | -111   |
# | 4                   | -131     | -246     | -76    | -128   |
# | 5                   | -131     | -246     | -76    | -128   |
_MAX_TRANSIT_BLOCKS = 2


def _group_connected_edge_sets(edge_sets: Sequence[_EdgeSet]) -> Sequence[_EdgeSetGroup]:
    graph = nx.Graph((edge_set, block) for edge_set in edge_sets for block in edge_set.all_blocks)

    groups = [
        _EdgeSetGroup(
            sorted(
                (node for node in component if isinstance(node, _EdgeSet)),
                key=lambda s: s.sort_id,
            )
        )
        for component in nx.connected_components(graph)
    ]
    return sorted(groups, key=lambda g: g.edge_sets[0].sort_id)


def _add_x_stack_ops(sub: mir.MemorySubroutine, edge_sets: Sequence[_EdgeSet]) -> None:
    local_id_atypes = sub.local_id_types
    for record in _records_from_edge_sets(edge_sets):
        _add_x_stack_ops_to_block(sub, record, local_id_atypes)


def _add_x_stack_ops_to_block(
    sub: mir.MemorySubroutine, record: _BlockRecord, local_id_atypes: Mapping[str, AVMType]
) -> None:
    block = record.block
    x_in = set(block.x_stack_in)
    x_out_index = {local_id: idx for idx, local_id in enumerate(block.x_stack_out)}

    stack_consumed_at_end_of_block = block.terminator.consumes_stack
    if not stack_consumed_at_end_of_block:
        transit = x_in & x_out_index.keys()
        drops = x_in - x_out_index.keys() - record.live_in
    else:
        # when the terminator consumes the x-stack on exit, only dead values above a load need
        # explicit drops - otherwise loads would be deeper and cost more than the drop.
        # dead values at or below the deepest load are handled by the terminator
        deepest_load_idx = next(
            (
                idx
                for idx, local_id in enumerate(block.x_stack_in)
                if local_id in record.local_id_loads
            ),
            len(block.x_stack_in),
        )
        drops = {
            local_id
            for idx, local_id in enumerate(block.x_stack_in)
            if idx > deepest_load_idx and local_id not in record.live_in
        }
        transit = x_in - record.local_id_loads - drops
    copy_eligible = transit - record.local_id_stores

    stack = Stack.begin_block(sub, block)
    new_mem_ops = list[mir.Op]()

    for local_id in sorted(drops, key=stack.x_stack.index, reverse=True):
        load = mir.LoadXStack(
            local_id=local_id,
            depth=stack.x_stack_depth_for_local(local_id),
            copy=False,
            atype=local_id_atypes[local_id],
            source_location=None,
        )
        pop = mir.Pop(n=1, source_location=None)
        load.accept(stack)
        pop.accept(stack)
        new_mem_ops += (load, pop)

    for op in block.mem_ops:
        if isinstance(op, mir.AbstractStore) and op.local_id in x_out_index:
            target_idx = x_out_index[op.local_id]
            # preserve x_stack_out order by inserting before the first x_out local in stack with
            # a greater-or-equal target, regardless of op ordering or transit-out drops
            insert_pos = next(
                (
                    idx
                    for idx, local_id in enumerate(stack.x_stack)
                    if local_id in x_out_index and x_out_index[local_id] >= target_idx
                ),
                len(stack.x_stack),
            )
            op = attrs_extend(
                mir.StoreXStack,
                op,
                depth=stack.x_stack_depth_for_index(insert_pos),
                source_location=op.source_location,
            )
        elif isinstance(op, mir.AbstractLoad) and op.local_id in x_in:
            op = attrs_extend(
                mir.LoadXStack,
                op,
                depth=stack.x_stack_depth_for_local(op.local_id),
                copy=op.local_id in copy_eligible,
                produces=attrs.NOTHING,  # explicitly force default value
            )
        new_mem_ops.append(op)
        op.accept(stack)
    block.mem_ops[:] = new_mem_ops

    unmatched_stores = x_out_index.keys() - record.local_id_stores - transit
    if unmatched_stores:
        raise InternalError(
            f"Failed to copy {', '.join(sorted(unmatched_stores))} to the x-stack",
            location=block.source_location,
        )
    unmatched_loads = x_in - copy_eligible - record.local_id_loads - transit - drops
    if unmatched_loads:
        raise InternalError(
            f"Failed to move {', '.join(sorted(unmatched_loads))} from the x-stack",
            location=block.source_location,
        )

    if not stack_consumed_at_end_of_block and tuple(stack.x_stack) != block.x_stack_out:
        _reorder_x_stack(block, stack, block.x_stack_out, local_id_atypes)


def _reorder_x_stack(
    block: mir.MemoryBasicBlock,
    stack: Stack,
    x_stack_out: tuple[str, ...],
    local_id_atypes: Mapping[str, AVMType],
) -> None:
    for target_idx, local_id in enumerate(x_stack_out):
        current_idx = stack.x_stack.index(local_id)
        if current_idx == target_idx:
            continue
        atype = local_id_atypes[local_id]

        load_op = mir.LoadXStack(
            local_id=local_id,
            depth=stack.x_stack_depth_for_index(current_idx),
            copy=False,
            atype=atype,
            source_location=None,
        )
        block.mem_ops.append(load_op)
        load_op.accept(stack)

        store_op = mir.StoreXStack(
            local_id=local_id,
            depth=stack.x_stack_depth_for_index(target_idx),
            atype=atype,
            source_location=None,
        )
        block.mem_ops.append(store_op)
        store_op.accept(stack)
    if tuple(stack.x_stack) != x_stack_out:
        raise InternalError(
            f"x-stack reorder failed: {tuple(stack.x_stack)} != {x_stack_out}",
            location=block.source_location,
        )
