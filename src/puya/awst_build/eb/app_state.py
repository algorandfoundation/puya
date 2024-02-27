from typing import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes  # noqa: TCH001
from puya.awst.nodes import (
    AppStateExpression,
    AppStateKind,
    ConditionalExpression,
    Expression,
    Literal,
    Not,
    StateDelete,
    StateGetEx,
    Statement,
    TupleItemExpression,
)
from puya.awst_build import constants
from puya.awst_build.contract_data import AppStateDeclaration
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import create_temporary_assignment, expect_operand_wtype
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


def _build_field(state_decl: AppStateDeclaration, location: SourceLocation) -> AppStateExpression:
    return AppStateExpression(
        field_name=state_decl.member_name, wtype=state_decl.storage_wtype, source_location=location
    )


class AppStateClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self._storage: wtypes.WType | None = None
        self._initial_value: Expression | None = None

    @property
    def initial_value(self) -> Expression | None:
        return self._initial_value

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if self._storage is not None:
            raise InternalError("Multiple indexing of GlobalState?", location)
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
        call_expr_loc = location
        match args:
            case [TypeClassExpressionBuilder() as typ_class_eb]:
                storage_wtype = typ_class_eb.produces()
                self._initial_value = None
            case [ExpressionBuilder() as value_eb]:
                self._initial_value = value_eb.rvalue()
                storage_wtype = self._initial_value.wtype
            case _:
                raise CodeError("expected a single argument with storage type", call_expr_loc)

        if self._storage is not None and self._storage != storage_wtype:
            raise CodeError(
                f"{constants.CLS_GLOBAL_STATE_ALIAS} explicit type annotation"
                f" does not match first argument - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                call_expr_loc,
            )
        self._storage = storage_wtype
        return self


class AppStateExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_decl: AppStateDeclaration, location: SourceLocation) -> None:
        self.state_decl = state_decl
        super().__init__(location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        exists_expr = TupleItemExpression(
            source_location=location,
            base=_build_app_global_get_ex(self.state_decl, location),
            index=1,
        )
        if negate:
            expr: Expression = Not(location, exists_expr)
        else:
            expr = exists_expr
        return var_expression(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "value":
                return AppStateValueExpressionBuilder(
                    state_decl=self.state_decl,
                    location=self.source_location,
                )
            case "get":
                return AppStateGetExpressionBuilder(
                    state_decl=self.state_decl, location=self.source_location
                )
            case "maybe":
                return AppStateMaybeExpressionBuilder(
                    state_decl=self.state_decl, location=self.source_location
                )
            case _:
                return super().member_access(name, location)


class AppStateMethodBaseExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_decl: AppStateDeclaration, location: SourceLocation) -> None:
        super().__init__(location)
        self.state_decl = state_decl


class AppStateMaybeExpressionBuilder(AppStateMethodBaseExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case []:
                return var_expression(_build_app_global_get_ex(self.state_decl, location))
            case _:
                raise CodeError("Unexpected/unhandled arguments", location)


class AppStateGetExpressionBuilder(AppStateMethodBaseExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        (default_arg,) = args
        default_expr = expect_operand_wtype(
            default_arg, target_wtype=self.state_decl.storage_wtype
        )
        app_global_get_ex = create_temporary_assignment(
            _build_app_global_get_ex(self.state_decl, location), location
        )
        conditional_expr = ConditionalExpression(
            location,
            wtype=self.state_decl.storage_wtype,
            condition=TupleItemExpression(
                app_global_get_ex.define, index=1, source_location=location
            ),
            true_expr=TupleItemExpression(
                app_global_get_ex.read, index=0, source_location=location
            ),
            false_expr=default_expr,
        )
        return var_expression(conditional_expr)


def _build_app_global_get_ex(
    state_decl: AppStateDeclaration, location: SourceLocation
) -> StateGetEx:
    return StateGetEx(field=_build_field(state_decl, location), source_location=location)


class AppStateValueExpressionBuilder(ValueProxyExpressionBuilder):
    def __init__(self, state_decl: AppStateDeclaration, location: SourceLocation):
        assert state_decl.kind is AppStateKind.app_global
        self.__field = _build_field(state_decl, location)
        self.wtype = state_decl.storage_wtype
        super().__init__(self.__field)

    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.__field, source_location=location)
