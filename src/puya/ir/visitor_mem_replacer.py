from typing import Iterable, Sequence

import attrs

from puya.ir import models
from puya.ir.visitor_mutator import IRMutator


@attrs.define
class MemoryReplacer(IRMutator):
    _find: frozenset[models.Register]
    _replacement: models.Register
    replaced: int = 0

    @classmethod
    def apply(
        cls,
        blocks: Sequence[models.BasicBlock],
        *,
        find: Iterable[models.Register] | models.Register,
        replacement: models.Register,
    ) -> int:
        if isinstance(find, models.Register):
            find = [find]
        replacer = cls(find=frozenset(find), replacement=replacement)
        for block in blocks:
            replacer.visit_block(block)
        return replacer.replaced

    def visit_register(self, reg: models.Register) -> models.Register:
        if reg not in self._find:
            return reg
        self.replaced += 1
        return self._replacement
