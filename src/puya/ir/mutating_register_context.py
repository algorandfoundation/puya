import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence

import attrs

from puya.ir import models as ir
from puya.ir._puya_lib import PuyaLibIR
from puya.ir._utils import multi_value_to_values
from puya.ir.models import MultiValue, Subroutine, Value, ValueProvider
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
    _inserted_ops: list[ir.Op] = attrs.field(factory=list, init=False)

    @typing.override
    def visit_block(self, block: ir.BasicBlock) -> None:
        for phi in block.phis:
            phi.accept(self)
            assert not self._inserted_ops, "cannot insert ops before phi node"

        ops = []
        for op in block.ops:
            maybe_replacement = op.accept(self)
            if self._inserted_ops:
                ops.extend(self._inserted_ops)
                self._inserted_ops.clear()
            ops.append(maybe_replacement or op)

        if block.terminator is not None:
            maybe_replacement = block.terminator.accept(self)
            if self._inserted_ops:
                ops.extend(self._inserted_ops)
                self._inserted_ops.clear()
            if maybe_replacement:
                block.terminator = maybe_replacement
        block.ops[:] = ops

    @_versions.default
    def _versions_factory(self) -> dict[str, int]:
        return _VersionGatherer.gather(self.subroutine)

    @typing.override
    def resolve_embedded_func(self, full_name: PuyaLibIR) -> Subroutine:
        return self._embedded_funcs[full_name]

    @typing.override
    def materialise_value_provider(
        self, value_provider: ValueProvider, description: str | Sequence[str]
    ) -> list[Value]:
        if isinstance(value_provider, MultiValue):
            return multi_value_to_values(value_provider)
        descriptions = (
            [description] * len(value_provider.types)
            if isinstance(description, str)
            else description
        )
        targets = [
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
            version = 0
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
        self._inserted_ops.append(op)


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
