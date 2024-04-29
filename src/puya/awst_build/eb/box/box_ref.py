from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BoxKeyExpression,
    BoxLength,
    BoxProxyExpression,
    BytesConstant,
    Expression,
    IntrinsicCall,
    Literal,
    Not,
    StateExists,
    UInt64Constant,
)
from puya.awst_build import constants
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.box._common import BoxGetExpressionBuilder, BoxMaybeExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import (
    expect_operand_wtype,
    get_arg_mapping,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class BoxRefClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return self.wtype

    def __init__(self, location: SourceLocation) -> None:
        super().__init__(location)
        self.wtype = wtypes.box_ref_proxy_type

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        arg_map = get_arg_mapping(
            positional_arg_names=(),
            args=zip(arg_names, args, strict=True),
            location=location,
        )
        key = expect_operand_wtype(arg_map.pop("key"), wtypes.bytes_wtype)

        if arg_map:
            raise CodeError("Invalid/unhandled arguments", location)

        return BoxRefProxyExpressionBuilder(
            expr=BoxProxyExpression(key=key, wtype=self.wtype, source_location=location)
        )


class BoxRefProxyExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression) -> None:
        if expr.wtype != wtypes.box_ref_proxy_type:
            raise InternalError(
                "BoxRefProxyExpressionBuilder can only be created with expressions of "
                f"wtype {wtypes.box_ref_proxy_type}",
                expr.source_location,
            )
        self.wtype = expr.wtype

        super().__init__(expr)
        self.python_name = constants.CLS_BOX_REF_PROXY

    def _box_key_expr(self, location: SourceLocation) -> BoxKeyExpression:
        return BoxKeyExpression(
            proxy=self.expr,
            source_location=location,
        )

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        box_exists = StateExists(
            field=self._box_key_expr(location),
            source_location=location,
        )
        return var_expression(
            Not(expr=box_exists, source_location=location) if negate else box_exists
        )

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "create":
                return BoxRefCreateExpressionBuilder(location, box_proxy=self.expr)
            case "replace":
                return BoxRefIntrinsicMethodExpressionBuilder(
                    location,
                    box_proxy=self.expr,
                    op_code="box_replace",
                    arg_wtypes=(wtypes.uint64_wtype, wtypes.bytes_wtype),
                    args=("start_index", "value"),
                    return_wtype=wtypes.void_wtype,
                )
            case "splice":
                return BoxRefIntrinsicMethodExpressionBuilder(
                    location,
                    box_proxy=self.expr,
                    op_code="box_splice",
                    arg_wtypes=(wtypes.uint64_wtype, wtypes.uint64_wtype, wtypes.bytes_wtype),
                    args=("start_index", "length", "value"),
                    return_wtype=wtypes.void_wtype,
                )
            case "extract":
                return BoxRefIntrinsicMethodExpressionBuilder(
                    location,
                    box_proxy=self.expr,
                    op_code="box_extract",
                    arg_wtypes=(wtypes.uint64_wtype, wtypes.uint64_wtype),
                    args=("start_index", "length"),
                    return_wtype=wtypes.bytes_wtype,
                )
            case "delete":
                return BoxRefIntrinsicMethodExpressionBuilder(
                    location,
                    box_proxy=self.expr,
                    op_code="box_del",
                    arg_wtypes=(),
                    args=(),
                    return_wtype=wtypes.bool_wtype,
                )
            case "maybe":
                return BoxMaybeExpressionBuilder(self._box_key_expr(location))
            case "get":
                return BoxGetExpressionBuilder(self._box_key_expr(location))
            case "length":
                return var_expression(
                    BoxLength(box_key=self._box_key_expr(location), source_location=location)
                )

            case _:
                return super().member_access(name, location)


class BoxRefIntrinsicMethodExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        *,
        box_proxy: Expression,
        op_code: str,
        arg_wtypes: Sequence[wtypes.WType],
        return_wtype: wtypes.WType,
        args: Sequence[str],
    ) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy
        self.op_code = op_code
        self.arg_wtypes = arg_wtypes
        self.args = args
        self.return_wtype = return_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        args_map = get_arg_mapping(self.args, zip(arg_names, args, strict=True), location)
        try:
            stack_args = [
                expect_operand_wtype(args_map.pop(arg_name), arg_wtype)
                for arg_name, arg_wtype in zip(self.args, self.arg_wtypes, strict=True)
            ]
        except KeyError as er:
            raise CodeError(f"Missing required arg '{er.args[0]}'", location) from None
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        return var_expression(
            IntrinsicCall(
                op_code=self.op_code,
                stack_args=[self.box_proxy, *stack_args],
                wtype=self.return_wtype,
                source_location=location,
            )
        )


class BoxRefCreateExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation, *, box_proxy: Expression) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case (Literal(value=int(int_lit), source_location=lit_location),):
                op_code = "box_create"
                call_args: list[Expression] = [
                    UInt64Constant(value=int_lit, source_location=lit_location)
                ]
                return_wtype = wtypes.bool_wtype
            case (Literal(value=bytes(bytes_lit), source_location=lit_location),):
                op_code = "box_put"
                call_args = [BytesConstant(value=bytes_lit, source_location=lit_location)]
                return_wtype = wtypes.void_wtype
            case (ExpressionBuilder() as eb,):
                match eb.rvalue().wtype:
                    case wtypes.uint64_wtype:
                        op_code = "box_create"
                        call_args = [eb.rvalue()]
                        return_wtype = wtypes.bool_wtype
                    case wtypes.bytes_wtype:
                        op_code = "box_put"
                        call_args = [eb.rvalue()]
                        return_wtype = wtypes.void_wtype
                    case _:
                        raise CodeError("Invalid/unexpected args", location)
            case _:
                raise CodeError("Invalid/unexpected args", location)

        return var_expression(
            IntrinsicCall(
                op_code=op_code,
                stack_args=[
                    self.box_proxy,
                    *call_args,
                ],
                source_location=location,
                wtype=return_wtype,
            )
        )
