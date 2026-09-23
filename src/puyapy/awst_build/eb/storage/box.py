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
    TupleExpression,
    TupleItemExpression,
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
from puyapy.awst_build.eb._utils import reinterpret_cast
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StorageProxyConstructorArgs,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puyapy.awst_build.eb.reference_types.application import ApplicationExpressionBuilder
from puyapy.awst_build.eb.storage._common import (
    BoxGetExpressionBuilder,
    BoxMaybeExpressionBuilder,
    BoxValueExpressionBuilder,
)
from puyapy.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    extract_key_override,
    parse_storage_proxy_constructor_args,
)
from puyapy.awst_build.eb.storage._util import box_length_checked
from puyapy.awst_build.eb.storage.box_ref import BoxRefProxyExpressionBuilder, _IntrinsicMethod
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder, UInt64TypeBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)


def box_proxy_builder(expr: Expression, typ: pytypes.PyType) -> InstanceBuilder:
    """Select the local or remote proxy builder based on the box's location type parameter."""
    if pytypes.is_remote_box(typ):
        return RemoteBoxProxyExpressionBuilder(expr, typ)
    return BoxProxyExpressionBuilder(expr, typ)


_REMOTE_MEMBER = "remote"


class BoxTypeBuilder(TypeBuilder[pytypes.StorageProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericBoxType
        super().__init__(typ, location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == _REMOTE_MEMBER:
            return _RemoteInit(location, result_type=self.produces())
        return super().member_access(name, location)

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
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == _REMOTE_MEMBER:
            return _RemoteInit(location, result_type=None)
        return super().member_access(name, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=None)


def _resolve_result_type(
    result_type: pytypes.StorageProxyType | None,
    content: pytypes.PyType,
    location: SourceLocation,
    *,
    remote: bool,
) -> pytypes.StorageProxyType:
    box_location = pytypes.BoxRemoteType if remote else pytypes.BoxLocalType
    inferred = pytypes.GenericBoxType.parameterise([content, box_location], location)
    if result_type is None:
        return inferred
    if result_type.content != content:
        logger.error(
            "explicit type annotation does not match first argument"
            " - suggest to remove the explicit type annotation, it shouldn't be required",
            location=location,
        )
    if pytypes.is_remote_box(result_type) != remote:
        annotated = (
            pytypes.BoxRemoteType if pytypes.is_remote_box(result_type) else (pytypes.BoxLocalType)
        )
        logger.error(
            f"box annotated as {annotated} but constructed as {box_location}"
            f" - Box() constructs a {pytypes.BoxLocalType} box,"
            f" and Box.{_REMOTE_MEMBER}() constructs a {pytypes.BoxRemoteType} box",
            location=location,
        )
    # deliberately returns the inferred type rather than the annotation, so that the members
    # resolve consistently with the way the box was actually constructed
    return inferred


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

    result_type = _resolve_result_type(result_type, content, location, remote=False)
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


class _RemoteInit(FunctionBuilder):
    """`Box.remote(...)`, for a box belonging to another application.

    A separate constructor rather than an `app` argument on `Box(...)`, so that the location
    can be part of the resulting type without overloading `Box.__init__` - overloads would
    degrade the type errors mypy reports for every other misuse of `Box(...)`.
    """

    def __init__(
        self, location: SourceLocation, *, result_type: pytypes.StorageProxyType | None
    ) -> None:
        super().__init__(location)
        self.result_type = result_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        type_arg_name = "type_"
        key_arg_name = "key"
        app_arg_name = "app"
        arg_mapping, _ = get_arg_mapping(
            required_positional_names=[type_arg_name],
            required_kw_only=[app_arg_name, key_arg_name],
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

        result_type = _resolve_result_type(self.result_type, content, location, remote=True)
        # a box of another application is not this contract's state, so there is no member name
        # to infer a key from, and the app has to be evaluated where the box is used - hence the
        # key is required and there is no StorageProxyDefinitionBuilder path
        app = expect.argument_of_type_else_dummy(
            arg_mapping[app_arg_name], pytypes.ApplicationType
        ).resolve()
        key = extract_key_override(arg_mapping.get(key_arg_name), location, typ=wtypes.box_key)
        if key is None:
            raise CodeError(
                "a key is required for a box belonging to another application", location
            )
        proxy = TupleExpression(
            items=[app, key],
            wtype=wtypes.remote_box_wtype,
            source_location=location,
        )
        return RemoteBoxProxyExpressionBuilder(proxy, result_type)


def _box_expr(
    key: Expression,
    app: Expression | None,
    pytype: pytypes.StorageProxyType,
    member_name: str | None,
    location: SourceLocation,
) -> BoxValueExpression:
    if member_name:
        exists_assertion_message = f"check self.{member_name} exists"
    elif pytypes.is_remote_box(pytype):
        exists_assertion_message = "check remote Box exists"
    else:
        exists_assertion_message = "check Box exists"
    return BoxValueExpression(
        key=key,
        app=app,
        wtype=pytype.content_wtype,
        exists_assertion_message=exists_assertion_message,
        source_location=location,
    )


class RemoteBoxProxyExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.StorageProxyType]
):
    """A box belonging to another application, accessed via the `app_box_*` ops.

    The underlying expression is a `(app, key)` tuple, so that the proxy can be round-tripped
    through a variable without losing the application it refers to.
    """

    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericBoxType
        assert pytypes.is_remote_box(typ)
        super().__init__(typ, expr)

    def _app_and_key(self, location: SourceLocation) -> tuple[Expression, Expression]:
        # single_eval so that a proxy built inline (rather than read from a variable)
        # doesn't evaluate its app and key expressions twice
        proxy = self.single_eval().resolve()
        app = TupleItemExpression(base=proxy, index=0, source_location=location)
        key = TupleItemExpression(base=proxy, index=1, source_location=location)
        return app, key

    def _box_key_expr(self, location: SourceLocation) -> BoxValueExpression:
        app, key = self._app_and_key(location)
        return _box_expr(key, app, self.pytype, None, location)

    def _get_value(self, location: SourceLocation) -> BoxValueExpressionBuilder:
        return BoxValueExpressionBuilder(self.pytype.content, self._box_key_expr(location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "app":
                app, _ = self._app_and_key(location)
                return ApplicationExpressionBuilder(app)
            case "key":
                _, key = self._app_and_key(location)
                return BytesExpressionBuilder(
                    reinterpret_cast(expr=key, wtype=wtypes.bytes_wtype, source_location=location)
                )
            case "create":
                return _Create(
                    stack_args_prefix=self._app_and_key(location),
                    op_code="app_box_create",
                    content_type=self.pytype.content,
                    location=location,
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
                raise CodeError(
                    "BoxRef does not support boxes of another application"
                    " - the equivalent methods are available directly on this box",
                    location,
                )
            case "extract":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=self._app_and_key(location),
                    op_code="app_box_extract",
                    args={"start_index": pytypes.UInt64Type, "length": pytypes.UInt64Type},
                    return_type=pytypes.BytesType,
                )
            case "resize":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=self._app_and_key(location),
                    op_code="app_box_resize",
                    args={"new_size": pytypes.UInt64Type},
                    return_type=pytypes.NoneType,
                )
            case "replace":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=self._app_and_key(location),
                    op_code="app_box_replace",
                    args={"start_index": pytypes.UInt64Type, "value": pytypes.BytesType},
                    return_type=pytypes.NoneType,
                )
            case "splice":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=self._app_and_key(location),
                    op_code="app_box_splice",
                    args={
                        "start_index": pytypes.UInt64Type,
                        "length": pytypes.UInt64Type,
                        "value": pytypes.BytesType,
                    },
                    return_type=pytypes.NoneType,
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

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(f"cannot serialize {self.pytype}", location)


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
        return _box_expr(self.resolve(), None, self.pytype, self._member_name, location)

    def _get_value(self, location: SourceLocation) -> BoxValueExpressionBuilder:
        return BoxValueExpressionBuilder(self.pytype.content, self._box_key_expr(location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "app":
                return ApplicationExpressionBuilder(
                    IntrinsicCall(
                        op_code="global",
                        immediates=["CurrentApplicationID"],
                        wtype=wtypes.application_wtype,
                        source_location=location,
                    )
                )
            case "create":
                return _Create(
                    stack_args_prefix=(self.resolve(),),
                    op_code="box_create",
                    content_type=self.pytype.content,
                    location=location,
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
            case "extract":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=(self.resolve(),),
                    op_code="box_extract",
                    args={"start_index": pytypes.UInt64Type, "length": pytypes.UInt64Type},
                    return_type=pytypes.BytesType,
                )
            case "resize":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=(self.resolve(),),
                    op_code="box_resize",
                    args={"new_size": pytypes.UInt64Type},
                    return_type=pytypes.NoneType,
                )
            case "replace":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=(self.resolve(),),
                    op_code="box_replace",
                    args={"start_index": pytypes.UInt64Type, "value": pytypes.BytesType},
                    return_type=pytypes.NoneType,
                )
            case "splice":
                return _IntrinsicMethod(
                    location,
                    stack_args_prefix=(self.resolve(),),
                    op_code="box_splice",
                    args={
                        "start_index": pytypes.UInt64Type,
                        "length": pytypes.UInt64Type,
                        "value": pytypes.BytesType,
                    },
                    return_type=pytypes.NoneType,
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
    def __init__(
        self,
        *,
        content_type: pytypes.PyType,
        stack_args_prefix: Sequence[Expression],
        op_code: str,
        location: SourceLocation,
    ) -> None:
        super().__init__(location)
        self.content_type = content_type
        self.stack_args_prefix = tuple(stack_args_prefix)
        self.op_code = op_code

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg_of_type(
            args, [pytypes.IntLiteralType, pytypes.UInt64Type], location
        )
        match arg:
            case InstanceBuilder(pytype=pytypes.IntLiteralType):
                size = arg.resolve_literal(converter=UInt64TypeBuilder(location)).resolve()
            case InstanceBuilder(pytype=pytypes.UInt64Type):
                size = arg.resolve()
            case None:
                size = SizeOf(
                    size_wtype=self.content_type.checked_wtype(location),
                    source_location=location,
                )
            case _:
                size = expect.not_this_type(
                    arg, default=expect.default_dummy_value(pytypes.UInt64Type)
                ).resolve()
        return BoolExpressionBuilder(
            IntrinsicCall(
                op_code=self.op_code,
                stack_args=[*self.stack_args_prefix, size],
                wtype=wtypes.bool_wtype,
                source_location=location,
            )
        )
