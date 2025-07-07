import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence

import attrs

from puya.ir import models as ir
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.models import Register, Subroutine, Value, ValueProvider, ValueTuple
from puya.ir.op_utils import assign_targets
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import IRType
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation


@attrs.define(kw_only=True)
class MutatingRegisterContext(IRMutator, IRRegisterContext):
    temp_prefix: str
    subroutine: ir.Subroutine
    _versions: dict[str, int] = attrs.field()
    _tmp_counters: defaultdict[str, Iterator[int]] = attrs.field(
        factory=lambda: defaultdict(itertools.count)
    )
    _embedded_funcs: Mapping[PuyaLibIR, Subroutine]

    @_versions.default
    def _versions_factory(self) -> dict[str, int]:
        return _VersionGatherer.gather(self.subroutine)

    def process_and_validate(self) -> None:
        for block in self.subroutine.body:
            self.visit_block(block)
        self.subroutine.validate_with_ssa()

    def resolve_embedded_func(self, full_name: PuyaLibIR) -> Subroutine:
        return self._embedded_funcs[full_name]

    def materialise_value_provider(
        self, value_provider: ValueProvider, description: str | Sequence[str]
    ) -> list[Value]:
        if isinstance(value_provider, Value):
            return [value_provider]
        elif isinstance(value_provider, ValueTuple):
            return list(value_provider.values)
        descriptions = (
            [description] * len(value_provider.types)
            if isinstance(description, str)
            else description
        )
        targets: list[Register] = [
            self.new_register(self.next_tmp_name(desc), ir_type, value_provider.source_location)
            for ir_type, desc in zip(value_provider.types, descriptions, strict=True)
        ]
        assign_targets(
            self,
            source=value_provider,
            targets=targets,
            assignment_location=value_provider.source_location,
        )
        return list(targets)

    def _next_version(self, name: str) -> int:
        try:
            version = self._versions[name] + 1
        except KeyError:
            version = 1
        self._versions[name] = version
        return version

    @typing.override
    def new_register(
        self, name: str, ir_type: IRType, location: SourceLocation | None
    ) -> ir.Register:
        return ir.Register(
            name=name,
            version=self._next_version(name),
            ir_type=ir_type,
            source_location=location,
        )

    @typing.override
    def next_tmp_name(self, description: str) -> str:
        counter_value = next(self._tmp_counters[description])
        # temp prefix should ensure uniqueness with other temps
        return ir.TMP_VAR_INDICATOR.join(
            (
                self.temp_prefix,
                description,
                str(counter_value),
            )
        )

    @typing.override
    def add_assignment(
        self, targets: list[ir.Register], source: ir.ValueProvider, loc: SourceLocation | None
    ) -> None:
        self.add_op(ir.Assignment(targets=targets, source=source, source_location=loc))

    @typing.override
    def add_op(self, op: ir.Op) -> None:
        self.current_block_ops.append(op)


@attrs.define
class _VersionGatherer(IRTraverser):
    versions: dict[str, int] = attrs.field(factory=dict)

    @classmethod
    def gather(cls, sub: ir.Subroutine) -> dict[str, int]:
        visitor = cls()
        visitor.visit_all_blocks(sub.body)
        return visitor.versions

    def visit_register(self, reg: ir.Register) -> None:
        self.versions[reg.name] = max(self.versions.get(reg.name, 0), reg.version)
