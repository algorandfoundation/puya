import abc
import ast
import operator
import typing
from collections.abc import Callable, Mapping, Sequence

from mypy.types import PROTOCOL_NAMES

from puya import log
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy import reachability
from puyapy.awst_build import symbols
from puyapy.awst_build.context import ASTConversionContext, ASTConversionModuleContext
from puyapy.awst_build.utils import log_warnings
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors import ExpressionVisitor, StatementVisitor
from puyapy.models import ConstantValue

logger = log.get_logger(__name__)


StatementResult: typing.TypeAlias = list[symbols.CodeSymbol]


_BUILTIN_INHERITABLE: typing.Final = frozenset(("builtins.object", "abc.ABC", *PROTOCOL_NAMES))

StaticReachability = typing.Literal[
    reachability.ConditionValue.ALWAYS_TRUE,
    reachability.ConditionValue.ALWAYS_FALSE,
    reachability.ConditionValue.TYPE_CHECKING_TRUE,
    reachability.ConditionValue.TYPE_CHECKING_FALSE,
]


class _BaseModuleASTConverter[T](StatementVisitor[T], abc.ABC):
    @abc.abstractmethod
    def empty_statement(self, node: fast_nodes.Statement) -> T: ...

    @typing.override
    def visit_pass(self, pass_stmt: fast_nodes.Pass) -> T:
        return self.empty_statement(pass_stmt)

    @typing.override
    def visit_expression_statement(self, stmt: fast_nodes.ExpressionStatement) -> T:
        match stmt.expr:
            case fast_nodes.Constant(value=str()):
                # ignore any doc-strings at module level
                return self.empty_statement(stmt)
        return self._unsupported(stmt)

    @typing.override
    def visit_delete(self, delete: fast_nodes.Delete) -> T:
        return self._unsupported(delete)

    @typing.override
    def visit_annotation(self, annotation: fast_nodes.AnnotationStatement) -> T:
        return self._unsupported(annotation)

    @typing.override
    def visit_for(self, for_stmt: fast_nodes.For) -> T:
        return self._unsupported(for_stmt)

    @typing.override
    def visit_while(self, while_stmt: fast_nodes.While) -> T:
        return self._unsupported(while_stmt)

    @typing.override
    def visit_assert(self, assert_stmt: fast_nodes.Assert) -> T:
        return self._unsupported(assert_stmt)

    @typing.override
    def visit_return(self, ret: fast_nodes.Return) -> T:
        # we don't descend into any construct where this would be valid in this visitor
        return self._invalid(ret)

    @typing.override
    def visit_break(self, break_stmt: fast_nodes.Break) -> T:
        # we don't descend into any construct where this would be valid in this visitor
        return self._invalid(break_stmt)

    @typing.override
    def visit_continue(self, continue_stmt: fast_nodes.Continue) -> T:
        # we don't descend into any construct where this would be valid in this visitor
        return self._invalid(continue_stmt)

    @typing.override
    def visit_match(self, match_stmt: fast_nodes.Match) -> T:
        return self._unsupported(match_stmt)

    def _unsupported(
        self,
        node: fast_nodes.Node,
        msg: str = "unsupported statement at module level",
        ex: Exception | None = None,
    ) -> typing.Never:
        raise CodeError(msg, node.source_location) from ex

    def _invalid(
        self,
        node: fast_nodes.Node,
        msg: str = "invalid Python syntax at module level",
    ) -> typing.Never:
        raise CodeError(msg, node.source_location)


