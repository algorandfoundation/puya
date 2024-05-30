import typing
from collections.abc import Callable, Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    AppAccountStateExpression,
    BytesConstant,
    ContractReference,
    Expression,
    IntegerConstant,
    Literal,
    StateDelete,
    StateExists,
    StateGet,
    StateGetEx,
    Statement,
)
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._storage import (
    StorageProxyDefinitionBuilder,
    extract_description,
    extract_key_override,
)
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.base import (
    FunctionBuilder,
    GenericTypeBuilder,
    InstanceBuilder,
    InstanceExpressionBuilder,
    Iteration,
    NodeBuilder,
    StorageProxyConstructorResult,
    TypeBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import convert_literal_to_builder, expect_operand_type, get_arg_mapping
from puya.errors import CodeError
from puya.parse import SourceLocation


class AppAccountStateClassExpressionBuilder(TypeBuilder[pytypes.StorageProxyType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation) -> None:
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericLocalStateType
        self._typ = typ
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        return _init(args, arg_typs, arg_names, location, result_type=self._typ)


class AppAccountStateGenericClassExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        return _init(args, arg_typs, arg_names, location, result_type=None)


def _init(
    args: Sequence[NodeBuilder | Literal],
    arg_typs: Sequence[pytypes.PyType],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    result_type: pytypes.StorageProxyType | None,
) -> NodeBuilder:
    type_arg_name = "type_"
    arg_mapping = get_arg_mapping(
        positional_arg_names=[type_arg_name],
        args=zip(arg_names, zip(args, arg_typs, strict=True), strict=True),
        location=location,
    )
    try:
        _, type_arg_typ = arg_mapping.pop(type_arg_name)
    except KeyError as ex:
        raise CodeError("Required positional argument missing", location) from ex

    key_arg, _ = arg_mapping.pop("key", (None, None))
    descr_arg, _ = arg_mapping.pop("description", (None, None))
    if arg_mapping:
        raise CodeError(f"Unrecognised keyword argument(s): {", ".join(arg_mapping)}", location)

    match type_arg_typ:
        case pytypes.TypeType(typ=content):
            pass
        case _:
            raise CodeError("First argument must be a type reference", location)
    if result_type is None:
        result_type = pytypes.GenericLocalStateType.parameterise([content], location)
    elif result_type.content != content:
        raise CodeError(
            "App account state explicit type annotation does not match first argument"
            " - suggest to remove the explicit type annotation,"
            " it shouldn't be required",
            location,
        )

    key_override = extract_key_override(key_arg, location, is_prefix=False)
    description = extract_description(descr_arg)
    if key_override is None:
        return StorageProxyDefinitionBuilder(
            result_type, location=location, description=description
        )
    return _AppAccountStateExpressionBuilderFromConstructor(
        key_override=key_override, typ=result_type, description=description
    )


class AppAccountStateExpressionBuilder(InstanceExpressionBuilder[pytypes.StorageProxyType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType, member_name: str | None = None):
        assert isinstance(typ, pytypes.StorageProxyType)
        assert typ.generic == pytypes.GenericLocalStateType
        self._member_name = member_name
        super().__init__(typ, expr)

    def _build_field(
        self,
        index: NodeBuilder | Literal,
        location: SourceLocation,
    ) -> AppAccountStateExpression:
        index_expr = convert_literal_to_builder(index, pytypes.UInt64Type).rvalue()
        match index_expr:
            case IntegerConstant(value=account_offset):
                # https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/#resource-availability
                # Note that the sender address is implicitly included in the array,
                # but doesn't count towards the limit of 4, so the <= 4 below is correct
                # and intended
                if not (0 <= account_offset <= 4):
                    raise CodeError(
                        "Account index should be between 0 and 4 inclusive", index.source_location
                    )
            case Expression(wtype=(wtypes.uint64_wtype | wtypes.account_wtype)):
                pass
            case _:
                raise CodeError(
                    "Invalid index argument - must be either an Address or a UInt64",
                    index.source_location,
                )
        return AppAccountStateExpression(
            key=self.expr,
            member_name=self._member_name,
            account=index_expr,
            wtype=self.pytype.content.wtype,
            source_location=location,
        )

    @typing.override
    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        expr = self._build_field(index, location)
        return AppAccountStateForAccountExpressionBuilder(self.pytype.content, expr)

    @typing.override
    def contains(self, item: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        exists_expr = StateExists(
            field=self._build_field(item, location), source_location=location
        )
        return BoolExpressionBuilder(exists_expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "get":
                return _Get(self.pytype.content, self._build_field, location)
            case "maybe":
                return _Maybe(self.pytype.content, self._build_field, location)
        return super().member_access(name, location)

    @typing.override
    def iterate(self) -> Iteration:
        raise CodeError("cannot iterate account states", self.source_location)

    @typing.override
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        raise CodeError("cannot slice account states", self.source_location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)


class _AppAccountStateExpressionBuilderFromConstructor(
    AppAccountStateExpressionBuilder, StorageProxyConstructorResult
):
    def __init__(
        self, key_override: Expression, typ: pytypes.StorageProxyType, description: str | None
    ):
        super().__init__(key_override, typ, member_name=None)
        self.description = description

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
            description=self.description,
            member_name=member_name,
            key_override=key_override,
            source_location=location,
            typ=typ,
            defined_in=defined_in,
        )


FieldBuilder = Callable[[NodeBuilder | Literal, SourceLocation], AppAccountStateExpression]


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
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        if len(args) != 2:
            raise CodeError(f"Expected 2 arguments, got {len(args)}", location)
        if arg_names[0] == "default":
            default_arg, item = args
        else:
            item, default_arg = args
        default_expr = expect_operand_type(default_arg, self._content_typ).rvalue()
        expr = StateGet(
            field=self._build_field(item, location),
            default=default_expr,
            source_location=location,
        )

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
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        match args:
            case [item]:
                field = self._build_field(item, location)
                app_local_get_ex = StateGetEx(field=field, source_location=location)
                result_typ = pytypes.GenericTupleType.parameterise(
                    [self._content_typ, pytypes.BoolType], location
                )
                return TupleExpressionBuilder(app_local_get_ex, result_typ)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class AppAccountStateForAccountExpressionBuilder(ValueProxyExpressionBuilder):
    expr: AppAccountStateExpression  # TODO: remove "lies"

    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.expr, source_location=location)
