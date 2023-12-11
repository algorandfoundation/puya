from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    AppAccountStateExpression,
    AppStateDefinition,
    AppStateExpression,
    AppStateKind,
    BytesConstant,
    ConditionalExpression,
    Expression,
    ExpressionStatement,
    InstanceSubroutineTarget,
    IntegerConstant,
    IntrinsicCall,
    Literal,
    Statement,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.subroutine import SubroutineInvokerExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import create_temporary_assignment, expect_operand_wtype
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class ContractSelfExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        app_state: dict[str, AppStateDefinition],
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._app_state = app_state

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        try:
            state_def = self._app_state[name]
        except KeyError:
            return SubroutineInvokerExpressionBuilder(
                context=self.context,
                target=InstanceSubroutineTarget(name=name),
                location=location,
            )
        if state_def.kind is AppStateKind.app_global:
            global_expr = AppStateExpression(
                source_location=location,
                wtype=state_def.storage_wtype,
                key=state_def.key,
                key_encoding=state_def.key_encoding,
            )

            return var_expression(global_expr)
        else:
            assert state_def.kind is AppStateKind.account_local
            return ContractLocalStateExpressionBuilder(state_def, location)


class ContractLocalStateExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_def: AppStateDefinition, location: SourceLocation):
        assert state_def.kind is AppStateKind.account_local
        super().__init__(location)
        self.state_def = state_def

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        index_expr = _validated_index_expr(index)
        return ContractLocalStateForAccountExpressionBuilder(
            state_def=self.state_def,
            index_expr=index_expr,
            location=location,
        )

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        app_local_get_ex = _build_app_local_get_ex(self.state_def, item, location)
        exists_expr = TupleItemExpression(app_local_get_ex, index=1, source_location=location)
        return var_expression(exists_expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "get":
                return ContractLocalStateGetMethodBuilder(self.state_def, location)
            case "maybe":
                return ContractLocalStateMaybeMethodBuilder(self.state_def, location)
        return super().member_access(name, location)


class ContractLocalStateGetMethodBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_def: AppStateDefinition, location: SourceLocation):
        super().__init__(location)
        self.state_def = state_def

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
        default_expr = expect_operand_wtype(default_arg, target_wtype=self.state_def.storage_wtype)
        app_local_get_ex = create_temporary_assignment(
            _build_app_local_get_ex(self.state_def, item, location), location
        )
        conditional_expr = ConditionalExpression(
            location,
            wtype=self.state_def.storage_wtype,
            condition=TupleItemExpression(
                app_local_get_ex.define, index=1, source_location=location
            ),
            true_expr=TupleItemExpression(
                app_local_get_ex.read, index=0, source_location=location
            ),
            false_expr=default_expr,
        )
        return var_expression(conditional_expr)


class ContractLocalStateMaybeMethodBuilder(IntermediateExpressionBuilder):
    def __init__(self, state_def: AppStateDefinition, location: SourceLocation):
        super().__init__(location)
        self.state_def = state_def

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
                app_local_get_ex = _build_app_local_get_ex(self.state_def, item, location)
                return var_expression(app_local_get_ex)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


def _build_app_local_get_ex(
    state_def: AppStateDefinition, item: ExpressionBuilder | Literal, location: SourceLocation
) -> IntrinsicCall:
    index_expr = _validated_index_expr(item)
    app_local_get_ex = IntrinsicCall(
        source_location=location,
        op_code="app_local_get_ex",
        stack_args=[
            index_expr,
            UInt64Constant(value=0, source_location=location),
            BytesConstant(value=state_def.key, source_location=location),
        ],
        wtype=wtypes.WTuple.from_types((state_def.storage_wtype, wtypes.bool_wtype)),
    )
    return app_local_get_ex


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


class ContractLocalStateForAccountExpressionBuilder(ValueExpressionBuilder):
    def __init__(
        self, index_expr: Expression, state_def: AppStateDefinition, location: SourceLocation
    ):
        assert state_def.kind is AppStateKind.account_local
        self.wtype = state_def.storage_wtype
        expr = AppAccountStateExpression(
            source_location=location,
            key=state_def.key,
            key_encoding=state_def.key_encoding,
            wtype=state_def.storage_wtype,
            account=index_expr,
        )
        self.index_expr = index_expr
        self.state_def = state_def
        super().__init__(expr)

    def delete(self, location: SourceLocation) -> Statement:
        return ExpressionStatement(
            IntrinsicCall(
                source_location=location,
                op_code="app_local_del",
                stack_args=[
                    self.index_expr,
                    BytesConstant(value=self.state_def.key, source_location=self.source_location),
                ],
                wtype=wtypes.void_wtype,
            )
        )

    @property
    def _proxied(self) -> ExpressionBuilder:
        return var_expression(self.expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return self._proxied.bool_eval(location, negate=negate)

    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._proxied.unary_plus(location)

    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._proxied.unary_minus(location)

    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        return self._proxied.bitwise_invert(location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._proxied.contains(item, location)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._proxied.compare(other, op, location)

    def binary_op(
        self,
        other: ExpressionBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> ExpressionBuilder:
        return self._proxied.binary_op(other, op, location, reverse=reverse)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        return self._proxied.augmented_assignment(op, rhs, location)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._proxied.index(index, location)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        return self._proxied.slice_index(begin_index, end_index, stride, location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return self._proxied.call(args, arg_kinds, arg_names, location, original_expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        return self._proxied.member_access(name, location)

    def iterate(self) -> Iteration:
        return self._proxied.iterate()


class LocalStorageClassExpressionBuilder(IntermediateExpressionBuilder):
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
        call_expr_loc = location
        match args:
            case [TypeClassExpressionBuilder() as typ_class_eb]:
                storage_wtype = typ_class_eb.produces()
            case _:
                raise CodeError("expected a single argument with storage type", call_expr_loc)

        if self._storage is not None and self._storage != storage_wtype:
            raise CodeError(
                "Local storage explicit type annotation does not match first argument"
                " - suggest to remove the explicit type annotation,"
                " it shouldn't be required",
                call_expr_loc,
            )
        return self
