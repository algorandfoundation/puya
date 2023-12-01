from wyvern.awst import wtypes
from wyvern.awst.nodes import Literal, UInt64Constant
from wyvern.awst_build.eb.base import (
    ExpressionBuilder,
    TypeClassExpressionBuilder,
)
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.errors import CodeError, InternalError
from wyvern.parse import SourceLocation


class TypingLiteralClassExpressionBuilder(TypeClassExpressionBuilder):
    wtype: wtypes.WType | None

    def produces(self) -> wtypes.WType:
        if self.wtype:
            return self.wtype
        raise InternalError("Cannot determine wtype of TypingLiteral until index is called ")

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        assert isinstance(
            index, Literal
        ), "Index item must be a literal value to be indexed with typing.Literal[...]"

        match index.value:
            case int(int_value):
                self.wtype = wtypes.uint64_wtype
                return var_expression(UInt64Constant(value=int_value, source_location=location))
            # case bool():
            #     wtype = wtypes.bool_wtype
            # case str():
            #     wtype = wtypes.bytes_wtype
            case _:
                raise CodeError("Unsupported value for a literal type")
