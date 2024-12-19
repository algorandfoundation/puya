from collections.abc import Iterable, Mapping

import attrs

from puya.ir import models
from puya.ir.visitor_mutator import IRMutator


@attrs.define
class MemoryReplacer(IRMutator):
    _replacements: Mapping[models.Register, models.Register]
    replaced: int = 0

    @classmethod
    def apply(
        cls,
        blocks: Iterable[models.BasicBlock],
        *,
        replacements: Mapping[models.Register, models.Register],
    ) -> int:
        if not replacements:
            return 0
        replacer = cls(replacements=replacements)
        for block in blocks:
            replacer.visit_block(block)
        return replacer.replaced

    def visit_register(self, reg: models.Register) -> models.Register:
        try:
            replacement = self._replacements[reg]
        except KeyError:
            return reg
        self.replaced += 1
        return replacement
