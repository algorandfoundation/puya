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
    get_integer_literal_value,
)
from puya.awst_build.eb.base import BuilderComparisonOp, ExpressionBuilder
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class NumericARC4ClassExpressionBuilder(ARC4ClassExpressionBuilder, abc.ABC):

    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self.wtype: wtypes.ARC4UIntN | wtypes.ARC4UFixedNxM | None = None

    def produces(self) -> wtypes.ARC4Type:
        if self.wtype is None:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
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
        super().__init__(location)
        self.wtype = wtypes.arc4_byte_type

    @classmethod
    def zero_literal(cls) -> ConstantValue:
        return 0

    @classmethod
    def _value_builder(cls) -> type[ARC4EncodedExpressionBuilder]:
        return UIntNExpressionBuilder


class _UIntNClassExpressionBuilder(NumericARC4ClassExpressionBuilder, abc.ABC):
    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        n = get_integer_literal_value(index, "UIntN scale")
        self.check_bitsize(n, location)
        self.wtype = wtypes.ARC4UIntN(n, location)
        return self

    @abc.abstractmethod
    def check_bitsize(self, n: int, location: SourceLocation) -> None: ...

    @classmethod
    def zero_literal(cls) -> ConstantValue:
        return 0

    @classmethod
    def _value_builder(cls) -> type[ARC4EncodedExpressionBuilder]:
        return UIntNExpressionBuilder


class UIntNClassExpressionBuilder(_UIntNClassExpressionBuilder):
    def check_bitsize(self, n: int, location: SourceLocation) -> None:
        if n % 8 or not (8 <= n <= 64):
            raise CodeError(
                "UIntN scale must be >=8 and <=64 bits, and be a multiple of 8",
                location,
            )


class BigUIntNClassExpressionBuilder(_UIntNClassExpressionBuilder):
    def check_bitsize(self, n: int, location: SourceLocation) -> None:
        if n % 8 or not (64 < n <= 512):
            raise CodeError(
                "BigUIntN scale must be >64 and <=512 bits, and be a multiple of 8",
                location,
            )


class _UFixedNxMClassExpressionBuilder(NumericARC4ClassExpressionBuilder):
    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> ExpressionBuilder:
        try:
            scale_expr, precision_expr = indexes
        except ValueError as ex:
            raise CodeError(f"Expected two type arguments, got {len(indexes)}", location) from ex
        bits = get_integer_literal_value(scale_expr, "UFixedNxM scale")
        precision = get_integer_literal_value(precision_expr, "UFixedNxM precision")

        self.check_bitsize(bits, location)
        if not (1 <= precision < 160):
            raise CodeError("UFixedNxM precision must be between 1 and 160.")
        self.wtype = wtypes.ARC4UFixedNxM(bits=bits, precision=precision, source_location=location)
        return self

    @abc.abstractmethod
    def check_bitsize(self, n: int, location: SourceLocation) -> None: ...

    @classmethod
    def zero_literal(cls) -> ConstantValue:
        return "0.0"

    @classmethod
    def _value_builder(cls) -> type[ARC4EncodedExpressionBuilder]:
        return UFixedNxMExpressionBuilder


class UFixedNxMClassExpressionBuilder(_UFixedNxMClassExpressionBuilder):
    def check_bitsize(self, n: int, location: SourceLocation) -> None:
        if n % 8 or not (8 <= n <= 64):
            raise CodeError(
                "UFixedNxM scale must be >=8 and <=64 bits, and be a multiple of 8",
                location,
            )


class BigUFixedNxMClassExpressionBuilder(_UFixedNxMClassExpressionBuilder):
    def check_bitsize(self, n: int, location: SourceLocation) -> None:
        if n % 8 or not (64 < n <= 512):
            raise CodeError(
                "BigUFixedNxM scale must be >64 and <=512 bits, and be a multiple of 8",
                location,
            )


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
