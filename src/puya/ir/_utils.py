from collections import deque
from collections.abc import Iterator

from puya.ir import models
from puya.utils import set_add


def bfs_block_order(start: models.BasicBlock) -> Iterator[models.BasicBlock]:
    q = deque((start,))
    visited = {start}
    while q:
        block = q.popleft()
        yield block
        q.extend(succ for succ in block.successors if set_add(visited, succ))
