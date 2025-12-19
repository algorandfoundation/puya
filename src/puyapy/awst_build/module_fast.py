import abc
import functools
import operator
import typing
from collections.abc import Callable, Iterator, Mapping, Set

from mypy.types import PROTOCOL_NAMES

from puya import log
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy._stub_symtables import STUB_SYMTABLES
from puyapy.awst_build import pytypes, symbols
from puyapy.awst_build.context import ASTConversionContext, ASTConversionModuleContext
from puyapy.awst_build.utils import log_warnings
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors import ExpressionVisitor, StatementVisitor

logger = log.get_logger(__name__)


StatementResult: typing.TypeAlias = list[symbols.CodeSymbol]


_BUILTIN_INHERITABLE: typing.Final = frozenset(("builtins.object", "abc.ABC", *PROTOCOL_NAMES))


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


class ModuleFASTConverter(_BaseModuleASTConverter[StatementResult]):
    def __init__(self, context: ASTConversionModuleContext, module: fast_nodes.Module):
        self.context: typing.Final = context
        self._imported_modules = set[str]()
        self._const_visitor = ModuleConstantExpressionVisitor(
            context, context.symbol_table, self._imported_modules
        )
        for builtin_name in ("tuple", "bool", "int", "str", "bytes", "dict", "list"):
            self.context.symbol_table[builtin_name] = symbols.StubReference(
                qualified_name="builtins.tuple", definition=None
            )
        for stmt in module.body:
            with self.context.log_exceptions(fallback_location=stmt.source_location):
                try:  # noqa: SIM105
                    stmt.accept(self)
                except NotImplementedError:
                    pass

    @typing.override
    def empty_statement(self, node: fast_nodes.Statement) -> StatementResult:
        return []

    @typing.override
    def visit_module_import(self, module_import: fast_nodes.ModuleImport) -> StatementResult:
        # ref: https://docs.python.org/3/reference/simple_stmts.html#the-import-statement
        if module_import.type_checking_only:
            # raise NotImplementedError("TODO: support TYPE_CHECKING imports")
            return []
        for imp in module_import.names:
            self._imported_modules.update(_expand_all_imports(imp.name))
            if imp.as_name is None:
                # examples:
                # import foo
                #   -> foo imported and bound locally
                # import foo.bar.baz
                #   -> foo, foo.bar, and foo.bar.baz imported, foo bound locally
                root = imp.name.partition(".")[0]
                local_name = root
                qualified_name = root
            else:
                # example:
                # import foo.bar.baz as fbb
                #   -> foo, foo.bar, and foo.bar.baz imported, foo.bar.baz bound as fbb
                local_name = imp.as_name
                qualified_name = imp.name
            # an import <module> statement can only ever import a module
            sym = symbols.ImportedModule(
                qualified_name=qualified_name,
                definition=module_import,
            )
            try:
                existing_defn = self.context.symbol_table[local_name]
            except KeyError:
                self.context.symbol_table[local_name] = sym
            else:
                if not (
                    isinstance(existing_defn, symbols.ImportedModule)
                    and existing_defn.qualified_name == qualified_name
                ):
                    self._unsupported(imp, "import would shadow existing definition")
        return []

    @typing.override
    def visit_from_import(self, from_import: fast_nodes.FromImport) -> StatementResult:
        # ref: https://docs.python.org/3/reference/simple_stmts.html#the-import-statement
        # also: https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
        if from_import.type_checking_only:
            # raise NotImplementedError("TODO: support TYPE_CHECKING from-imports")
            return []

        self._imported_modules.update(_expand_all_imports(from_import.module))
        if from_import.module in STUB_SYMTABLES:
            stub_syms = STUB_SYMTABLES[from_import.module]
            if from_import.names is not None:
                for alias in from_import.names:
                    stub_data = stub_syms.get(alias.name)
                    if stub_data is None:
                        raise CodeError("unresolved stub import", alias.source_location)
                    if stub_data.fullname in STUB_SYMTABLES:
                        sym: symbols.Symbol = symbols.ImportedModule(
                            qualified_name=stub_data.fullname, definition=from_import
                        )
                        self._imported_modules.add(stub_data.fullname)
                    else:
                        sym = symbols.StubReference(
                            qualified_name=stub_data.fullname,
                            definition=from_import,
                        )
                    # TODO: prevent re-def
                    self.context.symbol_table[alias.as_name or alias.name] = sym
            else:
                # TODO: rebind previously imported modules
                for sym_name, stub_data in stub_syms.items():
                    if stub_data.module_public:
                        if stub_data.fullname in STUB_SYMTABLES:
                            sym = symbols.ImportedModule(
                                qualified_name=stub_data.fullname, definition=from_import
                            )
                            self._imported_modules.add(stub_data.fullname)
                        else:
                            sym = symbols.StubReference(
                                qualified_name=stub_data.fullname,
                                definition=from_import,
                            )
                        # TODO: prevent re-def
                        self.context.symbol_table[sym_name] = sym
        else:
            mod_data = self.context.modules.get(from_import.module)
            if mod_data is None:
                raise NotImplementedError("TODO: support implict NS imports")
            if from_import.names is not None:
                for alias in from_import.names:
                    sym = self._resolve_from_import(
                        mod_data.fast, from_import, alias.name, alias.source_location
                    )
                    # TODO: prevent re-def
                    self.context.symbol_table[alias.as_name or alias.name] = sym
            else:
                assert mod_data.fast.path != self.context.module_path, "import * from self"
                if mod_data.fast.dunder_all is not None:
                    import_names = mod_data.fast.dunder_all
                else:
                    import_names = tuple(
                        name
                        for name in self.context.symbol_tables[from_import.module]
                        if name[0] != "_"
                    )
                # TODO: rebind previously imported modules
                for sym_name in import_names:
                    sym = self._resolve_from_import(
                        mod_data.fast, from_import, sym_name, from_import.source_location
                    )
                    # TODO: prevent re-def
                    self.context.symbol_table[sym_name] = sym
        return []

    def _handle_module_import(self, module_id: str) -> None:
        self._imported_modules.update(_expand_all_imports(module_id))
        # self.context.modules[module_id].dependencies
        raise NotImplementedError

    def _resolve_from_import(
        self,
        mod_fast: fast_nodes.Module,
        from_import: fast_nodes.FromImport,
        symbol_name: str,
        loc: SourceLocation,
    ) -> symbols.Symbol:
        qualified_name = ".".join((from_import.module, symbol_name))
        if mod_fast.path != self.context.module_path:
            mod_syms = self.context.symbol_tables[from_import.module]
            try:
                return mod_syms[symbol_name]
            except KeyError:
                pass
            if (
                symbol_name in mod_fast.symbols.get_identifiers()
                and qualified_name in self.context.modules
            ):
                raise CodeError(f"attempted to import {qualified_name}", loc)
            self._imported_modules.add(qualified_name)
        return symbols.ImportedModule(
            qualified_name=qualified_name,
            definition=from_import,
        )

    @typing.override
    def visit_function_def(self, func_def: fast_nodes.FunctionDef) -> StatementResult:
        self.context.symbol_table[func_def.name] = symbols.Subroutine(
            qualified_name="", definition=func_def
        )
        raise NotImplementedError

    @typing.override
    def visit_class_def(self, class_def: fast_nodes.ClassDef) -> StatementResult:
        self.context.symbol_table[class_def.name] = symbols.DeferredDataClass(definition=class_def)
        raise NotImplementedError

    @typing.override
    def visit_assign(self, assign: fast_nodes.Assign) -> StatementResult:
        match assign.target:
            case fast_nodes.Name(id=target):
                pass
            case unsupported:
                raise CodeError(
                    "only straight-forward assignment targets supported at module level",
                    unsupported.source_location,
                )
        match assign.value:
            case fast_nodes.Name(id=source) if (
                source_sym := self.context.symbol_table.get(source)
            ) and not isinstance(source_sym, symbols.Const):
                self.context.symbol_table[target] = symbols.DeferredTypeAlias(definition=assign)
                return []
        try:
            value = self._visit_const_expr(assign.value)
        except SymbolIsNotAConstantError:
            # TODO: !!!
            self.context.symbol_table[target] = symbols.DeferredTypeAlias(definition=assign)
        else:
            self.context.symbol_table[target] = symbols.Const(
                qualified_name=".".join((self.context.module_name, target)),
                definition=assign,
                value=value,
            )
        # match assign.annotation:
        #     case None:
        #         # if no annotation, then for our purposes, implicit type-alias detection is simple,
        #         # we can check for Attribute, Name, or a Subscript thereof, and if the reference
        #         # resolves to a type (which will be available as a predecessor, and can't be
        #         # quoted (at least not the root reference expression) without an explicit TypeAlias
        #         # annotation), then it must be a type alias, otherwise it must be a constant
        #         # expression
        #         pass
        #     case fast_nodes.Constant(value=str()):
        #         raise CodeError(
        #             "quoted type-annotations are not supported on module level assignments",
        #             assign.source_location,
        #         )
        #     case fast_nodes.Attribute(base=fast_nodes.Name(id=module), attr="TypeAlias") if (
        #         isinstance(
        #             module_sym := self.context.symbol_table.get(module), symbols.ImportedModule
        #         )
        #     ) and module_sym.qualified_name in ("typing", "typing_extensions"):
        #         match assign.value:
        #             case fast_nodes.Constant(value=str()):
        #                 self.context.symbol_table[target] = symbols.DeferredTypeAlias(
        #                     definition=assign
        #                 )
        #             case fast_nodes.Subscript():
        #                 pass
        # # TODO!!!
        # self.context.symbol_table[target] = symbols.DeferredTypeAlias(definition=assign)
        return []

    @typing.override
    def visit_multi_assign(self, multi_assign: fast_nodes.MultiAssign) -> StatementResult:
        # multi-assignments cannot be annotated, and cannot be implicit type-aliases (can't
        # find a spec for the latter other than it's mypy's behaviour)
        # therefore they must be simple constant expressions
        value = self._visit_const_expr(multi_assign.value)
        for lvalue in multi_assign.targets:
            match lvalue:
                case fast_nodes.Name(id=target):
                    pass
                case unsupported:
                    raise CodeError(
                        "only straight-forward assignment targets supported at module level",
                        unsupported.source_location,
                    )
            self.context.symbol_table[target] = symbols.Const(
                qualified_name=".".join((self.context.module_name, target)),
                definition=multi_assign,
                value=value,
            )
        return []

    @typing.override
    def visit_aug_assign(self, aug_assign: fast_nodes.AugAssign) -> typing.Never:
        # we do support this for __all__ but those are stripped during FAST build
        # TODO: message might be confusing as per the above comment
        self._unsupported(aug_assign)

    @typing.override
    def visit_if(self, if_stmt: fast_nodes.If) -> StatementResult:
        condition = self._visit_const_expr(if_stmt.test)
        if condition:
            branch = if_stmt.body
        else:
            branch = if_stmt.else_body or ()
        result = StatementResult()
        for stmt in branch:
            result.extend(stmt.accept(self))
        return result

    def _visit_const_expr(self, expr: fast_nodes.Expression) -> fast_nodes.ConstantValue:
        result = expr.accept(self._const_visitor)
        if not isinstance(result, fast_nodes.ConstantValue):
            raise CodeError("unsupported result type", expr.source_location)
        return result


