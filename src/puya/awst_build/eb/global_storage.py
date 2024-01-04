from typing import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateDefinition,
    AppStateExpression,
    BytesConstant,
    Expression,
    IntrinsicCall,
    Literal,
    Lvalue,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.type_registry import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class GlobalStorageClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location)
        self._storage: wtypes.WType | None = None
        self._initial_value: Expression | None = None

    def rvalue(self) -> Expression:
        if self._initial_value is None:
            raise InternalError(
                f"{type(self).__name__} is not valid as an rvalue as it does not have an"
                "initial value. Check has_initial_value before trying to read rvalue",
                self.source_location,
            )
        return self._initial_value

    def has_initial_value(self) -> bool:
        return self._initial_value is not None

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if self._storage is not None:
            raise InternalError("Multiple indexing of AppGlobal?", location)
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
                storage_wtype = value_eb.rvalue().wtype
                self._initial_value = value_eb.rvalue()
            case _:
                raise CodeError("expected a single argument with storage type", call_expr_loc)

        if self._storage is not None and self._storage != storage_wtype:
            raise CodeError(
                "Global storage explicit type annotation does not match first argument"
                " - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                call_expr_loc,
            )
        return self


class GlobalStorageExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        state_def: AppStateDefinition,
        location: SourceLocation,
    ) -> None:
        super().__init__(location)
        self.state_def = state_def
        self.key_expression = BytesConstant(
            value=state_def.key,
            encoding=state_def.key_encoding,
            source_location=location,
        )

    def lvalue(self) -> Lvalue:
        return AppStateExpression(
            source_location=self.source_location,
            key=self.state_def.key,
            key_encoding=self.state_def.key_encoding,
            wtype=self.state_def.storage_wtype,
        )

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "exists":
                return GlobalStorageExistsExpressionBuilder(
                    state_def=self.state_def,
                    location=self.source_location,
                    key_expression=self.key_expression,
                )
            case "get":
                return GlobalStorageGetExpressionBuilder(
                    state_def=self.state_def,
                    location=self.source_location,
                    key_expression=self.key_expression,
                )
            case "put":
                return GlobalStoragePutExpressionBuilder(
                    state_def=self.state_def,
                    location=self.source_location,
                    key_expression=self.key_expression,
                )
            case "maybe":
                return GlobalStorageMaybeExpressionBuilder(
                    state_def=self.state_def,
                    location=self.source_location,
                    key_expression=self.key_expression,
                )
            case "delete":
                return GlobalStorageDeleteExpressionBuilder(
                    state_def=self.state_def,
                    location=self.source_location,
                    key_expression=self.key_expression,
                )
            case _:
                return super().member_access(name, location)


class GlobalStorageMethodBaseExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self, state_def: AppStateDefinition, location: SourceLocation, key_expression: Expression
    ) -> None:
        super().__init__(location)
        self.state_def = state_def
        self.key_expression = key_expression


class GlobalStorageExistsExpressionBuilder(GlobalStorageMethodBaseExpressionBuilder):
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
                return var_expression(
                    TupleItemExpression(
                        source_location=location,
                        base=IntrinsicCall(
                            op_code="app_global_get_ex",
                            stack_args=[
                                UInt64Constant(value=0, source_location=location),
                                self.key_expression,
                            ],
                            wtype=wtypes.WTuple.from_types(
                                (self.state_def.storage_wtype, wtypes.bool_wtype)
                            ),
                            source_location=location,
                        ),
                        index=1,
                    )
                )
            case _:
                raise CodeError("Unexpected/unhandled arguments", location)


class GlobalStorageMaybeExpressionBuilder(GlobalStorageMethodBaseExpressionBuilder):
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
                return var_expression(
                    IntrinsicCall(
                        op_code="app_global_get_ex",
                        stack_args=[
                            UInt64Constant(value=0, source_location=location),
                            self.key_expression,
                        ],
                        wtype=wtypes.WTuple.from_types(
                            (self.state_def.storage_wtype, wtypes.bool_wtype)
                        ),
                        source_location=location,
                    ),
                )
            case _:
                raise CodeError("Unexpected/unhandled arguments", location)


class GlobalStorageGetExpressionBuilder(GlobalStorageMethodBaseExpressionBuilder):
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
                return var_expression(AppStateExpression.from_state_def(self.state_def, location))
            case _:
                raise CodeError("Unexpected/unhandled arguments", location)


class GlobalStorageDeleteExpressionBuilder(GlobalStorageMethodBaseExpressionBuilder):
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
                return var_expression(
                    IntrinsicCall(
                        op_code="app_global_del",
                        stack_args=[
                            self.key_expression,
                        ],
                        wtype=wtypes.void_wtype,
                        source_location=location,
                    ),
                )
            case _:
                raise CodeError("Unexpected/unhandled arguments", location)


class GlobalStoragePutExpressionBuilder(GlobalStorageMethodBaseExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [value]:
                typed_value = expect_operand_wtype(value, self.state_def.storage_wtype)
                return var_expression(
                    IntrinsicCall(
                        op_code="app_global_put",
                        stack_args=[
                            self.key_expression,
                            typed_value,
                        ],
                        wtype=wtypes.void_wtype,
                        source_location=location,
                    ),
                )
            case _:
                raise CodeError("Unexpected/unhandled arguments", location)
