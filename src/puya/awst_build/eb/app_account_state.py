from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    AppAccountStateExpression,
    AppStateKind,
    BytesEncoding,
    ConditionalExpression,
    Expression,
    IntegerConstant,
    Literal,
    StateDelete,
    StateGetEx,
    Statement,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import constants
from puya.awst_build.contract_data import AppStateDeclaration
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    StateProxyDefinitionBuilder,
    StateProxyMemberBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import (
    create_temporary_assignment,
    expect_operand_wtype,
    get_arg_mapping,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


def _build_field(
    state_decl: AppStateDeclaration, index: ExpressionBuilder | Literal, location: SourceLocation
) -> AppAccountStateExpression:
    index_expr = _validated_index_expr(index)
    return AppAccountStateExpression(
        field_name=state_decl.member_name,
        account=index_expr,
        wtype=state_decl.storage_wtype,
        source_location=location,
    )


class AppAccountStateExpressionBuilder(StateProxyMemberBuilder):
    def __init__(self, state_decl: AppStateDeclaration, location: SourceLocation):
        assert state_decl.kind is AppStateKind.account_local
        super().__init__(location)
        self.state_decl = state_decl

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        expr = _build_field(self.state_decl, index, location)
        return AppAccountStateForAccountExpressionBuilder(expr)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        app_local_get_ex = StateGetEx(
            field=_build_field(self.state_decl, item, location),
            source_location=location,
        )
        exists_expr = TupleItemExpression(app_local_get_ex, index=1, source_location=location)
        return var_expression(exists_expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "get":
                return AppAccountStateGetMethodBuilder(self.state_decl, location)
            case "maybe":
                return AppAccountStateMaybeMethodBuilder(self.state_decl, location)
        return super().member_access(name, location)


class AppAccountStateGetMethodBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_decl: AppStateDeclaration, location: SourceLocation):
        super().__init__(location)
        self.state_decl = state_decl

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        if len(args) != 2:
            raise CodeError(f"Expected 2 arguments, got {len(args)}", location)
        if arg_names[0] == "default":
            default_arg, item = args
        else:
            item, default_arg = args
        default_expr = expect_operand_wtype(
            default_arg, target_wtype=self.state_decl.storage_wtype
        )
        app_local_get_ex = create_temporary_assignment(
            _build_app_local_get_ex(self.state_decl, item, location), location
        )
        conditional_expr = ConditionalExpression(
            location,
            wtype=self.state_decl.storage_wtype,
            condition=TupleItemExpression(
                app_local_get_ex.define, index=1, source_location=location
            ),
            true_expr=TupleItemExpression(
                app_local_get_ex.read, index=0, source_location=location
            ),
            false_expr=default_expr,
        )
        return var_expression(conditional_expr)


class AppAccountStateMaybeMethodBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_decl: AppStateDeclaration, location: SourceLocation):
        super().__init__(location)
        self.state_decl = state_decl

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [item]:
                app_local_get_ex = _build_app_local_get_ex(self.state_decl, item, location)
                return var_expression(app_local_get_ex)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


def _build_app_local_get_ex(
    state_decl: AppStateDeclaration, item: ExpressionBuilder | Literal, location: SourceLocation
) -> StateGetEx:
    field = _build_field(state_decl, item, location)
    return StateGetEx(field=field, source_location=location)


def _validated_index_expr(index: ExpressionBuilder | Literal) -> Expression:
    # TODO: FIXME
    tmp: Expression | Literal
    if isinstance(index, Literal):
        tmp = index
    else:
        tmp = index.rvalue()
    match tmp:
        case Literal(value=int(account_offset)):
            valid_account_offset(account_offset, index.source_location)
            index_expr: Expression = UInt64Constant(
                value=account_offset, source_location=index.source_location
            )
        case Literal():
            raise CodeError("Invalid literal, expected an int", index.source_location)
        case IntegerConstant(value=account_offset) as index_expr:
            valid_account_offset(account_offset, index.source_location)
        case Expression(wtype=(wtypes.uint64_wtype | wtypes.account_wtype)) as index_expr:
            pass
        case _:
            raise CodeError(
                "Invalid index argument - must be either an Address or a UInt64",
                index.source_location,
            )
    return index_expr


def valid_account_offset(value: int, loc: SourceLocation) -> None:
    # https://developer.algorand.org/docs/get-details/dapps/smart-contracts/apps/#resource-availability
    # Note that the sender address is implicitly included in the array,
    # but doesn't count towards the limit of 4, so the <= 4 below is correct
    # and intended
    if not (0 <= value <= 4):
        raise CodeError("Account index should be between 0 and 4 inclusive", loc)


class AppAccountStateForAccountExpressionBuilder(ValueProxyExpressionBuilder):
    def __init__(self, expr: AppAccountStateExpression):
        self.__field = expr
        self.wtype = expr.wtype
        super().__init__(expr)

    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.__field, source_location=location)


class AppAccountStateClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self._storage: wtypes.WType | None = None

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if self._storage is not None:
            raise InternalError("Multiple indexing of Local?", location)
        match index:
            case TypeClassExpressionBuilder() as typ_class_eb:
                self.source_location += location
                self._storage = typ_class_eb.produces()
                return self
        raise CodeError(
            "Invalid indexing, only a single type arg is supported "
            "(you can also omit the type argument entirely as it should be redundant)",
            location,
        )

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        type_arg_name = "type_"
        arg_mapping = get_arg_mapping(
            positional_arg_names=[type_arg_name],
            args=zip(arg_names, args, strict=True),
            location=location,
        )
        try:
            type_arg = arg_mapping.pop(type_arg_name)
        except KeyError as ex:
            raise CodeError("Required positional argument missing", location) from ex

        key_arg = arg_mapping.pop("key", None)
        descr_arg = arg_mapping.pop("description", None)
        if arg_mapping:
            raise CodeError(
                f"Unrecognised keyword argument(s): {", ".join(arg_mapping)}", location
            )

        match type_arg:
            case TypeClassExpressionBuilder() as typ_class_eb:
                storage_wtype = typ_class_eb.produces()
            case _:
                raise CodeError("First argument must be a type reference", location)
        if self._storage is not None and self._storage != storage_wtype:
            raise CodeError(
                "App account state explicit type annotation does not match first argument"
                " - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                location,
            )

        match key_arg:
            case None:
                key = None
                key_encoding = None
            case Literal(value=bytes(bytes_value)):
                key = bytes_value
                key_encoding = BytesEncoding.unknown
            case Literal(value=str(str_value)):
                key = str_value.encode("utf8")
                key_encoding = BytesEncoding.utf8
            case _:
                raise CodeError("key should be a string or bytes literal", key_arg.source_location)

        match descr_arg:
            case None:
                description = None
            case Literal(value=str(str_value)):
                description = str_value
            case _:
                raise CodeError(
                    "description should be a string literal", descr_arg.source_location
                )

        return AppAccountStateProxyDefinitionBuilder(
            location=location,
            storage=storage_wtype,
            key=key,
            key_encoding=key_encoding,
            description=description,
        )


class AppAccountStateProxyDefinitionBuilder(StateProxyDefinitionBuilder):
    kind = AppStateKind.account_local
    python_name = constants.CLS_LOCAL_STATE_ALIAS
