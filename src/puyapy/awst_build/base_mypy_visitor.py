import abc
import typing

import mypy.checker
import mypy.nodes
import mypy.visitor

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

    def _unsupported_node(self, node: mypy.nodes.Context, details: str) -> typing.Never:
        raise UnsupportedASTError(node, self._location(node), details=details)


class BaseMyPyStatementVisitor[_TStatement](
    _BaseMyPyVisitor,
    mypy.visitor.StatementVisitor[_TStatement],
    abc.ABC,
):
    # ~~~ things we can just ignore ~~~ #
    @typing.override
    def visit_pass_stmt(self, o: mypy.nodes.PassStmt) -> _TStatement:
        return self.empty_statement(o)

    @typing.override
    def visit_import(self, o: mypy.nodes.Import) -> _TStatement:
        return self.empty_statement(o)

    @typing.override
    def visit_import_from(self, o: mypy.nodes.ImportFrom) -> _TStatement:
        return self.empty_statement(o)

    @typing.override
    def visit_import_all(self, o: mypy.nodes.ImportAll) -> _TStatement:
        return self.empty_statement(o)

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
    @typing.override
    def visit_func_def(self, fdef: mypy.nodes.FuncDef) -> _TStatement:
        self._precondition(
            not fdef.is_decorated,
            "Decorated functions should have been visited via visit_decorator",
            fdef,
        )
        self._precondition(not fdef.is_property, "Property function that is not decorated??", fdef)
        return self._do_function(fdef, decorator=None)

    @typing.final
    @typing.override
    def visit_decorator(self, dec: mypy.nodes.Decorator) -> _TStatement:
        self.check_fatal_decorators(dec.decorators)
        if mypy.checker.is_property(dec):
            self._unsupported_node(dec, "property decorator/descriptor not supported currently")
        return self._do_function(dec.func, dec)

    @typing.final
    @typing.override
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
            return o.impl.accept(self)
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

    # ~~~ unsupported scope modifiers ~~~ #
    @typing.override
    def visit_global_decl(self, stmt: mypy.nodes.GlobalDecl) -> typing.Never:
        self._unsupported_node(stmt, "global variables must be immutable")

    # TODO: do we reject nonlocal here too? are nested functions in/out?
    @typing.override
    def visit_nonlocal_decl(self, o: mypy.nodes.NonlocalDecl) -> typing.Never:
        self._unsupported_node(o, "nested functions are not supported")

    # ~~~ raising and handling exceptions unsupported ~~~ #
    @typing.override
    def visit_raise_stmt(self, stmt: mypy.nodes.RaiseStmt) -> typing.Never:
        self._unsupported_node(stmt, "exception raising and exception handling not supported")

    @typing.override
    def visit_try_stmt(self, stmt: mypy.nodes.TryStmt) -> typing.Never:
        self._unsupported_node(stmt, "exception raising and exception handling not supported")

    @typing.override
    def visit_with_stmt(self, stmt: mypy.nodes.WithStmt) -> typing.Never:
        self._unsupported_node(
            stmt,
            "context managers are redundant due to a lack of exception support",
        )


class BaseMyPyExpressionVisitor[_TExpression](
    _BaseMyPyVisitor,
    mypy.visitor.ExpressionVisitor[_TExpression],
    abc.ABC,
):
    # ~~~ things that we support but shouldn't encounter via visitation ~~~ #
    @typing.override
    def visit_star_expr(self, expr: mypy.nodes.StarExpr) -> _TExpression:
        # star expression examples (non-exhaustive):
        #  head, *tail = my_list
        #  my_func(first, *rest)
        #  [prepend, *existing]
        raise InternalError(
            "star expressions should be handled at a higher level", self._location(expr)
        )

    @typing.override
    def visit_dictionary_comprehension(
        self, expr: mypy.nodes.DictionaryComprehension
    ) -> typing.Never:
        self._unsupported_node(expr, "dictionaries are not supported")

    @typing.override
    def visit_set_expr(self, expr: mypy.nodes.SetExpr) -> typing.Never:
        self._unsupported_node(expr, "sets are not supported")

    @typing.override
    def visit_set_comprehension(self, expr: mypy.nodes.SetComprehension) -> typing.Never:
        self._unsupported_node(expr, "sets are not supported")

    # ~~~ math we don't support (yet?) ~~~ #
    @typing.override
    def visit_float_expr(self, expr: mypy.nodes.FloatExpr) -> typing.Never:
        self._unsupported_node(expr, "floating point math is not supported")

    @typing.override
    def visit_complex_expr(self, expr: mypy.nodes.ComplexExpr) -> typing.Never:
        self._unsupported_node(expr, "complex math is not supported")

    # ~~~ generator functions unsupported ~~~ #
    @typing.override
    def visit_generator_expr(self, expr: mypy.nodes.GeneratorExpr) -> typing.Never:
        self._unsupported_node(expr, "generator functions are not supported")

    @typing.override
    def visit_yield_expr(self, expr: mypy.nodes.YieldExpr) -> typing.Never:
        self._unsupported_node(expr, "generator functions are not supported")

    @typing.override
    def visit_yield_from_expr(self, o: mypy.nodes.YieldFromExpr) -> typing.Never:
        self._unsupported_node(o, "generator functions are not supported")

    # ~~~ async/await functions unsupported ~~~ #
    @typing.override
    def visit_await_expr(self, o: mypy.nodes.AwaitExpr) -> typing.Never:
        self._unsupported_node(o, "async/await is not supported")

    # ~~~ analysis-only expressions, should never show up ~~~ #
    @typing.override
    def visit_temp_node(self, expr: mypy.nodes.TempNode) -> _TExpression:
        # "dummy node"
        raise InternalError(
            "Placeholder expression node encountered, should be handled at a higher level",
            self._location(expr),
        )

    def __analysis_only(self, expr: mypy.nodes.Expression) -> typing.Never:
        raise InternalError(
            f"Can't compile analysis-only expression of type {type(expr).__name__}",
            self._location(expr),
        )

    @typing.override
    def visit_cast_expr(self, expr: mypy.nodes.CastExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_assert_type_expr(self, expr: mypy.nodes.AssertTypeExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_enum_call_expr(self, expr: mypy.nodes.EnumCallExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit__promote_expr(self, expr: mypy.nodes.PromoteExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_namedtuple_expr(self, expr: mypy.nodes.NamedTupleExpr) -> _TExpression:
        # NOTE: only appears as (ClassDef|CallExpr).analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_newtype_expr(self, expr: mypy.nodes.NewTypeExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_type_alias_expr(self, expr: mypy.nodes.TypeAliasExpr) -> _TExpression:
        # NOTE: only appears as (IndexExpr|CallExpr|OpExpr).analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_type_application(self, expr: mypy.nodes.TypeApplication) -> _TExpression:
        # NOTE: only appears as IndexExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_type_var_expr(self, expr: mypy.nodes.TypeVarExpr) -> _TExpression:
        # NOTE: appears as CallExpr.analyzed OR as SymbolTableNode.node
        return self.__analysis_only(expr)

    @typing.override
    def visit_paramspec_expr(self, expr: mypy.nodes.ParamSpecExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_type_var_tuple_expr(self, expr: mypy.nodes.TypeVarTupleExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_typeddict_expr(self, expr: mypy.nodes.TypedDictExpr) -> _TExpression:
        # NOTE: only appears as (ClassDef|CallExpr).analyzed
        return self.__analysis_only(expr)

    @typing.override
    def visit_reveal_expr(self, expr: mypy.nodes.RevealExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)
