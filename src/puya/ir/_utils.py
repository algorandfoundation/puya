import pickle
import typing
from collections import deque
from collections.abc import Collection, Iterator

import attrs

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.ir import models, visitor
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.models import Parameter, Subroutine, SubroutineID
from puya.ir.types_ import wtype_to_ir_type, wtype_to_ir_types
from puya.ir.utils import format_tuple_index
from puya.ir.visitor import NoOpIRVisitor
from puya.parse import SourceLocation
from puya.utils import Address, StableSet, biguint_bytes_eval, method_selector_hash, set_add


def bfs_block_order(start: models.BasicBlock) -> Iterator[models.BasicBlock]:
    q = deque((start,))
    visited = {start}
    while q:
        block = q.popleft()
        yield block
        q.extend(succ for succ in block.successors if set_add(visited, succ))


def make_subroutine(func: awst_nodes.Function, *, allow_implicits: bool) -> Subroutine:
    """Pre-construct subroutine with an empty body"""
    parameters = [
        param
        for arg in func.args
        for param in _expand_tuple_parameters_and_mark_implicit_returns(
            arg.name,
            arg.wtype,
            allow_implicits=allow_implicits,
            source_location=arg.source_location,
        )
    ]
    returns = wtype_to_ir_types(func.return_type, func.source_location)
    return Subroutine(
        id=SubroutineID(func.full_name),
        short_name=func.short_name,
        parameters=parameters,
        returns=returns,
        body=[],
        inline=func.inline,
        source_location=func.source_location,
    )


def _expand_tuple_parameters_and_mark_implicit_returns(
    name: str, typ: wtypes.WType, *, allow_implicits: bool, source_location: SourceLocation
) -> Iterator[Parameter]:
    if isinstance(typ, wtypes.WTuple):
        for item_idx, item_type in enumerate(typ.types):
            item_name = format_tuple_index(typ, name, item_idx)
            yield from _expand_tuple_parameters_and_mark_implicit_returns(
                item_name,
                item_type,
                allow_implicits=allow_implicits,
                source_location=source_location,
            )
    else:
        type_is_mutable = not typ.immutable
        type_is_slot = typ.is_reference
        yield Parameter(
            name=name,
            ir_type=wtype_to_ir_type(typ, source_location),
            version=0,
            implicit_return=(allow_implicits and type_is_mutable and not type_is_slot),
            source_location=source_location,
        )


def get_bytes_constant(key: models.Constant) -> bytes | None:
    return key.accept(_BytesConstantVisitor())


class _BytesConstantVisitor(NoOpIRVisitor[bytes]):
    @typing.override
    def visit_bytes_constant(self, const: models.BytesConstant) -> bytes:
        return const.value

    @typing.override
    def visit_address_constant(self, const: models.AddressConstant) -> bytes:
        return Address.parse(const.value).public_key

    @typing.override
    def visit_method_constant(self, const: models.MethodConstant) -> bytes:
        return method_selector_hash(const.value)

    @typing.override
    def visit_biguint_constant(self, const: models.BigUIntConstant) -> bytes:
        return biguint_bytes_eval(const.value)


def multi_value_to_values(arg: models.MultiValue) -> list[models.Value]:
    if isinstance(arg, models.ValueTuple):
        return list(arg.values)
    else:
        return [arg]


def deep_copy[T](obj: T) -> T:
    """provides a deep copy of obj, should only be used with trusted objects"""
    # pickle is faster than deepcopy
    return typing.cast(T, pickle.loads(pickle.dumps(obj)))  # noqa: S301


@attrs.define
class IRSubroutineCollector(visitor.IRTraverser):
    subs_by_id: dict[models.SubroutineID, models.Subroutine]
    subroutines: StableSet[models.Subroutine] = attrs.field(factory=StableSet)
    referenced_libs: StableSet[PuyaLibIR] = attrs.field(factory=StableSet)

    @classmethod
    def collect(
        cls, subroutines: Collection[models.Subroutine], *, start: models.Subroutine
    ) -> StableSet[models.Subroutine]:
        collector = cls(subs_by_id={s.id: s for s in subroutines})
        collector.visit_all_blocks(start.body)
        return collector.subroutines | [
            s for s in subroutines if str(s.id) in collector.referenced_libs
        ]

    def visit_subroutine(self, subroutine: models.Subroutine) -> None:
        if subroutine not in self.subroutines:
            self.subroutines.add(subroutine)
            self.visit_all_blocks(subroutine.body)

    def visit_replace_value(self, _: models.ReplaceValue) -> None:
        self.referenced_libs |= (
            PuyaLibIR.dynamic_array_replace_byte_length_head,
            PuyaLibIR.dynamic_array_replace_dynamic_element,
            PuyaLibIR.static_array_replace_byte_length_head,
            PuyaLibIR.static_array_replace_dynamic_element,
            PuyaLibIR.recalculate_head_for_elements_with_byte_length_head,
        )

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        target = self.subs_by_id[callsub.target]
        self.visit_subroutine(target)