def _expand_all_imports(module_id: str) -> Iterator[str]:
    while module_id:
        yield module_id
        module_id = module_id.rpartition(".")[0]


class _AnnotationNotReadyError(Exception):
    pass


class AnnotationEvaluator(ExpressionVisitor[pytypes.PyType]):
    @typing.override
    def visit_constant(self, constant: fast_nodes.Constant) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_name(self, name: fast_nodes.Name) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_attribute(self, attribute: fast_nodes.Attribute) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_subscript(self, subscript: fast_nodes.Subscript) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_bool_op(self, bool_op: fast_nodes.BoolOp) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_named_expr(self, named_expr: fast_nodes.NamedExpr) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_bin_op(self, bin_op: fast_nodes.BinOp) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_unary_op(self, unary_op: fast_nodes.UnaryOp) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_if_exp(self, if_exp: fast_nodes.IfExp) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_compare(self, compare: fast_nodes.Compare) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_call(self, call: fast_nodes.Call) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_formatted_value(self, formatted_value: fast_nodes.FormattedValue) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_joined_str(self, joined_str: fast_nodes.JoinedStr) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_tuple_expr(self, tuple_expr: fast_nodes.TupleExpr) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_list_expr(self, list_expr: fast_nodes.ListExpr) -> pytypes.PyType:
        raise NotImplementedError

    @typing.override
    def visit_dict_expr(self, dict_expr: fast_nodes.DictExpr) -> pytypes.PyType:
        raise CodeError("")


