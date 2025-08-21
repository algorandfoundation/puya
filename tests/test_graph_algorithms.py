import operator
from unittest.mock import Mock

import attrs
import pytest

from puya.ir.optimize.repeated_code_elimination import compute_dominator_tree


@attrs.frozen(kw_only=True)
class ComputeDominatorData:
    name: str
    preds: dict[int, list[int]]
    start: int
    dom_tree: dict[int, list[int]]


@pytest.mark.parametrize(
    "data",
    [
        ComputeDominatorData(
            name="simple_linear",
            preds={0: [], 1: [0], 2: [1]},
            start=0,
            dom_tree={0: [1], 1: [2]},
        ),
        ComputeDominatorData(
            name="linear_with_start_loop",
            preds={0: [1], 1: [0], 2: [1]},
            start=0,
            dom_tree={0: [1], 1: [2]},
        ),
        ComputeDominatorData(
            name="linear_with_unreachable",
            preds={0: [], 1: [0], 2: [], 3: [2]},
            start=0,
            dom_tree={0: [1]},
        ),
        ComputeDominatorData(
            name="multiple_loops_including_start",
            preds={
                2: [3],
                3: [2],
                7: [2],
                12: [7, 13],
                13: [12],
                14: [12],
            },
            start=2,
            dom_tree={
                2: [3, 7],
                7: [12],
                12: [13, 14],
            },
        ),
    ],
    ids=operator.attrgetter("name"),
)
def test_compute_dominators(data: ComputeDominatorData) -> None:
    succs = dict[int, list[int]]()
    for succ, preds in data.preds.items():
        for pred in preds:
            succs.setdefault(pred, []).append(succ)
    blocks = {n: Mock() for n in data.preds}
    for n, b in blocks.items():
        b.configure_mock(
            id=n,
            predecessors=[blocks[p] for p in data.preds[n]],
            successors=[blocks[s] for s in succs.get(n, [])],
        )
    sub = Mock(body=list(blocks.values()), entry=blocks[data.start])
    result = compute_dominator_tree(sub)
    result_ids = {b.id: [d.id for d in ds] for b, ds in result[1].items()}
    assert result_ids == data.dom_tree
