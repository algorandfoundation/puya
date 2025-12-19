import abc
import typing

import mypy.checker
import mypy.nodes

from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.exceptions import UnsupportedASTError
from puyapy.awst_build.utils import refers_to_fullname


class _BaseMyPyVisitor:
    def __init__(self, context: ASTConversionModuleContext):
        self.context = context

    def _location(self, node: mypy.nodes.Context) -> SourceLocation:
        return self.context.node_location(node)

    def _error(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        self.context.error(msg, location)

    def _precondition(
        self,
        condition: bool,  # noqa: FBT001
        /,
        msg: str,
        location: mypy.nodes.Context | SourceLocation,
    ) -> None:
        if not condition:
            raise InternalError(
                msg,
                self._location(location) if isinstance(location, mypy.nodes.Context) else location,
            )

    def _unsupported_node(self, node: mypy.nodes.Context, msg: str) -> typing.Never:
        raise UnsupportedASTError(msg, self._location(node))


class BaseMyPyStatementVisitor[_TStatement](
    _BaseMyPyVisitor,
    abc.ABC,
):
    def visit_statement(self, stmt: mypy.nodes.Statement) -> _TStatement:
        """Dispatch to the appropriate visit method based on statement type."""
        match stmt:
            case mypy.nodes.AssignmentStmt():
                return self.visit_assignment_stmt(stmt)
            case mypy.nodes.OperatorAssignmentStmt():
                return self.visit_operator_assignment_stmt(stmt)
            case mypy.nodes.IfStmt():
                return self.visit_if_stmt(stmt)
            case mypy.nodes.ForStmt():
                return self.visit_for_stmt(stmt)
            case mypy.nodes.WhileStmt():
                return self.visit_while_stmt(stmt)
            case mypy.nodes.Block():
                return self.visit_block(stmt)
            case mypy.nodes.ExpressionStmt():
                return self.visit_expression_stmt(stmt)
            case mypy.nodes.ReturnStmt():
                return self.visit_return_stmt(stmt)
            case mypy.nodes.AssertStmt():
                return self.visit_assert_stmt(stmt)
            case mypy.nodes.FuncDef():
                return self.visit_func_def(stmt)
            case mypy.nodes.OverloadedFuncDef():
                return self.visit_overloaded_func_def(stmt)
            case mypy.nodes.ClassDef():
                return self.visit_class_def(stmt)
            case mypy.nodes.Decorator():
                return self.visit_decorator(stmt)
            case mypy.nodes.BreakStmt():
                return self.visit_break_stmt(stmt)
            case mypy.nodes.ContinueStmt():
                return self.visit_continue_stmt(stmt)
            case mypy.nodes.DelStmt():
                return self.visit_del_stmt(stmt)
            case mypy.nodes.MatchStmt():
                return self.visit_match_stmt(stmt)

        stmt_type = type(stmt)
        if stmt_type in (
            mypy.nodes.Import,
            mypy.nodes.ImportFrom,
            mypy.nodes.ImportAll,
            mypy.nodes.PassStmt,
        ):
            return self.empty_statement(stmt)

        if stmt_type in (
            mypy.nodes.WithStmt,
            mypy.nodes.GlobalDecl,
            mypy.nodes.NonlocalDecl,
            mypy.nodes.RaiseStmt,
            mypy.nodes.TryStmt,
            mypy.nodes.TypeAliasStmt,
        ):
            self._unsupported_node(stmt, "unsupported statement")

        raise InternalError(
            f"unsupported statement type: {stmt_type.__name__}",
            self._location(stmt),
        )

    # ~~~ abstract methods that subclasses must implement ~~~ #
    @abc.abstractmethod
    def visit_block(self, o: mypy.nodes.Block) -> _TStatement: ...

    @abc.abstractmethod
    def visit_assignment_stmt(self, o: mypy.nodes.AssignmentStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_operator_assignment_stmt(
        self, o: mypy.nodes.OperatorAssignmentStmt
    ) -> _TStatement: ...

    @abc.abstractmethod
    def visit_expression_stmt(self, o: mypy.nodes.ExpressionStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_if_stmt(self, o: mypy.nodes.IfStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_while_stmt(self, o: mypy.nodes.WhileStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_for_stmt(self, o: mypy.nodes.ForStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_return_stmt(self, o: mypy.nodes.ReturnStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_assert_stmt(self, o: mypy.nodes.AssertStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_del_stmt(self, o: mypy.nodes.DelStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_break_stmt(self, o: mypy.nodes.BreakStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_continue_stmt(self, o: mypy.nodes.ContinueStmt) -> _TStatement: ...

    @abc.abstractmethod
    def visit_class_def(self, o: mypy.nodes.ClassDef) -> _TStatement: ...

    @abc.abstractmethod
    def visit_match_stmt(self, o: mypy.nodes.MatchStmt) -> _TStatement: ...

    # ~~~ things we can just ignore ~~~ #

    @abc.abstractmethod
    def empty_statement(self, stmt: mypy.nodes.Statement) -> _TStatement: ...

    # ~~~ simplify function (decorated, overloaded, normal) visitation ~~~ #

    def check_fatal_decorators(self, exprs: list[mypy.nodes.Expression]) -> None:
        for dec_expr in exprs:
            if isinstance(dec_expr, mypy.nodes.CallExpr):
                dec_expr = dec_expr.callee
            if isinstance(dec_expr, mypy.nodes.RefExpr):
                if refers_to_fullname(
                    dec_expr, "typing.no_type_check", "typing_extensions.no_type_check"
                ):
                    raise CodeError(
                        "no_type_check is not supported -"
                        " type checking is required for compilation",
                        self._location(dec_expr),
                    )
            else:
                self.context.warning(
                    "Unable to determine full name of expression", self._location(dec_expr)
                )

    @typing.final
    def visit_func_def(self, fdef: mypy.nodes.FuncDef) -> _TStatement:
        self._precondition(
            not fdef.is_decorated,
            "Decorated functions should have been visited via visit_decorator",
            fdef,
        )
        self._precondition(not fdef.is_property, "Property function that is not decorated??", fdef)
        return self._do_function(fdef, decorator=None)

    @typing.final
    def visit_decorator(self, dec: mypy.nodes.Decorator) -> _TStatement:
        self.check_fatal_decorators(dec.decorators)
        if mypy.checker.is_property(dec):
            self._unsupported_node(dec, "property decorator/descriptor not supported currently")
        return self._do_function(dec.func, dec)

    @typing.final
    def visit_overloaded_func_def(self, o: mypy.nodes.OverloadedFuncDef) -> _TStatement:
        # This could either be a @typing.overload, in which case o.impl will contain
        # the actual function, or it could be a @property with a setter and/or a deleter,
        # in which case o.impl will be None
        if mypy.checker.is_property(o):
            self._unsupported_node(o, "property decorator/descriptor not supported currently")
        if o.impl:
            self.context.warning(
                "@typing.overload() should not be required, "
                "and may not function exactly as intended",
                o,
            )
            return self.visit_statement(o.impl)
        else:
            # typing.overload sequences should always have an implementation,
            # unless they're in a stub file - but we don't process those,
            # so we shouldn't get here
            raise CodeError(
                "An overloaded function outside a stub file must have an implementation",
                self._location(o),
            )

    def _do_function(
        self,
        fdef: mypy.nodes.FuncDef,
        decorator: mypy.nodes.Decorator | None,
    ) -> _TStatement:
        self._precondition(
            not fdef.is_mypy_only, "function is defined in TYPE_CHECKING block", fdef
        )  # we shouldn't get here
        if fdef.is_generator:
            self._unsupported_node(fdef, "generator functions are not supported")
        if fdef.is_coroutine or fdef.is_awaitable_coroutine or fdef.is_async_generator:
            self._unsupported_node(fdef, "async functions are not supported")
        if fdef.dataclass_transform_spec is not None:
            self._unsupported_node(fdef, "data class transforms (PEP-681) are not supported ")
        return self.visit_function(fdef, decorator)

    @abc.abstractmethod
    def visit_function(
        self,
        fdef: mypy.nodes.FuncDef,
        decorator: mypy.nodes.Decorator | None,
    ) -> _TStatement: ...


class BaseMyPyExpressionVisitor[_TExpression](
    _BaseMyPyVisitor,
    abc.ABC,
):
    def visit_expression(self, expr: mypy.nodes.Expression) -> _TExpression:
        """Dispatch to the appropriate visit method based on expression type."""
        match expr:
            case mypy.nodes.IntExpr():
                return self.visit_int_expr(expr)
            case mypy.nodes.StrExpr():
                return self.visit_str_expr(expr)
            case mypy.nodes.BytesExpr():
                return self.visit_bytes_expr(expr)
            case mypy.nodes.NameExpr():
                return self.visit_name_expr(expr)
            case mypy.nodes.MemberExpr():
                return self.visit_member_expr(expr)
            case mypy.nodes.CallExpr():
                return self.visit_call_expr(expr)
            case mypy.nodes.OpExpr():
                return self.visit_op_expr(expr)
            case mypy.nodes.ComparisonExpr():
                return self.visit_comparison_expr(expr)
            case mypy.nodes.SuperExpr():
                return self.visit_super_expr(expr)
            case mypy.nodes.UnaryExpr():
                return self.visit_unary_expr(expr)
            case mypy.nodes.AssignmentExpr():
                return self.visit_assignment_expr(expr)
            case mypy.nodes.DictExpr():
                return self.visit_dict_expr(expr)
            case mypy.nodes.TupleExpr():
                return self.visit_tuple_expr(expr)
            case mypy.nodes.IndexExpr():
                return self.visit_index_expr(expr)
            case mypy.nodes.ConditionalExpr():
                return self.visit_conditional_expr(expr)
            case mypy.nodes.ListExpr():
                self._unsupported_node(expr, "unsupported usage of list literal")
            case mypy.nodes.EllipsisExpr():
                self._unsupported_node(expr, "unsupported usage of ...")
            case mypy.nodes.LambdaExpr():
                self._unsupported_node(expr, "lambda functions are not supported")
            case mypy.nodes.SliceExpr():
                self._unsupported_node(expr, "slices are not supported outside of indexing")
            case mypy.nodes.FloatExpr():
                self._unsupported_node(expr, "floating point math is not supported")
            case mypy.nodes.ComplexExpr():
                self._unsupported_node(expr, "complex math is not supported")
            case mypy.nodes.SetExpr():
                self._unsupported_node(expr, "sets are not supported")
            case (
                mypy.nodes.ListComprehension()
                | mypy.nodes.DictionaryComprehension()
                | mypy.nodes.SetComprehension()
            ):
                self._unsupported_node(expr, "comprehensions are not supported")
            case mypy.nodes.YieldExpr() | mypy.nodes.YieldFromExpr() | mypy.nodes.GeneratorExpr():
                self._unsupported_node(expr, "generator functions are not supported")
            case mypy.nodes.AwaitExpr():
                self._unsupported_node(expr, "async/await is not supported")
            case mypy.nodes.StarExpr():
                # star expression examples (non-exhaustive):
                #  head, *tail = my_list
                #  my_func(first, *rest)
                #  [prepend, *existing]
                raise InternalError(
                    "star expressions should be handled at a higher level", self._location(expr)
                )
            case mypy.nodes.TempNode():
                # "dummy node"
                raise InternalError(
                    "placeholder expression node encountered, should be handled at a higher level",
                    self._location(expr),
                )

        expr_type = type(expr)
        if expr_type in (
            mypy.nodes.CastExpr,
            mypy.nodes.AssertTypeExpr,
            mypy.nodes.RevealExpr,
            mypy.nodes.TypeApplication,
            mypy.nodes.TypeVarExpr,
            mypy.nodes.ParamSpecExpr,
            mypy.nodes.TypeVarTupleExpr,
            mypy.nodes.TypeAliasExpr,
            mypy.nodes.NamedTupleExpr,
            mypy.nodes.EnumCallExpr,
            mypy.nodes.TypedDictExpr,
            mypy.nodes.NewTypeExpr,
            mypy.nodes.PromoteExpr,
        ):
            raise InternalError(
                f"can't compile analysis-only expression of type {expr_type.__name__}",
                self._location(expr),
            )

        raise InternalError(
            f"unsupported expression type: {expr_type.__name__}",
            self._location(expr),
        )

    # ~~~ abstract methods that subclasses must implement ~~~ #
    @abc.abstractmethod
    def visit_int_expr(self, o: mypy.nodes.IntExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_str_expr(self, o: mypy.nodes.StrExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_bytes_expr(self, o: mypy.nodes.BytesExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_name_expr(self, o: mypy.nodes.NameExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_member_expr(self, o: mypy.nodes.MemberExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_call_expr(self, o: mypy.nodes.CallExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_op_expr(self, o: mypy.nodes.OpExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_comparison_expr(self, o: mypy.nodes.ComparisonExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_unary_expr(self, o: mypy.nodes.UnaryExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_index_expr(self, o: mypy.nodes.IndexExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_conditional_expr(self, o: mypy.nodes.ConditionalExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_tuple_expr(self, o: mypy.nodes.TupleExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_dict_expr(self, o: mypy.nodes.DictExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_super_expr(self, o: mypy.nodes.SuperExpr) -> _TExpression: ...

    @abc.abstractmethod
    def visit_assignment_expr(self, o: mypy.nodes.AssignmentExpr) -> _TExpression: ...