class SymbolIsNotAConstantError(CodeError):
    pass


class ModuleConstantExpressionVisitor(ExpressionVisitor[object]):
    def __init__(
        self,
        ctx: ASTConversionContext,
        symbol_table: Mapping[str, symbols.Symbol],
        imported_modules: Set[str],
    ):
        self.ctx: typing.Final = ctx
        self.symbols: typing.Final = symbol_table
        self.imported_modules: typing.Final = imported_modules

    @typing.override
    def visit_constant(self, constant: fast_nodes.Constant) -> fast_nodes.ConstantValue:
        return constant.value

    @typing.override
    def visit_name(self, name: fast_nodes.Name) -> fast_nodes.ConstantValue:
        try:
            sym = self.symbols[name.id]
        except KeyError:
            raise CodeError("unable to resolve symbol", name.source_location) from None
        if not isinstance(sym, symbols.Const):
            raise SymbolIsNotAConstantError("expected a module constant", name.source_location)
        return sym.value

    @typing.override
    def visit_attribute(self, attribute: fast_nodes.Attribute) -> fast_nodes.ConstantValue:
        submodules = list[str]()
        base = attribute.base
        while isinstance(base, fast_nodes.Attribute):
            submodules.append(base.attr)
            base = base.base
        if not isinstance(base, fast_nodes.Name):
            raise CodeError("unsupported expression syntax at this location", base.source_location)
        try:
            mod_sym = self.symbols[base.id]
        except KeyError:
            raise CodeError("unable to resolve module", base.source_location) from None
        if not isinstance(mod_sym, symbols.ImportedModule):
            raise CodeError("expected a module reference", base.source_location)
        module_fullname = ".".join((mod_sym.qualified_name, *reversed(submodules)))
        if module_fullname not in self.imported_modules:
            raise CodeError(
                f"module {module_fullname} has not been imported", attribute.base.source_location
            )
        module_symtable = self.ctx.symbol_tables[module_fullname]
        try:
            var_sym = module_symtable[attribute.attr]
        except KeyError:
            raise CodeError("unable to resolve attribute", attribute.source_location) from None
        if not isinstance(var_sym, symbols.Const):
            raise SymbolIsNotAConstantError(
                "expected a module constant", attribute.source_location
            )
        return var_sym.value

    @typing.override
    def visit_subscript(self, subscript: fast_nodes.Subscript) -> object:
        base = subscript.base.accept(self)
        indexes = list[object]()
        for index_expr in subscript.indexes:
            if not isinstance(index_expr, fast_nodes.Slice):
                index = index_expr.accept(self)
            else:
                lower = self._visit_optional(index_expr.lower)
                upper = self._visit_optional(index_expr.upper)
                step = self._visit_optional(index_expr.step)
                index = slice(lower, upper, step)
            indexes.append(index)
        try:
            (indexer,) = indexes
        except ValueError:
            indexer = tuple(indexes)
        try:
            return base[indexer]  # type: ignore[index]
        except Exception as ex:
            raise CodeError(str(ex), subscript.source_location) from ex

    def _visit_optional(self, expr: fast_nodes.Expression | None) -> object:
        if expr is None:
            return None
        return expr.accept(self)

    @typing.override
    def visit_bool_op(self, bool_op: fast_nodes.BoolOp) -> object:
        values = [operand.accept(self) for operand in bool_op.values]
        func: Callable[[object, object], object]
        match bool_op.op:
            case "and":
                func = lambda a, b: a and b  # noqa: E731
            case "or":
                func = lambda a, b: a or b  # noqa: E731
            case _:
                raise CodeError("unsupported boolean operator", bool_op.source_location)
        result = functools.reduce(func, values)
        return result

    @typing.override
    def visit_bin_op(self, bin_op: fast_nodes.BinOp) -> object:
        left = bin_op.left.accept(self)
        right = bin_op.right.accept(self)
        result = fold_binary_expr(bin_op.source_location, bin_op.op, left, right)
        return result

    @typing.override
    def visit_unary_op(self, unary_op: fast_nodes.UnaryOp) -> object:
        value = unary_op.operand.accept(self)
        result = fold_unary_expr(unary_op.source_location, unary_op.op, value)
        return result

    @typing.override
    def visit_if_exp(self, if_exp: fast_nodes.IfExp) -> object:
        condition = if_exp.test.accept(self)
        if condition:
            branch = if_exp.true
        else:
            branch = if_exp.false
        return branch.accept(self)

    @typing.override
    def visit_compare(self, compare: fast_nodes.Compare) -> object:
        result = compare.left.accept(self)
        for op, operand in zip(compare.ops, compare.comparators, strict=True):
            left = result
            right = operand.accept(self)
            result = fold_cmp_expr(compare.source_location, op, left, right)
            if not result:
                break
        return result

    @typing.override
    def visit_call(self, call: fast_nodes.Call) -> object:
        match call.func:
            case fast_nodes.Attribute(base=base_expr, attr=func_name):
                base = base_expr.accept(self)
                args = [arg.accept(self) for arg in call.args]
                kwargs = {name: arg.accept(self) for name, arg in call.kwargs.items()}
                try:
                    func = getattr(base, func_name)
                    result = func(*args, **kwargs)
                except Exception as ex:
                    raise CodeError(str(ex), call.source_location) from ex
                else:
                    return result
        return self._unsupported(call)

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
    def visit_tuple_expr(self, tuple_expr: fast_nodes.TupleExpr) -> tuple[object, ...]:
        return tuple(el.accept(self) for el in tuple_expr.elements)

    @typing.override
    def visit_list_expr(self, list_expr: fast_nodes.ListExpr) -> tuple[object, ...]:
        logger.warning(
            "only immutable data is supported at the module level, treating list as tuple",
            location=list_expr.source_location,
        )
        return tuple(el.accept(self) for el in list_expr.elements)

    @typing.override
    def visit_dict_expr(self, dict_expr: fast_nodes.DictExpr) -> typing.Never:
        self._unsupported(dict_expr)
        # result = dict[object, object]()
        # for k, v in dict_expr.pairs:
        #     value = v.accept(self)
        #     if k is not None:
        #         result[k.accept(self)] = value
        #     else:
        #         try:
        #             result.update(value)  # type: ignore[call-overload]
        #         except Exception as ex:
        #             raise CodeError(str(ex), v.source_location) from ex
        # return result

    @typing.override
    def visit_named_expr(self, named_expr: fast_nodes.NamedExpr) -> typing.Never:
        self._unsupported(named_expr)

    def _unsupported(
        self,
        node: fast_nodes.Expression,
        msg: str = "unsupported expression at module level",
        ex: Exception | None = None,
    ) -> typing.Never:
        raise CodeError(msg, node.source_location) from ex


