import enum
import typing
from collections import defaultdict
from collections.abc import Sequence

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir._utils import get_bytes_constant
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import HasHighLevelOps
from puya.ir.types_ import PrimitiveIRType
from puya.ir.visitor import NoOpIRVisitor

logger = log.get_logger(__name__)


def constant_reads_and_unobserved_writes_elimination(
    _: CompileContext, subroutine: models.Subroutine
) -> bool:
    if HasHighLevelOps.check(subroutine.body):
        return False

    any_modified = False
    # TODO: consider dominator blocks
    for block in subroutine.body:
        while _StateTrackingVisitor.optimise(block):
            any_modified = True
    return any_modified


@enum.unique
class _StateType(enum.Enum):
    box = enum.auto()
    app_global = enum.auto()
    app_local = enum.auto()
    slot = enum.auto()


_ReadType = typing.Literal["rw", "len", "extract"]

_StateKey = tuple[models.Value | bytes | _ReadType, ...]


@attrs.define(kw_only=True)
class _StateTrackingVisitor(NoOpIRVisitor[None]):
    modified: bool = attrs.field(default=False, init=False)
    _block: models.BasicBlock
    _read_results: defaultdict[_StateType, dict[_StateKey, Sequence[models.Value]]] = attrs.field(
        factory=lambda: defaultdict(dict)
    )
    _last_write: dict[_StateType, tuple[_StateKey, models.Op]] = attrs.field(factory=dict)

    @classmethod
    def optimise(cls, block: models.BasicBlock) -> bool:
        visitor = cls(block=block)
        for op in block.ops:
            op.accept(visitor)
        return visitor.modified

    def _cached_read(
        self,
        assignment: models.Assignment,
        typ: _StateType,
        key: tuple[models.Value | _ReadType, ...],
        *,
        allow_truncated_reads: bool = False,
    ) -> None:
        # doing a read resets the unobserved-writes cache
        self._last_write.pop(typ, None)

        normalized_key = _normalize_key(key)
        typ_read_results = self._read_results[typ]
        try:
            last_read = typ_read_results[normalized_key]
        except KeyError:
            typ_read_results[normalized_key] = assignment.targets
            return

        if len(last_read) == len(assignment.targets) or (
            allow_truncated_reads and len(last_read) > len(assignment.targets)
        ):
            logger.debug(
                f"replacing {typ.name} read with cached value for key: {_key_str(key)}",
                location=assignment.source.source_location,
            )
            new_source: models.ValueProvider
            try:
                (new_source,) = last_read
            except ValueError:
                new_source = models.ValueTuple(
                    values=last_read[: len(assignment.targets)],
                    source_location=None,
                )
            assignment.source = new_source
            self.modified = True

    def _handle_write(
        self,
        op: models.Op,
        typ: _StateType,
        key: tuple[models.Value | _ReadType, ...],
        values: tuple[models.Value, ...],
    ) -> None:
        # update cache with new value.
        # this is conservative to naively avoid the problem when multiple
        # values point to the same slot
        normalized_key = _normalize_key(key)
        self._read_results[typ] = {normalized_key: values}
        try:
            last_write_key, last_write_op = self._last_write[typ]
        except KeyError:
            pass
        else:
            if last_write_key == normalized_key:
                # remove last_write if it is overwritten with another write, and there
                # are no intervening reads
                logger.debug(
                    f"removing unobserved {typ.name} write to key: {_key_str(key)}",
                    location=last_write_op.source_location,
                )
                self._block.ops.remove(last_write_op)
                self.modified = True
        self._last_write[typ] = (normalized_key, op)

    def _invalidate(self, typ: _StateType | typing.Literal["all"]) -> None:
        if typ == "all":
            self._read_results.clear()
            self._last_write.clear()
        else:
            self._read_results[typ].clear()
            self._last_write.pop(typ, None)

    @typing.override
    def visit_assignment(self, op: models.Assignment) -> None:
        match op.source:
            # SLOTS
            case models.ReadSlot(slot=slot):
                self._cached_read(op, _StateType.slot, key=(slot,))
            # GLOBAL STATE
            case models.Intrinsic(
                op=AVMOp.app_global_get_ex, args=[models.UInt64Constant(value=0), key]
            ):
                self._cached_read(op, _StateType.app_global, key=(key,))
            case models.Intrinsic(op=AVMOp.app_global_get, args=[key]):
                self._cached_read(
                    op, _StateType.app_global, key=(key,), allow_truncated_reads=True
                )
            # LOCAL STATE
            case models.Intrinsic(
                op=AVMOp.app_local_get_ex, args=[account, models.UInt64Constant(value=0), key]
            ):
                self._cached_read(op, _StateType.app_local, key=(account, key))
            case models.Intrinsic(op=AVMOp.app_local_get, args=[account, key]):
                self._cached_read(
                    op, _StateType.app_local, key=(account, key), allow_truncated_reads=True
                )
            # BOX
            case models.Intrinsic(op=AVMOp.box_get, args=[key]) | models.BoxRead(key=key):
                self._cached_read(op, _StateType.box, key=("rw", key))
            case models.Intrinsic(op=AVMOp.box_len, args=[key]):
                self._cached_read(op, _StateType.box, key=("len", key))
            case models.Intrinsic(op=AVMOp.box_extract, args=[key, offset, length]):
                self._cached_read(op, _StateType.box, key=("extract", key, offset, length))
            # OTHER
            case other_source:
                # visit in case invalidations need to occur
                other_source.accept(self)

    def visit_box_write(self, write: models.BoxWrite) -> None:
        self._handle_write(
            write, _StateType.box, key=("rw", write.key), values=(write.value, _const_true())
        )

    @typing.override
    def visit_write_slot(self, write: models.WriteSlot) -> None:
        self._handle_write(op=write, typ=_StateType.slot, key=(write.slot,), values=(write.value,))

    @typing.override
    def visit_intrinsic_op(self, op: models.Intrinsic) -> None:
        match op.op:
            # GLOBAL STATE
            case AVMOp.app_global_put:
                key, value = op.args
                self._handle_write(
                    op, _StateType.app_global, key=(key,), values=(value, _const_true())
                )
            case AVMOp.app_global_del:
                self._invalidate(_StateType.app_global)
            # LOCAL STATE
            case AVMOp.app_local_put:
                (account, key, value) = op.args
                self._handle_write(
                    op, _StateType.app_local, key=(account, key), values=(value, _const_true())
                )
            case AVMOp.app_local_del:
                self._invalidate(_StateType.app_local)
            # BOX
            case AVMOp.box_put:
                key, value = op.args
                self._handle_write(
                    op, _StateType.box, key=("rw", key), values=(value, _const_true())
                )
            case AVMOp.box_create:
                # box_create never modifies existing boxes or their contents
                pass
            case AVMOp.box_del | AVMOp.box_splice | AVMOp.box_resize | AVMOp.box_replace:
                self._invalidate(_StateType.box)

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        # be conservative and treat any subroutine call as a barrier
        if not callsub.target.pure:
            self._invalidate("all")


def _normalize_key(keys: tuple[models.Value | _ReadType, ...]) -> _StateKey:
    state_key = list[models.Value | bytes | _ReadType]()
    for key in keys:
        if (
            isinstance(key, models.Constant)
            and (bytes_const := get_bytes_constant(key)) is not None
        ):
            state_key.append(bytes_const)
        else:
            state_key.append(key)
    return tuple(state_key)


def _key_str(key: tuple[models.Value | _ReadType, ...]) -> str:
    try:
        (single_key,) = key
    except ValueError:
        return f'({",".join(map(str, key))})'
    else:
        return str(single_key)


def _const_true() -> models.Value:
    return models.UInt64Constant(
        value=1,
        ir_type=PrimitiveIRType.bool,
        source_location=None,
    )
