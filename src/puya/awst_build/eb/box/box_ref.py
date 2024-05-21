import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BoxLength,
    BoxValueExpression,
    Expression,
    IntrinsicCall,
    Literal,
    Not,
    StateExists,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.box._common import BoxGetExpressionBuilder, BoxMaybeExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import (
    expect_operand_wtype,
    get_arg_mapping,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class BoxRefClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation) -> None:
        super().__init__(wtypes.bytes_wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
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
            expr=BoxValueExpression(key=key, wtype=self.produces(), source_location=location)
        )


class BoxRefProxyExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.bytes_wtype

    def _box_key_expr(self, location: SourceLocation) -> BoxValueExpression:
        return BoxValueExpression(
            key=self.expr,
            source_location=location,
            wtype=wtypes.bytes_wtype,
            field_name=None,
        )

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        box_exists = StateExists(
            field=self._box_key_expr(location),
            source_location=location,
        )
        return BoolExpressionBuilder(
            Not(expr=box_exists, source_location=location) if negate else box_exists
        )

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "create":
                return BoxRefCreateExpressionBuilder(location, box_proxy=self.expr)
            case "delete":
                return BoxRefIntrinsicMethodExpressionBuilder(
                    location,
                    box_proxy=self.expr,
                    op_code="box_del",
                    arg_wtypes=(),
                    args=(),
                    return_wtype=wtypes.bool_wtype,
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
            case "resize":
                raise NotImplementedError("TODO: BoxRef.resize handler")
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

            case "get":
                return BoxGetExpressionBuilder(self._box_key_expr(location))
            case "put":
                return BoxRefPutExpressionBuilder(location, box_proxy=self.expr)
            case "maybe":
                return BoxMaybeExpressionBuilder(self._box_key_expr(location))
            case "length":
                return UInt64ExpressionBuilder(
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
        arg_typs: Sequence[pytypes.PyType],
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
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(f"Expected a single argument, got {len(args)}", location) from None
        size = expect_operand_wtype(arg, wtypes.uint64_wtype)
        return BoolExpressionBuilder(
            IntrinsicCall(
                op_code="box_create",
                stack_args=[self.box_proxy, size],
                source_location=location,
                wtype=wtypes.bool_wtype,
            )
        )


class BoxRefPutExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation, *, box_proxy: Expression) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(f"Expected a single argument, got {len(args)}", location) from None
        data = expect_operand_wtype(arg, wtypes.bytes_wtype)

        return VoidExpressionBuilder(
            IntrinsicCall(
                op_code="box_put",
                stack_args=[self.box_proxy, data],
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )
