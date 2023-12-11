import typing

import networkx as nx  # type: ignore[import-untyped]

from puya.ir import models as ir


class CallGraph:
    def __init__(self, graph: nx.DiGraph) -> None:
        self._graph = graph

    @classmethod
    def build(cls, program: ir.Program) -> typing.Self:
        graph = nx.DiGraph()
        for sub in program.all_subroutines:
            for block in sub.body:
                for op in block.ops:
                    match op:
                        case (
                            ir.InvokeSubroutine(target=target)
                            | ir.Assignment(source=ir.InvokeSubroutine(target=target))
                        ):
                            graph.add_edge(sub.full_name, target.full_name)
        return cls(graph)

    def has_path(self, from_: ir.Subroutine, to: ir.Subroutine) -> bool:
        from_name = from_.full_name
        to_name = to.full_name
        if from_name == to_name:
            return True
        # TODO: TEST THIS
        for _, target in nx.dfs_edges(self._graph, source=from_name):  # noqa: SIM110
            if target == to_name:
                return True
        return False
