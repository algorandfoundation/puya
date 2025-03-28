import operator
from unittest.mock import Mock

import attrs
import pytest

from puya.ir.optimize.repeated_code_elimination import compute_dominators


@attrs.frozen(kw_only=True)
class ComputeDominatorData:
    name: str
    preds: dict[int, list[int]]
    start: int
    doms: dict[int, list[int]]


@pytest.mark.parametrize(
    "data",
    [
        ComputeDominatorData(
            name="simple_linear",
            preds={0: [], 1: [0], 2: [1]},
            start=0,
            doms={0: [], 1: [0], 2: [0, 1]},
        ),
        ComputeDominatorData(
            name="linear_with_start_loop",
            preds={0: [1], 1: [0], 2: [1]},
            start=0,
            doms={0: [], 1: [0], 2: [0, 1]},
        ),
        ComputeDominatorData(
            name="linear_with_unreachable",
            preds={0: [], 1: [0], 2: [], 3: [2]},
            start=0,
            doms={0: [], 1: [0], 2: [], 3: [2]},
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
            doms={
                2: [],
                3: [2],
                7: [2],
                12: [2, 7],
                13: [2, 7, 12],
                14: [2, 7, 12],
            },
        ),
    ],
    ids=operator.attrgetter("name"),
)
def test_compute_dominators(data: ComputeDominatorData) -> None:
    blocks = {n: Mock() for n in data.preds}
    for n, b in blocks.items():
        b.configure_mock(id=n, predecessors=[blocks[p] for p in data.preds[n]])
    sub = Mock(body=list(blocks.values()), entry=blocks[data.start])
    result = compute_dominators(sub)
    result_ids = {b.id: [d.id for d in ds] for b, ds in result.items()}
    assert result_ids == data.doms
