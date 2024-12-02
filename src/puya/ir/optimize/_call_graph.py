import typing

import networkx as nx  # type: ignore[import-untyped]

from puya.ir import models


class CallGraph:
    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self._graph = graph
        self._paths = dict(nx.all_pairs_shortest_path(graph))

    @classmethod
    def build(cls, program: models.Program) -> typing.Self:
        graph = nx.MultiDiGraph()
        for sub in program.all_subroutines:
            graph.add_node(sub.id, ref=sub)
        for sub in program.all_subroutines:
            for block in sub.body:
                for op in block.ops:
                    match op:
                        case (
                            models.InvokeSubroutine(target=target)
                            | models.Assignment(source=models.InvokeSubroutine(target=target))
                        ):
                            graph.add_edge(sub.id, target.id)
        return cls(graph)

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
