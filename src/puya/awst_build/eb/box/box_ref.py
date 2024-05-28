import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    BytesConstant,
    ContractReference,
    Expression,
    IntrinsicCall,
    Literal,
    Not,
    StateExists,
)
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._storage import StorageProxyDefinitionBuilder, extract_key_override
from puya.awst_build.eb.base import (
    FunctionBuilder,
    NodeBuilder,
    StorageProxyConstructorResult,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.box._common import BoxGetExpressionBuilder, BoxMaybeExpressionBuilder
from puya.awst_build.eb.box._util import box_length_checked
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import (
    expect_operand_type,
    get_arg_mapping,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class BoxRefClassExpressionBuilder(TypeClassExpressionBuilder[pytypes.StorageProxyType]):
    def __init__(self, location: SourceLocation) -> None:
        super().__init__(pytypes.BoxRefType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        arg_mapping = get_arg_mapping(
            positional_arg_names=(),
            args=zip(arg_names, args, strict=True),
            location=location,
        )
        key_arg = arg_mapping.pop("key", None)
        if arg_mapping:
            raise CodeError("Invalid/unhandled arguments", location)

        key_override = extract_key_override(key_arg, location, is_prefix=False)
        if key_override is None:
            return StorageProxyDefinitionBuilder(
                self.produces2(), location=location, description=None
            )
        return _BoxRefProxyExpressionBuilderFromConstructor(expr=key_override)


class BoxRefProxyExpressionBuilder(ValueExpressionBuilder[pytypes.StorageProxyType]):
    def __init__(self, expr: Expression, member_name: str | None = None):
        super().__init__(pytypes.BoxRefType, expr)
        self._member_name = member_name

    def _box_key_expr(self, location: SourceLocation) -> BoxValueExpression:
        return BoxValueExpression(
            key=self.expr,
            source_location=location,
            wtype=wtypes.bytes_wtype,
            member_name=self._member_name,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> NodeBuilder:
        box_exists = StateExists(
            field=self._box_key_expr(location),
            source_location=location,
        )
        return BoolExpressionBuilder(
            Not(expr=box_exists, source_location=location) if negate else box_exists
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "create":
                return _Create(location, box_proxy=self.expr)
            case "delete":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.expr,
                    op_code="box_del",
                    arg_types=(),
                    args=(),
                    return_type=pytypes.BoolType,
                )
            case "extract":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.expr,
                    op_code="box_extract",
                    arg_types=(pytypes.UInt64Type, pytypes.UInt64Type),
                    args=("start_index", "length"),
                    return_type=pytypes.BytesType,
                )
            case "resize":
                raise NotImplementedError("TODO: BoxRef.resize handler")
            case "replace":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.expr,
                    op_code="box_replace",
                    arg_types=(pytypes.UInt64Type, pytypes.BytesType),
                    args=("start_index", "value"),
                    return_type=pytypes.NoneType,
                )
            case "splice":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.expr,
                    op_code="box_splice",
                    arg_types=(pytypes.UInt64Type, pytypes.UInt64Type, pytypes.BytesType),
                    args=("start_index", "length", "value"),
                    return_type=pytypes.NoneType,
                )

            case "get":
                return BoxGetExpressionBuilder(
                    self._box_key_expr(location), content_type=pytypes.BytesType
                )
            case "put":
                return _Put(location, box_proxy=self.expr)
            case "maybe":
                return BoxMaybeExpressionBuilder(
                    self._box_key_expr(location), content_type=pytypes.BytesType
                )
            case "length":
                return UInt64ExpressionBuilder(
                    box_length_checked(self._box_key_expr(location), location)
                )
            case _:
                return super().member_access(name, location)


class _BoxRefProxyExpressionBuilderFromConstructor(
    BoxRefProxyExpressionBuilder, StorageProxyConstructorResult
):
    @typing.override
    @property
    def initial_value(self) -> Expression | None:
        return None

    @typing.override
    def build_definition(
        self,
        member_name: str,
        defined_in: ContractReference,
        typ: pytypes.PyType,
        location: SourceLocation,
    ) -> AppStorageDeclaration:
        key_override = self.expr
        if not isinstance(key_override, BytesConstant):
            raise CodeError(
                f"assigning {typ} to a member variable requires a constant value for key",
                location,
            )
        return AppStorageDeclaration(
            description=None,
            member_name=member_name,
            key_override=key_override,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )


class _IntrinsicMethod(FunctionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        *,
        box_proxy: Expression,
        op_code: str,
        arg_types: Sequence[pytypes.PyType],
        return_type: pytypes.PyType,
        args: Sequence[str],
    ) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy
        self.op_code = op_code
        self.arg_types = arg_types
        self.args = args
        self.return_type = return_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        args_map = get_arg_mapping(self.args, zip(arg_names, args, strict=True), location)
        try:
            stack_args = [
                expect_operand_type(args_map.pop(arg_name), arg_type).rvalue()
                for arg_name, arg_type in zip(self.args, self.arg_types, strict=True)
            ]
        except KeyError as er:
            raise CodeError(f"Missing required arg '{er.args[0]}'", location) from None
        if args_map:
            raise CodeError("Invalid/unexpected args", location)
        result_expr = IntrinsicCall(
            op_code=self.op_code,
            stack_args=[self.box_proxy, *stack_args],
            wtype=self.return_type.wtype,
            source_location=location,
        )
        return builder_for_instance(self.return_type, result_expr)


class _Create(FunctionBuilder):
    def __init__(self, location: SourceLocation, *, box_proxy: Expression) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(f"Expected a single argument, got {len(args)}", location) from None
        size = expect_operand_type(arg, pytypes.UInt64Type).rvalue()
        return BoolExpressionBuilder(
            IntrinsicCall(
                op_code="box_create",
                stack_args=[self.box_proxy, size],
                source_location=location,
                wtype=wtypes.bool_wtype,
            )
        )


class _Put(FunctionBuilder):
    def __init__(self, location: SourceLocation, *, box_proxy: Expression) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(f"Expected a single argument, got {len(args)}", location) from None
        data = expect_operand_type(arg, pytypes.BytesType).rvalue()

        return VoidExpressionBuilder(
            IntrinsicCall(
                op_code="box_put",
                stack_args=[self.box_proxy, data],
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )
