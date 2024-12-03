import typing
from functools import cached_property

import networkx as nx  # type: ignore[import-untyped]

from puya.ir import models


class CallGraph:
    def __init__(self, program: models.Program) -> None:
        self._program = program

    @cached_property
    def _graph(self) -> nx.MultiDiGraph:
        graph = nx.MultiDiGraph()
        for sub in self._program.all_subroutines:
            graph.add_node(sub.id, ref=sub)
        for sub in self._program.all_subroutines:
            for block in sub.body:
                for op in block.ops:
                    match op:
                        case (
                            models.InvokeSubroutine(target=target)
                            | models.Assignment(source=models.InvokeSubroutine(target=target))
                        ):
                            graph.add_edge(sub.id, target.id)
        return graph

    @cached_property
    def _paths(self) -> dict[str, dict[str, object]]:
        return dict(nx.all_pairs_shortest_path(self._graph))

    def has_maybe_inlineable_calls(self, sub: models.Subroutine) -> bool:
        for target_id in self._graph.successors(sub.id):
            target = self._graph.nodes[target_id]["ref"]
            assert isinstance(target, models.Subroutine)
            if sub.inline is not False:
                return True
        return False

    def reference_count(self, sub: models.Subroutine) -> int:
        return typing.cast(int, self._graph.in_degree(sub.id))

    def maybe_reentrant(self, sub: models.Subroutine) -> bool:
        reference_count = self.reference_count(sub)
        if reference_count <= 1:
            return False
        successors = list(self._graph.successors(sub.id))
        if sub.id in successors:
            return True
        for succ in successors:
            try:
                self._paths[succ][sub.id]
            except KeyError:
                pass
            else:
                return True
        return False
