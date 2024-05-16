from __future__ import annotations

import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    ConstantValue,
    Expression,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.awst_build.eb._utils import uint64_to_biguint
from puya.awst_build.eb.arc4._utils import convert_arc4_literal
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    ARC4EncodedExpressionBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.base import BuilderComparisonOp, ExpressionBuilder
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build import pytypes
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class NumericARC4ClassExpressionBuilder(ARC4ClassExpressionBuilder, abc.ABC):
    def __init__(self, wtype: wtypes.ARC4UIntN | wtypes.ARC4UFixedNxM, location: SourceLocation):
        super().__init__(wtype, location)
        self._wtype = wtype

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        wtype = self.produces()
        match args:
            case []:
                zero_literal = Literal(value=self.zero_literal(), source_location=location)
                expr = convert_arc4_literal(zero_literal, wtype, location)
            case [Literal() as lit]:
                expr = convert_arc4_literal(lit, wtype, location)
            case [ExpressionBuilder(value_type=wtypes.WType() as value_type) as eb]:
                value = eb.rvalue()
                if value_type not in (
                    wtypes.bool_wtype,
                    wtypes.uint64_wtype,
                    wtypes.biguint_wtype,
                ):
                    raise CodeError(
                        f"{wtype} constructor expects an int literal or a "
                        "uint64 expression or a biguint expression"
                    )
                expr = ARC4Encode(value=value, source_location=location, wtype=wtype)
            case _:
                raise CodeError(
                    "Invalid/unhandled arguments",
                    location,
                )
        return self._value_builder()(expr)

    @classmethod
    @abc.abstractmethod
    def zero_literal(cls) -> ConstantValue: ...

    @classmethod
    @abc.abstractmethod
    def _value_builder(cls) -> type[ARC4EncodedExpressionBuilder]: ...


class ByteClassExpressionBuilder(NumericARC4ClassExpressionBuilder):

    def __init__(self, location: SourceLocation):
        super().__init__(wtypes.arc4_byte_type, location)

    @classmethod
    def zero_literal(cls) -> ConstantValue:
        return 0

    @classmethod
    def _value_builder(cls) -> type[ARC4EncodedExpressionBuilder]:
        return UIntNExpressionBuilder


class UIntNClassExpressionBuilder(NumericARC4ClassExpressionBuilder, abc.ABC):
    def __init__(self, wtype: wtypes.WType, location: SourceLocation):
        assert isinstance(wtype, wtypes.ARC4UIntN)
        super().__init__(wtype, location)

    @classmethod
    def zero_literal(cls) -> ConstantValue:
        return 0

    @classmethod
    def _value_builder(cls) -> type[ARC4EncodedExpressionBuilder]:
        return UIntNExpressionBuilder


class UFixedNxMClassExpressionBuilder(NumericARC4ClassExpressionBuilder):
    def __init__(self, wtype: wtypes.WType, location: SourceLocation):
        assert isinstance(wtype, wtypes.ARC4UFixedNxM)
        super().__init__(wtype, location)

    @classmethod
    def zero_literal(cls) -> ConstantValue:
        return "0.0"

    @classmethod
    def _value_builder(cls) -> type[ARC4EncodedExpressionBuilder]:
        return UFixedNxMExpressionBuilder


class UIntNExpressionBuilder(ARC4EncodedExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4UIntN)
        self.wtype: wtypes.ARC4UIntN = expr.wtype
        super().__init__(expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(
            self.expr,
            false_bytes=b"\x00" * (self.wtype.n // 8),
            location=location,
            negate=negate,
        )

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        if isinstance(other, Literal):
            other_expr = convert_arc4_literal(other, self.wtype)
        else:
            other_expr = other.rvalue()
        match other_expr.wtype:
            case wtypes.biguint_wtype:
                pass
            case wtypes.ARC4UIntN():
                other_expr = ReinterpretCast(
                    expr=other_expr,
                    wtype=wtypes.biguint_wtype,
                    source_location=other_expr.source_location,
                )
            case wtypes.uint64_wtype:
                other_expr = uint64_to_biguint(other, location)
            case _:
                return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=ReinterpretCast(
                expr=self.expr,
                wtype=wtypes.biguint_wtype,
                source_location=self.source_location,
            ),
            operator=NumericComparison(op.value),
            rhs=other_expr,
        )
        return BoolExpressionBuilder(cmp_expr)


class UFixedNxMExpressionBuilder(ARC4EncodedExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4UFixedNxM)
        self.wtype: wtypes.ARC4UFixedNxM = expr.wtype
        super().__init__(expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(
            self.expr,
            false_bytes=b"\x00" * (self.wtype.n // 8),
            location=location,
            negate=negate,
        )
