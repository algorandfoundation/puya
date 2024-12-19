from collections import Counter
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

    def callees(self, sub: models.Subroutine) -> list[tuple[str, int]]:
        return list(Counter(callee_id for callee_id, _ in self._graph.in_edges(sub.id)).items())

    def has_path(self, from_: str, to: str) -> bool:
        try:
            self._paths[from_][to]
        except KeyError:
            return False
        else:
            return True

    def is_auto_recursive(self, sub: models.Subroutine) -> bool:
        return bool(self._graph.has_predecessor(sub.id, sub.id))
