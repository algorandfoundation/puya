import abc
import typing

import mypy.checker
import mypy.nodes
import mypy.visitor

from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.exceptions import UnsupportedASTError
from puya.awst_build.utils import refers_to_fullname
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation

_TStatement = typing.TypeVar("_TStatement")
_TExpression = typing.TypeVar("_TExpression")


class BaseMyPyStatementVisitor(
    mypy.visitor.StatementVisitor[_TStatement],
    abc.ABC,
):
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

    # ~~~ things we can just ignore ~~~ #
    def visit_pass_stmt(self, o: mypy.nodes.PassStmt) -> _TStatement:
        return self.empty_statement(o)

    def visit_import(self, o: mypy.nodes.Import) -> _TStatement:
        return self.empty_statement(o)

    def visit_import_from(self, o: mypy.nodes.ImportFrom) -> _TStatement:
        return self.empty_statement(o)

    def visit_import_all(self, o: mypy.nodes.ImportAll) -> _TStatement:
        return self.empty_statement(o)

    @abc.abstractmethod
    def empty_statement(self, stmt: mypy.nodes.Statement) -> _TStatement:
        ...

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
            raise UnsupportedASTError(
                self._location(dec),
                details="property decorator/descriptor not supported currently",
            )
        return self._do_function(dec.func, dec)

    @typing.final
    def visit_overloaded_func_def(self, o: mypy.nodes.OverloadedFuncDef) -> _TStatement:
        # This could either be a @typing.overload, in which case o.impl will contain
        # the actual function, or it could be a @property with a setter and/or a deleter,
        # in which case o.impl will be None
        if mypy.checker.is_property(o):
            raise UnsupportedASTError(
                self._location(o), details="property decorator/descriptor not supported currently"
            )
        elif o.impl:
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
            raise UnsupportedASTError(
                self._location(fdef), details="generator functions are not supported"
            )
        if fdef.is_coroutine or fdef.is_awaitable_coroutine or fdef.is_async_generator:
            raise UnsupportedASTError(
                self._location(fdef), details="async functions are not supported"
            )
        if fdef.dataclass_transform_spec is not None:
            raise UnsupportedASTError(
                self._location(fdef), details="data class transforms (PEP-681) are not supported "
            )
        return self.visit_function(fdef, decorator)

    @abc.abstractmethod
    def visit_function(
        self,
        fdef: mypy.nodes.FuncDef,
        decorator: mypy.nodes.Decorator | None,
    ) -> _TStatement:
        ...

    # ~~~ unsupported scope modifiers ~~~ #
    def visit_global_decl(self, stmt: mypy.nodes.GlobalDecl) -> _TStatement:
        raise UnsupportedASTError(
            self._location(stmt), details="global variables must be immutable"
        )

    # TODO: do we reject nonlocal here too? are nested functions in/out?

    # ~~~ raising and handling exceptions unsupported ~~~ #
    def visit_raise_stmt(self, stmt: mypy.nodes.RaiseStmt) -> _TStatement:
        raise UnsupportedASTError(
            self._location(stmt),
            details="exception raising and exception handling not supported",
        )

    def visit_try_stmt(self, stmt: mypy.nodes.TryStmt) -> _TStatement:
        raise UnsupportedASTError(
            self._location(stmt),
            details="exception raising and exception handling not supported",
        )

    def visit_with_stmt(self, stmt: mypy.nodes.WithStmt) -> _TStatement:
        raise UnsupportedASTError(
            self._location(stmt),
            details="context managers are redundant due to a lack of exception support",
        )


