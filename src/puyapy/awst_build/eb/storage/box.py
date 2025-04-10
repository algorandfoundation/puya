import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    Expression,
    IntrinsicCall,
    Not,
    SizeOf,
    StateExists,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    NotIterableInstanceExpressionBuilder,
)
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StorageProxyConstructorArgs,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puyapy.awst_build.eb.storage._common import (
    BoxGetExpressionBuilder,
    BoxMaybeExpressionBuilder,
    BoxValueExpressionBuilder,
)
from puyapy.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    parse_storage_proxy_constructor_args,
)
from puyapy.awst_build.eb.storage._util import box_length_checked
from puyapy.awst_build.eb.storage.box_ref import BoxRefProxyExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


class BoxTypeBuilder(TypeBuilder[pytypes.StorageProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericBoxType
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=self.produces())


class BoxGenericTypeExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=None)


def _init(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    result_type: pytypes.StorageProxyType | None,
) -> InstanceBuilder:
    type_arg_name = "type_"
    key_arg_name = "key"
    arg_mapping, _ = get_arg_mapping(
        required_positional_names=[type_arg_name],
        optional_kw_only=[key_arg_name],
        args=args,
        arg_names=arg_names,
        call_location=location,
        raise_on_missing=True,
    )
    type_arg = arg_mapping[type_arg_name]
    match type_arg.pytype:
        case pytypes.TypeType(typ=content):
            pass
        case _:
            raise CodeError("first argument must be a type reference", location)

    if result_type is None:
        result_type = pytypes.GenericBoxType.parameterise([content], location)
    elif result_type.content != content:
        logger.error(
            "explicit type annotation does not match first argument"
            " - suggest to remove the explicit type annotation, it shouldn't be required",
            location=location,
        )

    typed_args = parse_storage_proxy_constructor_args(
        arg_mapping,
        key_wtype=wtypes.box_key,
        key_arg_name=key_arg_name,
        descr_arg_name=None,
        location=location,
    )

    if typed_args.key is None:
        return StorageProxyDefinitionBuilder(typed_args, result_type, location)
    return _BoxProxyExpressionBuilderFromConstructor(typed_args, result_type)


class BoxProxyExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.StorageProxyType],
    BytesBackedInstanceExpressionBuilder[pytypes.StorageProxyType],
    bytes_member="key",
):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericBoxType
        self._member_name = member_name
        super().__init__(typ, expr)

    def _box_key_expr(self, location: SourceLocation) -> BoxValueExpression:
        if self._member_name:
            exists_assertion_message = f"check self.{self._member_name} exists"
        else:
            exists_assertion_message = "check Box exists"
        return BoxValueExpression(
            key=self.resolve(),
            wtype=self.pytype.content_wtype,
            exists_assertion_message=exists_assertion_message,
            source_location=location,
        )

    def _get_value(self, location: SourceLocation) -> BoxValueExpressionBuilder:
        return BoxValueExpressionBuilder(self.pytype.content, self._box_key_expr(location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "create":
                return _Create(
                    box_proxy=self.resolve(),
                    content_type=self.pytype.content,
                )
            case "value":
                return self._get_value(location)
            case "get":
                return BoxGetExpressionBuilder(
                    self._box_key_expr(location), content_type=self.pytype.content
                )
            case "maybe":
                return BoxMaybeExpressionBuilder(
                    self._box_key_expr(location), content_type=self.pytype.content
                )
            case "length":
                return UInt64ExpressionBuilder(
                    box_length_checked(self._get_value(location).resolve(), location)
                )
            case "ref":
                return BoxRefProxyExpressionBuilder(self.resolve())
        return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        box_exists = StateExists(
            field=self._box_key_expr(location),
            source_location=location,
        )
        return BoolExpressionBuilder(
            Not(expr=box_exists, source_location=location) if negate else box_exists
        )


class _BoxProxyExpressionBuilderFromConstructor(
    BoxProxyExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(self, args: StorageProxyConstructorArgs, typ: pytypes.StorageProxyType):
        assert args.key is not None
        super().__init__(args.key, typ, member_name=None)
        self._args = args

    @typing.override
    @property
    def args(self) -> StorageProxyConstructorArgs:
        return self._args


class _Create(FunctionBuilder):
    def __init__(self, *, content_type: pytypes.PyType, box_proxy: Expression) -> None:
        super().__init__(box_proxy.source_location)
        self.content_type = content_type
        self.box_proxy = box_proxy

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg_of_type(args, [pytypes.UInt64Type], location)
        if arg is not None:
            size = arg.resolve()
        else:
            size = SizeOf(
                size_wtype=self.content_type.checked_wtype(location),
                source_location=location,
            )
        return BoolExpressionBuilder(
            IntrinsicCall(
                op_code="box_create",
                stack_args=[self.box_proxy, size],
                wtype=wtypes.bool_wtype,
                source_location=location,
            )
        )