class ModuleASTConverter(_BaseModuleASTConverter[StatementResult]):
    def __init__(self, context: ASTConversionModuleContext):
        self.context: typing.Final = context
        self._const_visitor = ModuleConstantExpressionVisitor(context, context.symbol_table)
        self._in_type_checking: bool = False
        self._imported_modules = set[str]()

    @typing.override
    def empty_statement(self, node: fast_nodes.Statement) -> StatementResult:
        return []

    @typing.override
    def visit_module_import(self, module_import: fast_nodes.ModuleImport) -> StatementResult:
        # ref: https://docs.python.org/3/reference/simple_stmts.html#the-import-statement
        for imp in module_import.names:
            if imp.as_name is not None:
                local_name = imp.as_name
                qualified_name = imp.name
            else:
                root = imp.name.partition(".")[0]
                local_name = root
                qualified_name = root
            if not self._in_type_checking:
                path = imp.name
                while path:
                    self._imported_modules.add(path)
                    path = path.rpartition(".")[0]
            sym = symbols.ImportedModule(
                name=local_name,
                qualified_name=qualified_name,
                definition=module_import,
                type_checking_only=self._in_type_checking,
            )
            try:
                existing_defn = self.context.symbol_table[local_name]
            except KeyError:
                insert_symbol = True
            else:
                if not (
                    isinstance(existing_defn, symbols.ImportedModule)
                    and existing_defn.qualified_name == qualified_name
                ):
                    self._unsupported(imp, "import would shadow existing definition")
                # only replace if the existing symbol was from a TYPE_CHECKING block
                # and this one isn't
                insert_symbol = existing_defn.type_checking_only and not self._in_type_checking
            if insert_symbol:
                self.context.symbol_table[local_name] = sym
        return []

    @typing.override
    def visit_from_import(self, from_import: fast_nodes.FromImport) -> StatementResult:
        # ref: https://docs.python.org/3/reference/simple_stmts.html#the-import-statement
        # also: https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
        from_symbols = self.context.symbol_tables.get(from_import.module)
        if from_symbols is None:
            # we expect there to be no dependency cycles at this point, unless
            # we're inside a TYPE_CHECKING block
            # TODO: what about implicit namespace packages??
            assert self._in_type_checking, f"unable to resolve symtable for {from_import.module}"

        return []

    @typing.override
    def visit_function_def(self, func_def: fast_nodes.FunctionDef) -> StatementResult:
        self._require_not_type_checking(func_def)
        raise NotImplementedError

    @typing.override
    def visit_class_def(self, class_def: fast_nodes.ClassDef) -> StatementResult:
        self._require_not_type_checking(class_def)
        raise NotImplementedError

    @typing.override
    def visit_assign(self, assign: fast_nodes.Assign) -> StatementResult:
        self._require_not_type_checking(assign)
        raise NotImplementedError

    @typing.override
    def visit_multi_assign(self, multi_assign: fast_nodes.MultiAssign) -> StatementResult:
        self._require_not_type_checking(multi_assign)
        raise NotImplementedError

    @typing.override
    def visit_aug_assign(self, aug_assign: fast_nodes.AugAssign) -> StatementResult:
        self._require_not_type_checking(aug_assign)
        match aug_assign.target:
            case fast_nodes.Name(id="__all__"):
                logger.critical("TODO: handle __all__", location=aug_assign.source_location)
                return []
            case _:
                self._unsupported(aug_assign)

    @typing.override
    def visit_if(self, if_stmt: fast_nodes.If) -> StatementResult:
        self._require_not_type_checking(if_stmt)  # no nesting if/else inside a if TYPE_CHECKING
        condition = evaluate_compile_time_constant_condition(self._const_visitor, if_stmt.test)
        result = self._visit_conditional(condition, if_stmt.body)
        assert condition.negated is not reachability.ConditionValue.UNKNOWN
        result += self._visit_conditional(condition.negated, if_stmt.else_body)
        return result

    def _visit_conditional(
        self, condition: StaticReachability, body: Sequence[fast_nodes.Statement] | None
    ) -> StatementResult:
        match condition:
            case reachability.ALWAYS_FALSE:
                return []
            case reachability.ALWAYS_TRUE:
                result = StatementResult()
                for stmt in body or ():
                    result.extend(stmt.accept(self))
                return result
            case reachability.TYPE_CHECKING_TRUE:
                assert not self._in_type_checking, "unexpected TYPE_CHECKING nesting"
                self._in_type_checking = True
                try:
                    result = StatementResult()
                    for stmt in body or ():
                        result.extend(stmt.accept(self))
                    return result
                finally:
                    self._in_type_checking = False
            case reachability.TYPE_CHECKING_FALSE:
                if body:
                    return self._unsupported(
                        body[0], "code that is conditional on not TYPE_CHECKING is not supported"
                    )
                return []

    def _require_not_type_checking(self, stmt: fast_nodes.Statement) -> None:
        if self._in_type_checking:
            self._unsupported(stmt, "statement is not supported inside a TYPE_CHECKING block")


