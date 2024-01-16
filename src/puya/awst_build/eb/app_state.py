from typing import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateDefinition,
    AppStateExpression,
    AppStateKind,
    BytesConstant,
    ConditionalExpression,
    Expression,
    ExpressionStatement,
    IntrinsicCall,
    Literal,
    Not,
    Statement,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import constants
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.type_registry import var_expression
from puya.awst_build.eb.value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.utils import create_temporary_assignment, expect_operand_wtype
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


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
    def __init__(self, state_def: AppStateDefinition, location: SourceLocation) -> None:
        self.state_def = state_def
        super().__init__(location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        exists_expr = TupleItemExpression(
            source_location=location,
            base=_build_app_global_get_ex(self.state_def, location),
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
                    state_def=self.state_def,
                    location=self.source_location,
                )
            case "get":
                return AppStateGetExpressionBuilder(
                    state_def=self.state_def, location=self.source_location
                )
            case "maybe":
                return AppStateMaybeExpressionBuilder(
                    state_def=self.state_def, location=self.source_location
                )
            case _:
                return super().member_access(name, location)


class AppStateMethodBaseExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_def: AppStateDefinition, location: SourceLocation) -> None:
        super().__init__(location)
        self.state_def = state_def


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
                return var_expression(_build_app_global_get_ex(self.state_def, location))
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
        default_expr = expect_operand_wtype(default_arg, target_wtype=self.state_def.storage_wtype)
        app_global_get_ex = create_temporary_assignment(
            _build_app_global_get_ex(self.state_def, location), location
        )
        conditional_expr = ConditionalExpression(
            location,
            wtype=self.state_def.storage_wtype,
            condition=TupleItemExpression(
                app_global_get_ex.define, index=1, source_location=location
            ),
            true_expr=TupleItemExpression(
                app_global_get_ex.read, index=0, source_location=location
            ),
            false_expr=default_expr,
        )
        return var_expression(conditional_expr)


def _key_constant(state_def: AppStateDefinition, location: SourceLocation) -> BytesConstant:
    return BytesConstant(
        value=state_def.key, encoding=state_def.key_encoding, source_location=location
    )


def _build_app_global_get_ex(
    state_def: AppStateDefinition, location: SourceLocation
) -> IntrinsicCall:
    return IntrinsicCall(
        op_code="app_global_get_ex",
        stack_args=[
            UInt64Constant(value=0, source_location=location),
            _key_constant(state_def, location),
        ],
        wtype=wtypes.WTuple.from_types((state_def.storage_wtype, wtypes.bool_wtype)),
        source_location=location,
    )


class AppStateValueExpressionBuilder(ValueProxyExpressionBuilder):
    def __init__(self, state_def: AppStateDefinition, location: SourceLocation):
        assert state_def.kind is AppStateKind.app_global
        self.wtype = state_def.storage_wtype
        expr = AppStateExpression.from_state_def(state_def, location)
        self.state_def = state_def
        super().__init__(expr)

    def delete(self, location: SourceLocation) -> Statement:
        return ExpressionStatement(
            IntrinsicCall(
                op_code="app_global_del",
                stack_args=[_key_constant(self.state_def, self.source_location)],
                wtype=wtypes.void_wtype,
                source_location=location,
            ),
        )