class BaseMyPyVisitor(
    typing.Generic[_TStatement, _TExpression],
    BaseMyPyStatementVisitor[_TStatement],
    mypy.visitor.ExpressionVisitor[_TExpression],
    abc.ABC,
):
    # ~~~ things that we support but shouldn't encounter via visitation ~~~ #
    def visit_star_expr(self, expr: mypy.nodes.StarExpr) -> _TExpression:
        # star expression examples (non-exhaustive):
        #  head, *tail = my_list
        #  my_func(first, *rest)
        #  [prepend, *existing]
        raise InternalError(
            "star expressions should be handled at a higher level", self._location(expr)
        )

    # ~~~ unsupported data structures (yet?) ~~~ #
    def visit_dict_expr(self, expr: mypy.nodes.DictExpr) -> _TExpression:
        raise UnsupportedASTError(self._location(expr), details="dictionaries are not supported")

    def visit_dictionary_comprehension(
        self, expr: mypy.nodes.DictionaryComprehension
    ) -> _TExpression:
        raise UnsupportedASTError(self._location(expr), details="dictionaries are not supported")

    def visit_set_expr(self, expr: mypy.nodes.SetExpr) -> _TExpression:
        raise UnsupportedASTError(self._location(expr), details="sets are not supported")

    def visit_set_comprehension(self, expr: mypy.nodes.SetComprehension) -> _TExpression:
        raise UnsupportedASTError(self._location(expr), details="sets are not supported")

    # ~~~ math we don't support (yet?) ~~~ #
    def visit_float_expr(self, expr: mypy.nodes.FloatExpr) -> _TExpression:
        raise UnsupportedASTError(
            self._location(expr), details="floating point math is not supported"
        )

    def visit_complex_expr(self, expr: mypy.nodes.ComplexExpr) -> _TExpression:
        raise UnsupportedASTError(self._location(expr), details="complex math is not supported")

    # ~~~ generator functions unsupported ~~~ #
    def visit_generator_expr(self, expr: mypy.nodes.GeneratorExpr) -> _TExpression:
        raise UnsupportedASTError(
            self._location(expr), details="generator functions are not supported"
        )

    def visit_yield_expr(self, expr: mypy.nodes.YieldExpr) -> _TExpression:
        raise UnsupportedASTError(
            self._location(expr), details="generator functions are not supported"
        )

    def visit_yield_from_expr(self, o: mypy.nodes.YieldFromExpr) -> _TExpression:
        raise UnsupportedASTError(
            self._location(o), details="generator functions are not supported"
        )

    # ~~~ async/await functions unsupported ~~~ #
    def visit_await_expr(self, o: mypy.nodes.AwaitExpr) -> _TExpression:
        raise UnsupportedASTError(self._location(o), details="async/await is not supported")

    # ~~~ analysis-only expressions, should never show up ~~~ #
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

    def visit_cast_expr(self, expr: mypy.nodes.CastExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    def visit_assert_type_expr(self, expr: mypy.nodes.AssertTypeExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    def visit_enum_call_expr(self, expr: mypy.nodes.EnumCallExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    def visit__promote_expr(self, expr: mypy.nodes.PromoteExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    def visit_namedtuple_expr(self, expr: mypy.nodes.NamedTupleExpr) -> _TExpression:
        # NOTE: only appears as (ClassDef|CallExpr).analyzed
        return self.__analysis_only(expr)

    def visit_newtype_expr(self, expr: mypy.nodes.NewTypeExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    def visit_type_alias_expr(self, expr: mypy.nodes.TypeAliasExpr) -> _TExpression:
        # NOTE: only appears as (IndexExpr|CallExpr|OpExpr).analyzed
        return self.__analysis_only(expr)

    def visit_type_application(self, expr: mypy.nodes.TypeApplication) -> _TExpression:
        # NOTE: only appears as IndexExpr.analyzed
        return self.__analysis_only(expr)

    def visit_type_var_expr(self, expr: mypy.nodes.TypeVarExpr) -> _TExpression:
        # NOTE: appears as CallExpr.analyzed OR as SymbolTableNode.node
        return self.__analysis_only(expr)

    def visit_paramspec_expr(self, expr: mypy.nodes.ParamSpecExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    def visit_type_var_tuple_expr(self, expr: mypy.nodes.TypeVarTupleExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)

    def visit_typeddict_expr(self, expr: mypy.nodes.TypedDictExpr) -> _TExpression:
        # NOTE: only appears as (ClassDef|CallExpr).analyzed
        return self.__analysis_only(expr)

    def visit_reveal_expr(self, expr: mypy.nodes.RevealExpr) -> _TExpression:
        # NOTE: only appears as CallExpr.analyzed
        return self.__analysis_only(expr)
