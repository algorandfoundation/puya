import typing
from collections.abc import Callable, Sequence

import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppAccountStateExpression,
    BytesConstant,
    BytesEncoding,
    ContractReference,
    Expression,
    IntegerConstant,
    StateDelete,
    StateExists,
    StateGet,
    StateGetEx,
    Statement,
)
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    InstanceBuilder,
    Iteration,
    NodeBuilder,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puya.awst_build.eb.storage._storage import (
    StorageProxyDefinitionBuilder,
    extract_description,
    extract_key_override,
)
from puya.awst_build.eb.storage._value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64TypeBuilder
from puya.awst_build.utils import get_arg_mapping, require_instance_builder
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class LocalStateTypeBuilder(TypeBuilder[pytypes.StorageProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericLocalStateType
        self._typ = typ
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, arg_names, location, result_type=self._typ)


class LocalStateGenericTypeBuilder(GenericTypeBuilder):
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
    descr_arg_name = "description"
    arg_mapping, _ = get_arg_mapping(
        required_positional_names=[type_arg_name],
        optional_kw_only=[key_arg_name, descr_arg_name],
        args=args,
        arg_names=arg_names,
        call_location=location,
        raise_on_missing=True,
    )

    match arg_mapping[type_arg_name].pytype:
        case pytypes.TypeType(typ=content):
            pass
        case _:
            raise CodeError("first argument must be a type reference", location)
    if result_type is None:
        result_type = pytypes.GenericLocalStateType.parameterise([content], location)
    elif result_type.content != content:
        logger.error(
            "explicit type annotation does not match first argument"
            " - suggest to remove the explicit type annotation,  it shouldn't be required",
            location=location,
        )

    key_arg = arg_mapping.get("key")
    key_override = extract_key_override(key_arg, location, typ=wtypes.state_key)

    descr_arg = arg_mapping.get("description")
    description = extract_description(descr_arg)

    if key_override is None:
        return StorageProxyDefinitionBuilder(
            result_type, location=location, description=description
        )
    return _LocalStateExpressionBuilderFromConstructor(
        key_override=key_override, typ=result_type, description=description
    )


class LocalStateExpressionBuilder(
    BytesBackedInstanceExpressionBuilder[pytypes.StorageProxyType], bytes_member="key"
):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericLocalStateType
        self._member_name = member_name
        super().__init__(typ, expr)

    def _build_field(
        self,
        index: InstanceBuilder,
        location: SourceLocation,
    ) -> AppAccountStateExpression:
        # TODO: maybe resolve literal should allow functions, so we can validate
        #       constant values inside e.g. conditional expressions, not just plain constants
        #       like we check below with matching on IntegerConstant
        index = index.resolve_literal(UInt64TypeBuilder(index.source_location))
        match index.pytype:
            case pytypes.AccountType:
                index_expr = index.resolve()
            case _:
                index_expr = expect.argument_of_type_else_dummy(
                    index, pytypes.UInt64Type
                ).resolve()
                # https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/#resource-availability
                # Note that the sender address is implicitly included in the array,
                # but doesn't count towards the limit of 4, so the <= 4 below is correct
                # and intended
                if isinstance(index_expr, IntegerConstant) and not (0 <= index_expr.value <= 4):
                    logger.error(
                        "account index should be between 0 and 4 inclusive",
                        location=index.source_location,
                    )
        if self._member_name:
            exists_assertion_message = f"check self.{self._member_name} exists for account"
        else:
            exists_assertion_message = "check LocalState exists for account"
        return AppAccountStateExpression(
            key=self.resolve(),
            account=index_expr,
            wtype=self.pytype.content.wtype,
            exists_assertion_message=exists_assertion_message,
            source_location=location,
        )

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        expr = self._build_field(index, location)
        return _Value(self.pytype.content, expr)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        exists_expr = StateExists(
            field=self._build_field(item, location), source_location=location
        )
        return BoolExpressionBuilder(exists_expr)

    @typing.override
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> NodeBuilder:
        match name:
            case "get":
                return _Get(self.pytype.content, self._build_field, location)
            case "maybe":
                return _Maybe(self.pytype.content, self._build_field, location)
        return super().member_access(name, expr, location)

    @typing.override
    def iterate(self) -> Iteration:
        raise CodeError("cannot iterate account states", self.source_location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot slice account states", self.source_location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        raise CodeError("cannot determine if a LocalState is empty or not", location)


class _LocalStateExpressionBuilderFromConstructor(
    LocalStateExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(
        self, key_override: Expression, typ: pytypes.StorageProxyType, description: str | None
    ):
        super().__init__(key_override, typ, member_name=None)
        self.description = description

    @typing.override
    @property
    def initial_value(self) -> None:
        return None

    @typing.override
    def build_definition(
        self,
        member_name: str,
        defined_in: ContractReference,
        typ: pytypes.PyType,
        location: SourceLocation,
    ) -> AppStorageDeclaration:
        key_override = self.resolve()
        if not isinstance(key_override, BytesConstant):
            logger.error(
                f"assigning {typ} to a member variable requires a constant value for key",
                location=location,
            )
            key_override = BytesConstant(
                value=b"",
                wtype=wtypes.box_key,
                encoding=BytesEncoding.unknown,
                source_location=key_override.source_location,
            )
        return AppStorageDeclaration(
            description=self.description,
            member_name=member_name,
            key_override=key_override,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )


FieldBuilder = Callable[[InstanceBuilder, SourceLocation], AppAccountStateExpression]


class _Get(FunctionBuilder):
    def __init__(
        self, content_typ: pytypes.PyType, field_builder: FieldBuilder, location: SourceLocation
    ):
        super().__init__(location)
        self._content_typ = content_typ
        self._build_field = field_builder

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        key_arg_name = "key"
        default_arg_name = "default"
        args_map, any_missing = get_arg_mapping(
            required_positional_names=[key_arg_name, default_arg_name],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(self._content_typ, location)
        item = require_instance_builder(args_map[key_arg_name])
        default_arg = expect.argument_of_type_else_dummy(
            args_map[default_arg_name], self._content_typ
        )
        key = self._build_field(item, location)
        default = default_arg.resolve()
        expr = StateGet(field=key, default=default, source_location=location)
        return builder_for_instance(self._content_typ, expr)


class _Maybe(FunctionBuilder):
    def __init__(
        self, content_typ: pytypes.PyType, field_builder: FieldBuilder, location: SourceLocation
    ):
        super().__init__(location)
        self._content_typ = content_typ
        self._build_field = field_builder

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        result_typ = pytypes.GenericTupleType.parameterise(
            [self._content_typ, pytypes.BoolType], location
        )
        arg = expect.exactly_one_arg(args, location, default=expect.default_fixed_value(None))
        if arg is None:
            return dummy_value(result_typ, location)

        field = self._build_field(arg, location)
        app_local_get_ex = StateGetEx(field=field, source_location=location)
        return TupleExpressionBuilder(app_local_get_ex, result_typ)


class _Value(ValueProxyExpressionBuilder[pytypes.PyType, AppAccountStateExpression]):
    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.resolve(), source_location=location)