class ModuleConstantExpressionVisitor(ExpressionVisitor[ConstantValue]):
    def __init__(self, ctx: ASTConversionContext, symbol_table: Mapping[str, symbols.Symbol]):
        self.ctx: typing.Final = ctx
        self.symbols: typing.Final = symbol_table

    @typing.override
    def visit_constant(self, constant: fast_nodes.Constant) -> ConstantValue:
        return constant.value

    @typing.override
    def visit_name(self, name: fast_nodes.Name) -> ConstantValue:
        raise NotImplementedError

    @typing.override
    def visit_attribute(self, attribute: fast_nodes.Attribute) -> ConstantValue:
        raise NotImplementedError

    @typing.override
    def visit_subscript(self, subscript: fast_nodes.Subscript) -> ConstantValue:
        raise NotImplementedError

    @typing.override
    def visit_bool_op(self, bool_op: fast_nodes.BoolOp) -> ConstantValue:
        raise NotImplementedError

    @typing.override
    def visit_bin_op(self, bin_op: fast_nodes.BinOp) -> ConstantValue:
        raise NotImplementedError

    @typing.override
    def visit_unary_op(self, unary_op: fast_nodes.UnaryOp) -> ConstantValue:
        value = unary_op.operand.accept(self)
        return fold_unary_expr(unary_op.source_location, type(unary_op.op), value)

    @typing.override
    def visit_if_exp(self, if_exp: fast_nodes.IfExp) -> ConstantValue:
        raise NotImplementedError

    @typing.override
    def visit_compare(self, compare: fast_nodes.Compare) -> ConstantValue:
        raise NotImplementedError

    @typing.override
    def visit_call(self, call: fast_nodes.Call) -> ConstantValue:
        match call.func:
            case fast_nodes.Attribute(base=fast_nodes.Constant(value=base), attr=func_name):
                args = [self._visit_call_arg(arg) for arg in call.args]
                kwargs = {name: self._visit_call_arg(arg) for name, arg in call.kwargs.items()}
                try:
                    func = getattr(base, func_name)
                    result = func(*args, **kwargs)
                except Exception as ex:
                    raise CodeError(str(ex), call.source_location) from ex
                else:
                    if not isinstance(result, ConstantValue):
                        raise CodeError("unsupported result type", call.source_location)
                    return result
        return self._unsupported(call)

    def _visit_call_arg(self, expr: fast_nodes.Expression) -> object:
        match expr:
            case fast_nodes.ListExpr(elements=items):
                return [item.accept(self) for item in items]
            case fast_nodes.TupleExpr(elements=items):
                return tuple(item.accept(self) for item in items)
            case _:
                return expr.accept(self)

    @typing.override
    def visit_formatted_value(self, formatted_value: fast_nodes.FormattedValue) -> str:
        value = formatted_value.value.accept(self)
        if formatted_value.conversion is None:
            conv_str = ""
        else:
            conv_str = "!" + formatted_value.conversion
        format_string = "{" + conv_str + ":{}}"
        if formatted_value.format_spec is not None:
            format_spec_exp = formatted_value.format_spec.accept(self)
        else:
            format_spec_exp = ""
        return format_string.format(value, format_spec_exp)

    @typing.override
    def visit_joined_str(self, joined_str: fast_nodes.JoinedStr) -> str:
        parts = [part.accept(self) for part in joined_str.values]
        if all(isinstance(x, str) for x in parts):
            return "".join(parts)  # type: ignore[arg-type]
        raise InternalError(
            "JoinedStr parts did not all evaluate to str", joined_str.source_location
        )

    @typing.override
    def visit_tuple_expr(self, tuple_expr: fast_nodes.TupleExpr) -> ConstantValue:
        return self._unsupported(tuple_expr)

    @typing.override
    def visit_list_expr(self, list_expr: fast_nodes.ListExpr) -> ConstantValue:
        return self._unsupported(list_expr)

    @typing.override
    def visit_dict_expr(self, dict_expr: fast_nodes.DictExpr) -> ConstantValue:
        return self._unsupported(dict_expr)

    @typing.override
    def visit_named_expr(self, named_expr: fast_nodes.NamedExpr) -> ConstantValue:
        return self._unsupported(named_expr)

    def _unsupported(
        self,
        node: fast_nodes.Expression,
        msg: str = "unsupported expression at module level",
        ex: Exception | None = None,
    ) -> typing.Never:
        raise CodeError(msg, node.source_location) from ex


def evaluate_compile_time_constant_condition(
    visitor: ExpressionVisitor[object], expr: fast_nodes.Expression
) -> StaticReachability:
    kind = reachability.infer_condition_value(expr)
    if kind != reachability.TRUTH_VALUE_UNKNOWN:
        return kind
    else:
        result = expr.accept(visitor)
        return reachability.ALWAYS_TRUE if result else reachability.ALWAYS_FALSE


UNARY_OPS: typing.Final[Mapping[type[ast.unaryop], Callable[[typing.Any], typing.Any]]] = {
    ast.Invert: operator.inv,
    ast.Not: operator.not_,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def fold_unary_expr(location: SourceLocation, op: type[ast.unaryop], expr: object) -> object:
    if not (func := UNARY_OPS.get(op)):
        raise InternalError(f"Unhandled unary operator: {op}", location)
    if op is ast.Invert and isinstance(expr, int):
        logger.warning(
            "due to Python ints being signed, bitwise inversion yield a negative number",
            location=location,
        )
    try:
        with log_warnings(location):
            result = func(expr)
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    return result