UNARY_OPS: typing.Final[Mapping[fast_nodes.UnaryOperator, Callable[[typing.Any], typing.Any]]] = {
    "~": operator.inv,
    "not": operator.not_,
    "+": operator.pos,
    "-": operator.neg,
}


def fold_unary_expr(
    location: SourceLocation, op: fast_nodes.UnaryOperator, expr: object
) -> object:
    if not (func := UNARY_OPS.get(op)):
        raise InternalError(f"unhandled unary operator: {op}", location)
    if op == "~" and isinstance(expr, int):
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


BINARY_OPS: typing.Final[
    Mapping[fast_nodes.BinaryOperator, Callable[[typing.Any, typing.Any], typing.Any]]
] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "@": operator.matmul,
    "/": operator.truediv,
    "%": operator.mod,
    "**": operator.pow,
    "<<": operator.lshift,
    ">>": operator.rshift,
    "|": operator.or_,
    "^": operator.xor,
    "&": operator.and_,
    "//": operator.floordiv,
}


def fold_binary_expr(
    location: SourceLocation,
    op: fast_nodes.BinaryOperator,
    lhs: object,
    rhs: object,
) -> object:
    if not (func := BINARY_OPS.get(op)):
        raise InternalError(f"unhandled binary operator: {op}", location)
    try:
        with log_warnings(location):
            result = func(lhs, rhs)
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    return result


COMPARISON_OPS: typing.Final[
    Mapping[fast_nodes.ComparisonOperator, Callable[[typing.Any, typing.Any], bool]]
] = {
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    "!=": operator.ne,
    "is": operator.is_,
    "is not": operator.is_not,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
    # "and": lambda a, b: a and b,
    # "or": lambda a, b: a or b,
}


def fold_cmp_expr(
    location: SourceLocation,
    op: fast_nodes.ComparisonOperator,
    lhs: object,
    rhs: object,
) -> object:
    if not (func := COMPARISON_OPS.get(op)):
        raise InternalError(f"unhandled binary operator: {op}", location)
    try:
        with log_warnings(location):
            result = func(lhs, rhs)
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    return result
