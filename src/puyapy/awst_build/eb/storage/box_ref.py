import typing
from collections.abc import Sequence

from puya.awst import wtypes
from puya.awst.nodes import BoxValueExpression, Expression, IntrinsicCall, Not, StateExists
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StorageProxyConstructorArgs,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.storage._common import BoxGetExpressionBuilder, BoxMaybeExpressionBuilder
from puyapy.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    parse_storage_proxy_constructor_args,
)
from puyapy.awst_build.eb.storage._util import box_length_checked
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puyapy.awst_build.utils import get_arg_mapping


class BoxRefTypeBuilder(TypeBuilder[pytypes.StorageProxyType]):
    def __init__(self, location: SourceLocation) -> None:
        super().__init__(pytypes.BoxRefType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        key_arg_name = "key"
        arg_mapping, _ = get_arg_mapping(
            optional_kw_only=[key_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        typed_args = parse_storage_proxy_constructor_args(
            arg_mapping,
            key_wtype=wtypes.box_key,
            key_arg_name=key_arg_name,
            descr_arg_name=None,
            location=location,
        )

        if typed_args.key is None:
            return StorageProxyDefinitionBuilder(typed_args, self.produces(), location)
        return _BoxRefProxyExpressionBuilderFromConstructor(typed_args)


class BoxRefProxyExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.StorageProxyType],
    BytesBackedInstanceExpressionBuilder[pytypes.StorageProxyType],
    bytes_member="key",
):
    def __init__(self, expr: Expression, member_name: str | None = None):
        super().__init__(pytypes.BoxRefType, expr)
        self._member_name = member_name

    def _box_key_expr(self, location: SourceLocation) -> BoxValueExpression:
        if self._member_name:
            exists_assertion_message = f"check self.{self._member_name} exists"
        else:
            exists_assertion_message = "check BoxRef exists"
        return BoxValueExpression(
            key=self.resolve(),
            wtype=wtypes.bytes_wtype,
            exists_assertion_message=exists_assertion_message,
            source_location=location,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        box_exists = StateExists(
            field=self._box_key_expr(location),
            source_location=location,
        )
        return BoolExpressionBuilder(
            Not(expr=box_exists, source_location=location) if negate else box_exists
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "create":
                return _Create(location, box_proxy=self.resolve())
            case "delete":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.resolve(),
                    op_code="box_del",
                    args={},
                    return_type=pytypes.BoolType,
                )
            case "extract":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.resolve(),
                    op_code="box_extract",
                    args={"start_index": pytypes.UInt64Type, "length": pytypes.UInt64Type},
                    return_type=pytypes.BytesType,
                )
            case "resize":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.resolve(),
                    op_code="box_resize",
                    args={"new_size": pytypes.UInt64Type},
                    return_type=pytypes.NoneType,
                )
            case "replace":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.resolve(),
                    op_code="box_replace",
                    args={"start_index": pytypes.UInt64Type, "value": pytypes.BytesType},
                    return_type=pytypes.NoneType,
                )
            case "splice":
                return _IntrinsicMethod(
                    location,
                    box_proxy=self.resolve(),
                    op_code="box_splice",
                    args={
                        "start_index": pytypes.UInt64Type,
                        "length": pytypes.UInt64Type,
                        "value": pytypes.BytesType,
                    },
                    return_type=pytypes.NoneType,
                )

            case "get":
                return BoxGetExpressionBuilder(
                    self._box_key_expr(location), content_type=pytypes.BytesType
                )
            case "put":
                return _Put(location, box_proxy=self.resolve())
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
    def __init__(self, args: StorageProxyConstructorArgs):
        assert args.key is not None
        super().__init__(args.key, member_name=None)
        self._args = args

    @typing.override
    @property
    def args(self) -> StorageProxyConstructorArgs:
        return self._args


class _IntrinsicMethod(FunctionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        *,
        box_proxy: Expression,
        op_code: str,
        args: dict[str, pytypes.PyType],
        return_type: pytypes.RuntimeType,
    ) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy
        self.op_code = op_code
        self.args = args
        self.return_type = return_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        args_map, any_missing = get_arg_mapping(
            required_positional_names=list(self.args.keys()),
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(self.return_type, location)
        stack_args = [
            expect.argument_of_type_else_dummy(
                args_map[arg_name], arg_type, resolve_literal=True
            ).resolve()
            for arg_name, arg_type in self.args.items()
        ]
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
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(
            args, pytypes.UInt64Type, location, resolve_literal=True
        )
        size = arg.resolve()
        return BoolExpressionBuilder(
            IntrinsicCall(
                op_code="box_create",
                stack_args=[self.box_proxy, size],
                wtype=wtypes.bool_wtype,
                source_location=location,
            )
        )


class _Put(FunctionBuilder):
    def __init__(self, location: SourceLocation, *, box_proxy: Expression) -> None:
        super().__init__(location)
        self.box_proxy = box_proxy

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(
            args, pytypes.BytesType, location, resolve_literal=True
        )
        data = arg.resolve()
        return NoneExpressionBuilder(
            IntrinsicCall(
                op_code="box_put",
                stack_args=[self.box_proxy, data],
                wtype=wtypes.void_wtype,
                source_location=location,
            )
        )
