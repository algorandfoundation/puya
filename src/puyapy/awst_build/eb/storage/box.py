import typing
from collections.abc import Sequence

import mypy.nodes
from puya import log
from puya.awst import wtypes
from puya.awst.nodes import BoxValueExpression, Expression, Not, StateExists
from puya.errors import CodeError
from puya.parse import SourceLocation

from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._base import GenericTypeBuilder, NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puyapy.awst_build.eb.storage._common import (
    BoxGetExpressionBuilder,
    BoxMaybeExpressionBuilder,
    BoxValueExpressionBuilder,
)
from puyapy.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    extract_key_override,
)
from puyapy.awst_build.eb.storage._util import BoxProxyConstructorResult, box_length_checked
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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=self.produces())


class BoxGenericTypeExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
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

    key_arg = arg_mapping.get(key_arg_name)

    if result_type is None:
        result_type = pytypes.GenericBoxType.parameterise([content], location)
    elif result_type.content != content:
        logger.error(
            "explicit type annotation does not match first argument"
            " - suggest to remove the explicit type annotation, it shouldn't be required",
            location=location,
        )

    key_override = extract_key_override(key_arg, location, typ=wtypes.box_key)
    if key_override is None:
        return StorageProxyDefinitionBuilder(result_type, location=location, description=None)
    return _BoxProxyExpressionBuilderFromConstructor(key_override=key_override, typ=result_type)


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
            wtype=self.pytype.content.wtype,
            exists_assertion_message=exists_assertion_message,
            source_location=location,
        )

    def _get_value(self, location: SourceLocation) -> BoxValueExpressionBuilder:
        return BoxValueExpressionBuilder(self.pytype.content, self._box_key_expr(location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
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
    BoxProxyExpressionBuilder, BoxProxyConstructorResult
):
    def __init__(self, key_override: Expression, typ: pytypes.StorageProxyType):
        super().__init__(key_override, typ, member_name=None)
