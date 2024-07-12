from collections import deque
from collections.abc import Iterator

from puya.ir import models


def bfs_block_order(start: models.BasicBlock) -> Iterator[models.BasicBlock]:
    q = deque[models.BasicBlock]()
    q.append(start)
    visited = {start}
    while q:
        block = q.popleft()
        yield block
        for succ in block.successors:
            if succ not in visited:
                q.append(succ)
                visited.add(succ)
