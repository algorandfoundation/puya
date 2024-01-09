from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.algo_constants import MAX_SCRATCH_SLOT_NUMBER
from puya.awst import wtypes
from puya.awst.nodes import IntegerConstant, Literal
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


def expect_valid_slot_number(slot_number: ExpressionBuilder | Literal) -> int:
    slot_as_uint64 = expect_operand_wtype(slot_number, wtypes.uint64_wtype)
    if not isinstance(slot_as_uint64, IntegerConstant):
        raise CodeError("Scratch slot number must be a compile time constant")
    if slot_as_uint64.value > MAX_SCRATCH_SLOT_NUMBER:
        raise CodeError(f"Scratch slot number must be between 0 and {MAX_SCRATCH_SLOT_NUMBER}")
    return slot_as_uint64.value


class ScratchSlotClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self._storage: wtypes.WType | None = None
        self._slot: int | None = None

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if self._storage is not None:
            raise InternalError("Multiple indexing of Local?", location)
        match index:
            case TypeClassExpressionBuilder() as typ_class_eb:
                self.source_location += location
                self._storage = typ_class_eb.produces()
                return self
        raise CodeError(
            "Invalid indexing, only a single type arg is supported "
            "(you can also omit the type argument entirely as it should be redundant)",
            location,
        )

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        call_expr_loc = location
        match args:
            case [slot, TypeClassExpressionBuilder() as typ_class_eb]:
                self._slot = expect_valid_slot_number(slot)
                storage_wtype = typ_class_eb.produces()
            case _:
                raise CodeError("Invalid arguments", call_expr_loc)

        if self._storage is not None and self._storage != storage_wtype:
            raise CodeError(
                "ScratchSlot explicit type annotation does not match type argument"
                " - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                call_expr_loc,
            )
        return self


class ScratchSlotRangeClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self._storage: wtypes.WType | None = None
        self._slot_start: int | None = None
        self._slot_stop: int | None = None

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if self._storage is not None:
            raise InternalError("Multiple indexing of Local?", location)
        match index:
            case TypeClassExpressionBuilder() as typ_class_eb:
                self.source_location += location
                self._storage = typ_class_eb.produces()
                return self
        raise CodeError(
            "Invalid indexing, only a single type arg is supported "
            "(you can also omit the type argument entirely as it should be redundant)",
            location,
        )

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        call_expr_loc = location
        match args:
            case [slot_start, slot_stop, TypeClassExpressionBuilder() as typ_class_eb]:
                self._slot_start = expect_valid_slot_number(slot_start)
                self._slot_stop = expect_valid_slot_number(slot_stop)
                storage_wtype = typ_class_eb.produces()
            case _:
                raise CodeError("Invalid arguments", call_expr_loc)

        if self._storage is not None and self._storage != storage_wtype:
            raise CodeError(
                "ScratchSlot explicit type annotation does not match type argument"
                " - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                call_expr_loc,
            )
        return self
