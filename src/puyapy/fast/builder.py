import ast
import contextlib
import symtable
import typing
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import log
from puya.errors import CodeError, InternalError, log_exceptions
from puya.parse import SourceLocation
from puya.utils import coalesce, set_add
from puyapy.fast import nodes

logger = log.get_logger(__name__)


_UNSUPPORTED_SYNTAX_MSG = "unsupported Python syntax"
_INVALID_SYNTAX_MSG = "invalid Python syntax"
_NO_TYPE_COMMENTS_MSG = "type comments are not supported"
_NO_TYPE_PARAMS_MSG = "type parameters are not supported"

_TYPING_MODULE_NAMES: typing.Final = ("typing", "typing_extensions")


def parse_module(
    *,
    source: str,
    module_path: Path,
    module_name: str,
    feature_version: int | tuple[int, int] | None = None,
) -> nodes.Module | None:
    try:
        mod = ast.parse(
            source, module_path, "exec", type_comments=True, feature_version=feature_version
        )
        symbols = symtable.symtable(source, str(module_path), "exec")
    except SyntaxError as e:
        loc = None
        if e.lineno is not None:
            loc = SourceLocation(
                file=module_path,
                line=e.lineno,
                end_line=coalesce(e.end_lineno, e.lineno),
                column=e.offset,
                end_column=e.end_offset,
            )
        logger.error(f"{_INVALID_SYNTAX_MSG}: {e.msg}", location=loc)  # noqa: TRY400
        fast = None
    except Exception:
        logger.exception(f"unable to parse {module_path}")
        fast = None
    else:
        fast = _convert_module(mod, symbols, module_path=module_path, module_name=module_name)
    return fast


_ASTNodeWithLocation = ast.expr | ast.stmt | ast.pattern | ast.alias | ast.arg | ast.keyword

_NestedScopeKind = typing.Literal["class", "func"]
_ScopeKind = typing.Literal[_NestedScopeKind, "module"]


@attrs.define
class _Scope:
    kind: _ScopeKind = attrs.field(on_setattr=attrs.setters.frozen)
    name: str = attrs.field(on_setattr=attrs.setters.frozen)
    imported_typing_modules: set[str] = attrs.field(on_setattr=attrs.setters.frozen)
    is_type_checking_imported: bool


@attrs.define
class _BuildContext:
    module_name: str = attrs.field(on_setattr=attrs.setters.frozen)
    module_path: Path = attrs.field(on_setattr=attrs.setters.frozen)
    _scope_stack: list[_Scope] = attrs.field(init=False, on_setattr=attrs.setters.frozen)
    _failures: int = attrs.field(default=0, init=False)

    @_scope_stack.default
    def _initial_scope_stack(self) -> list[_Scope]:
        return [
            _Scope(
                kind="module",
                name=self.module_name,
                imported_typing_modules=set(),
                is_type_checking_imported=False,
            )
        ]

    @property
    def failures(self) -> int:
        return self._failures

    def invalid_syntax(
        self, loc: SourceLocation | _ASTNodeWithLocation | None, detail: str | None = None
    ) -> None:
        if detail is None:
            message = _INVALID_SYNTAX_MSG
        else:
            message = f"{_INVALID_SYNTAX_MSG}: {detail}"
        self.fail(message, loc)

    def unsupported_syntax(
        self, loc: SourceLocation | _ASTNodeWithLocation | None, detail: str | None = None
    ) -> None:
        if detail is None:
            message = _UNSUPPORTED_SYNTAX_MSG
        else:
            message = f"{_UNSUPPORTED_SYNTAX_MSG}: {detail}"
        self.fail(message, loc)

    def fail(self, message: str, loc: SourceLocation | _ASTNodeWithLocation | None) -> None:
        if not isinstance(loc, SourceLocation | None):
            loc = self.loc(loc)
        logger.error(message, location=loc)
        self._failures += 1

    def loc(self, node: _ASTNodeWithLocation) -> SourceLocation:
        return SourceLocation(
            file=self.module_path,
            line=node.lineno,
            end_line=node.end_lineno if node.end_lineno is not None else node.lineno,
            column=node.col_offset,
            end_column=node.end_col_offset,
        )

    @property
    def scope(self) -> _Scope:
        return self._scope_stack[-1]

    @contextlib.contextmanager
    def enter_scope(self, kind: _NestedScopeKind, name: str) -> Iterator[None]:
        current = self.scope
        nested_scope = _Scope(
            kind=kind,
            name=f"{current.name}.{name}",
            imported_typing_modules=current.imported_typing_modules.copy(),
            is_type_checking_imported=current.is_type_checking_imported,
        )
        self._scope_stack.append(nested_scope)
        try:
            yield
        finally:
            self._scope_stack.pop()


def _convert_module(
    module: ast.Module,
    symbols: symtable.SymbolTable,
    *,
    module_path: Path,
    module_name: str,
) -> nodes.Module | None:
    ctx = _BuildContext(module_name=module_name, module_path=module_path)
    ast_body, docstring = _extract_docstring(module)
    body = list[nodes.Statement]()
    for ast_stmt in ast_body:
        if isinstance(ast_stmt, ast.If) and _is_type_checking(ctx, ast_stmt.test):
            if ast_stmt.orelse:
                ctx.fail(
                    "no code is allowed inside the else branch of an if TYPE_CHECKING block",
                    ast_stmt.orelse[0],
                )
            body.extend(_convert_type_checking_block(ctx, ast_stmt.body))
        else:
            stmt = _visit_stmt(ctx, ast_stmt)
            if stmt is not None:
                body.append(stmt)
    if ctx.failures:
        return None
    return nodes.Module(
        name=module_name,
        path=module_path,
        docstring=docstring,
        body=tuple(body),
        symbols=symbols,
    )


def _is_type_checking(ctx: _BuildContext, test: ast.expr) -> bool:
    if ctx.scope.is_type_checking_imported and isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return (
            test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and test.value.id in ctx.scope.imported_typing_modules
        )
    return False


def _convert_type_checking_block(
    ctx: _BuildContext, body: list[ast.stmt]
) -> list[nodes.Statement]:
    result = list[nodes.Statement]()
    for stmt in body:
        match stmt:
            case ast.Import():
                result.append(_convert_import(ctx, stmt, type_checking_only=True))
            case ast.ImportFrom():
                result.append(_convert_import_from(ctx, stmt, type_checking_only=True))
            case _:
                ctx.fail(
                    "only import and from-import statements"
                    " are supported inside a TYPE_CHECKING block",
                    stmt,
                )
    return result


def _extract_docstring(
    node: ast.Module | ast.ClassDef | ast.FunctionDef,
) -> tuple[list[ast.stmt], str | None]:
    docstring = ast.get_docstring(node, clean=False)
    body = node.body
    if docstring is not None:
        body = node.body[1:]
    return body, docstring


def _visit_stmt_list(ctx: _BuildContext, stmts: list[ast.stmt]) -> tuple[nodes.Statement, ...]:
    result = []
    for ast_stmt in stmts:
        stmt = _visit_stmt(ctx, ast_stmt)
        if stmt is not None:
            result.append(stmt)
    return tuple(result)


def _visit_stmt(ctx: _BuildContext, node: ast.stmt) -> nodes.Statement | None:
    node_type = type(node)
    try:
        handler = _STATEMENT_HANDLERS[node_type]
    except KeyError:
        logger.debug(f"unknown statement node type: {node_type.__name__}")
        handler = _unsupported_stmt
    loc = ctx.loc(node)
    result = None
    with log_exceptions(loc):
        result = handler(ctx, node)
    return result


def _visit_function_def(ctx: _BuildContext, func_def: ast.FunctionDef) -> nodes.FunctionDef:
    loc = ctx.loc(func_def)
    if func_def.type_comment is not None:
        ctx.fail(_NO_TYPE_COMMENTS_MSG, loc)
    type_params = getattr(func_def, "type_params", None)
    if type_params:
        ctx.fail(_NO_TYPE_PARAMS_MSG, loc)
    decorators = _convert_decorator_list(ctx, func_def.decorator_list)
    params = _convert_arguments(ctx, func_def.args)
    return_annotation = None
    if func_def.returns is not None:
        return_annotation = _visit_expr(ctx, func_def.returns)
    ast_body, docstring = _extract_docstring(func_def)
    with ctx.enter_scope("func", func_def.name):
        body = _visit_stmt_list(ctx, ast_body)
    return nodes.FunctionDef(
        decorators=decorators,
        name=func_def.name,
        params=params,
        return_annotation=return_annotation,
        docstring=docstring,
        body=body,
        source_location=loc,
    )


def _convert_decorator_list(
    ctx: _BuildContext, decorator_list: list[ast.expr]
) -> tuple[nodes.Decorator, ...]:
    result = []
    for decorator in decorator_list:
        callee: ast.expr
        args: tuple[nodes.Expression, ...] | None
        kwargs: immutabledict[str, nodes.Expression] | None
        match decorator:
            case ast.Call(func=callee, args=args_list, keywords=keywords):
                args = _visit_expr_list(ctx, args_list)
                kwargs = _visit_keywords_list(ctx, keywords)
            case callee:
                args = None
                kwargs = None
        loc = ctx.loc(decorator)
        callee_name = _extract_dotted_name(ctx, callee)
        if callee_name is None:
            # see comments on nodes.Decorator for more context
            ctx.unsupported_syntax(
                loc, "only direct function references are supported as decorators"
            )
        else:
            result.append(
                nodes.Decorator(
                    callee=callee_name,
                    args=args,
                    kwargs=kwargs,
                    source_location=loc,
                )
            )
    return tuple(result)


def _convert_arguments(ctx: _BuildContext, args: ast.arguments) -> tuple[nodes.Parameter, ...]:
    params = []
    args_args = args.posonlyargs + args.args
    num_no_defaults = len(args_args) - len(args.defaults)
    defaults = ([None] * num_no_defaults) + args.defaults

    for i, (a, d) in enumerate(zip(args_args, defaults, strict=True)):
        if i < len(args.posonlyargs):
            pass_by = nodes.PassBy.POSITION
        else:
            pass_by = nodes.PassBy.POSITION | nodes.PassBy.NAME
        params.append(_make_parameter(ctx, a, d, pass_by))

    # *arg
    if args.vararg is not None:
        ctx.unsupported_syntax(
            args.vararg, "variadic arguments are not supported in user functions"
        )

    for a, kd in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        params.append(_make_parameter(ctx, a, kd, nodes.PassBy.NAME))

    # **kwarg
    if args.kwarg is not None:
        ctx.unsupported_syntax(
            args.kwarg, "variadic arguments are not supported in user functions"
        )

    seen_names = set[str]()
    for param in params:
        if not set_add(seen_names, param.name):
            ctx.invalid_syntax(
                param.source_location,
                f"duplicate argument {param.name!r} in function definition",
            )

    return tuple(params)


def _make_parameter(
    ctx: _BuildContext, arg: ast.arg, default: ast.expr | None, pass_by: nodes.PassBy
) -> nodes.Parameter:
    name = arg.arg
    annotation = _visit_optional_expr(ctx, arg.annotation)
    default_value = _visit_optional_expr(ctx, default)
    loc = ctx.loc(arg)
    if arg.type_comment:
        ctx.fail(_NO_TYPE_COMMENTS_MSG, loc)
    return nodes.Parameter(
        name=name,
        annotation=annotation,
        default=default_value,
        pass_by=pass_by,
        source_location=loc,
    )


def _visit_class_def(ctx: _BuildContext, class_def: ast.ClassDef) -> nodes.ClassDef:
    loc = ctx.loc(class_def)
    type_params = getattr(class_def, "type_params", None)
    if type_params:
        ctx.fail(_NO_TYPE_PARAMS_MSG, loc)
    decorators = _convert_decorator_list(ctx, class_def.decorator_list)
    bases = _visit_expr_list(ctx, class_def.bases)
    kwargs = _visit_keywords_list(ctx, class_def.keywords)
    ast_body, docstring = _extract_docstring(class_def)
    with ctx.enter_scope("class", class_def.name):
        body = _visit_stmt_list(ctx, ast_body)
    return nodes.ClassDef(
        decorators=decorators,
        name=class_def.name,
        bases=bases,
        kwargs=kwargs,
        docstring=docstring,
        body=body,
        source_location=loc,
    )


def _visit_import(ctx: _BuildContext, node: ast.Import) -> nodes.ModuleImport:
    result = _convert_import(ctx, node, type_checking_only=False)
    for import_as in result.names:
        if import_as.name in _TYPING_MODULE_NAMES:
            ctx.scope.imported_typing_modules.add(import_as.as_name or import_as.name)
    return result


def _convert_import(
    ctx: _BuildContext, node: ast.Import, *, type_checking_only: bool
) -> nodes.ModuleImport:
    names = [_visit_alias(ctx, alias) for alias in node.names]
    loc = ctx.loc(node)
    return nodes.ModuleImport(
        names=names, type_checking_only=type_checking_only, source_location=loc
    )


def _visit_alias(ctx: _BuildContext, alias: ast.alias) -> nodes.ImportAs:
    loc = ctx.loc(alias)
    if alias.name == "*":
        raise InternalError("expected this to raise a SyntaxError", loc)
    return nodes.ImportAs(
        name=alias.name,
        as_name=alias.asname,
        source_location=loc,
    )


def _visit_import_from(ctx: _BuildContext, node: ast.ImportFrom) -> nodes.FromImport:
    result = _convert_import_from(ctx, node, type_checking_only=False)
    if result.module in _TYPING_MODULE_NAMES:
        if result.names is None:
            ctx.scope.is_type_checking_imported = True
        else:
            for as_name in result.names:
                if as_name.name == "TYPE_CHECKING":
                    if as_name.as_name in (None, "TYPE_CHECKING"):
                        ctx.scope.is_type_checking_imported = True
                    else:
                        ctx.fail(
                            "aliasing TYPE_CHECKING is not supported", as_name.source_location
                        )
    return result


def _convert_import_from(
    ctx: _BuildContext, node: ast.ImportFrom, *, type_checking_only: bool
) -> nodes.FromImport:
    match node.names:
        case [ast.alias("*", None) as star]:
            if ctx.scope.kind != "module":
                ctx.invalid_syntax(star, "import * only allowed at module level")
            names = None
        case _:
            names = [_visit_alias(ctx, alias) for alias in node.names]
    loc = ctx.loc(node)
    module_is_init = ctx.module_path.stem == "__init__"
    module = _correct_relative_import(
        ctx,
        node.level,
        current_module=ctx.module_name,
        target_module=node.module,
        module_is_init=module_is_init,
        import_loc=loc,
    )
    return nodes.FromImport(
        module=module,
        names=names,
        type_checking_only=type_checking_only,
        source_location=loc,
    )


def _correct_relative_import(
    ctx: _BuildContext,
    relative: int,
    *,
    current_module: str,
    target_module: str | None,
    module_is_init: bool,
    import_loc: SourceLocation,
) -> str:
    if not relative:
        if target_module is None:
            raise InternalError("non-relative from-import without identifier", import_loc)
        return target_module

    if module_is_init:
        relative -= 1
    parts = current_module.split(".")
    if len(parts) < relative:
        ctx.fail("attempted relative import with no known parent package", import_loc)
    if relative == 0:
        base = current_module
    else:
        base = ".".join(parts[:-relative])
    if target_module is None:
        absolute = base
    else:
        absolute = f"{base}.{target_module}"
    return absolute


def _visit_return(ctx: _BuildContext, ret: ast.Return) -> nodes.Return:
    if ret.value is None:
        value = None
    else:
        value = _visit_expr(ctx, ret.value)
    loc = ctx.loc(ret)
    return nodes.Return(value=value, source_location=loc)


def _visit_delete(ctx: _BuildContext, delete: ast.Delete) -> nodes.Delete:
    targets = _visit_expr_list(ctx, delete.targets)
    loc = ctx.loc(delete)
    return nodes.Delete(
        targets=tuple(targets),
        source_location=loc,
    )


def _visit_assign(ctx: _BuildContext, assign: ast.Assign) -> nodes.Assign | nodes.MultiAssign:
    loc = ctx.loc(assign)
    if assign.type_comment is not None:
        ctx.fail(_NO_TYPE_COMMENTS_MSG, loc)
    value = _visit_expr(ctx, assign.value)
    targets = _visit_expr_list(ctx, assign.targets)
    if len(targets) > 1:
        return nodes.MultiAssign(
            targets=tuple(targets),
            value=value,
            source_location=loc,
        )
    else:
        (target,) = targets
        return nodes.Assign(
            target=target,
            value=value,
            annotation=None,
            source_location=loc,
        )


def _visit_annotated_assign(
    ctx: _BuildContext, ann_assign: ast.AnnAssign
) -> nodes.AnnotationStatement | nodes.Assign:
    loc = ctx.loc(ann_assign)
    target: nodes.Name | nodes.Attribute | nodes.Subscript
    match ann_assign.target:
        case ast.Name() as name_expr:
            target = _visit_name(ctx, name_expr)
        case ast.Attribute() as attribute_expr:
            target = _visit_attribute(ctx, attribute_expr)
        case ast.Subscript() as subscript_expr:
            target = _visit_subscript(ctx, subscript_expr)
        case unexpected:
            typing.assert_never(unexpected)
    annotation = _visit_expr(ctx, ann_assign.annotation)
    if ann_assign.value is None:
        return nodes.AnnotationStatement(
            target=target,
            annotation=annotation,
            source_location=loc,
        )
    else:
        value = _visit_expr(ctx, ann_assign.value)
        return nodes.Assign(
            target=target,
            value=value,
            annotation=annotation,
            source_location=loc,
        )


def _visit_augmented_assign(ctx: _BuildContext, aug_assign: ast.AugAssign) -> nodes.AugAssign:
    loc = ctx.loc(aug_assign)
    target: nodes.Name | nodes.Attribute | nodes.Subscript
    match aug_assign.target:
        case ast.Name() as name_expr:
            target = _visit_name(ctx, name_expr)
        case ast.Attribute() as attribute_expr:
            target = _visit_attribute(ctx, attribute_expr)
        case ast.Subscript() as subscript_expr:
            target = _visit_subscript(ctx, subscript_expr)
        case unexpected:
            typing.assert_never(unexpected)
    value = _visit_expr(ctx, aug_assign.value)
    return nodes.AugAssign(
        target=target,
        op=aug_assign.op,
        value=value,
        source_location=loc,
    )


def _visit_for_loop(ctx: _BuildContext, for_stmt: ast.For) -> nodes.For:
    loc = ctx.loc(for_stmt)
    if for_stmt.type_comment is not None:
        ctx.fail(_NO_TYPE_COMMENTS_MSG, loc)
    target = _visit_expr(ctx, for_stmt.target)
    iterable = _visit_expr(ctx, for_stmt.iter)
    body = _visit_stmt_list(ctx, for_stmt.body)
    if not for_stmt.orelse:
        else_body = None
    else:
        else_body = _visit_stmt_list(ctx, for_stmt.orelse)
    return nodes.For(
        target=target,
        iterable=iterable,
        body=body,
        else_body=else_body,
        source_location=loc,
    )


def _visit_while_loop(ctx: _BuildContext, while_stmt: ast.While) -> nodes.While:
    loc = ctx.loc(while_stmt)
    test = _visit_expr(ctx, while_stmt.test)
    body = _visit_stmt_list(ctx, while_stmt.body)
    if not while_stmt.orelse:
        else_body = None
    else:
        else_body = _visit_stmt_list(ctx, while_stmt.orelse)
    return nodes.While(
        test=test,
        body=body,
        else_body=else_body,
        source_location=loc,
    )


def _visit_if(ctx: _BuildContext, if_stmt: ast.If) -> nodes.If:
    loc = ctx.loc(if_stmt)
    test = _visit_expr(ctx, if_stmt.test)
    body = _visit_stmt_list(ctx, if_stmt.body)
    if not if_stmt.orelse:
        else_body = None
    else:
        else_body = _visit_stmt_list(ctx, if_stmt.orelse)
    return nodes.If(
        test=test,
        body=body,
        else_body=else_body,
        source_location=loc,
    )


def _visit_assert(ctx: _BuildContext, assert_stmt: ast.Assert) -> nodes.Assert:
    loc = ctx.loc(assert_stmt)
    test = _visit_expr(ctx, assert_stmt.test)
    msg = _visit_optional_expr(ctx, assert_stmt.msg)
    return nodes.Assert(
        test=test,
        msg=msg,
        source_location=loc,
    )


def _visit_expression_statement(
    ctx: _BuildContext, expr_stmt: ast.Expr
) -> nodes.ExpressionStatement:
    loc = ctx.loc(expr_stmt)
    expr = _visit_expr(ctx, expr_stmt.value)
    return nodes.ExpressionStatement(
        expr=expr,
        source_location=loc,
    )


def _visit_pass(ctx: _BuildContext, pass_stmt: ast.Pass) -> nodes.Pass:
    loc = ctx.loc(pass_stmt)
    return nodes.Pass(
        source_location=loc,
    )


def _visit_break(ctx: _BuildContext, break_stmt: ast.Break) -> nodes.Break:
    loc = ctx.loc(break_stmt)
    return nodes.Break(
        source_location=loc,
    )


def _visit_continue(ctx: _BuildContext, continue_stmt: ast.Continue) -> nodes.Continue:
    loc = ctx.loc(continue_stmt)
    return nodes.Continue(
        source_location=loc,
    )


def _visit_keywords_list(
    ctx: _BuildContext, keywords: list[ast.keyword]
) -> immutabledict[str, nodes.Expression]:
    kwargs = {}
    for kw in keywords:
        if kw.arg is None:
            # if the arg names is None, it's a **kwargs unpacking
            ctx.unsupported_syntax(kw)
        elif kw.arg in kwargs:
            ctx.invalid_syntax(kw, f"keyword argument repeated: {kw.arg}")
        else:
            kwargs[kw.arg] = _visit_expr(ctx, kw.value)
    return immutabledict(kwargs)


def _extract_dotted_name(ctx: _BuildContext, expr: ast.expr) -> str | None:
    match expr:
        case ast.Name(id=name):
            return name
        case ast.Attribute(value=base, attr=name):
            base_name = _extract_dotted_name(ctx, base)
            if base_name is None:
                return None
            return f"{base_name}.{name}"
        case _:
            return None


def _visit_match(ctx: _BuildContext, match_stmt: ast.Match) -> nodes.Match:
    loc = ctx.loc(match_stmt)
    subject = _visit_expr(ctx, match_stmt.subject)
    cases = []
    for case in match_stmt.cases:
        pattern = _visit_match_pattern(ctx, case.pattern)
        guard = _visit_optional_expr(ctx, case.guard)
        body = _visit_stmt_list(ctx, case.body)
        cases.append(nodes.MatchCase(pattern=pattern, guard=guard, body=body))
    return nodes.Match(
        subject=subject,
        cases=tuple(cases),
        source_location=loc,
    )


def _visit_match_pattern(ctx: _BuildContext, pattern: ast.pattern) -> nodes.MatchPattern:
    loc = ctx.loc(pattern)
    match pattern:
        case ast.MatchValue(value=ast_value):
            value = _visit_expr(ctx, ast_value)
            return nodes.MatchValue(
                value=value,
                source_location=loc,
            )
        case ast.MatchSingleton(value=singleton):
            return nodes.MatchSingleton(
                value=singleton,
                source_location=loc,
            )
        case ast.MatchSequence(patterns=ast_patterns):
            patterns = [_visit_match_pattern(ctx, p) for p in ast_patterns]
            return nodes.MatchSequence(
                patterns=tuple(patterns),
                source_location=loc,
            )
        case ast.MatchStar(name=name):
            return nodes.MatchStar(
                name=name,
                source_location=loc,
            )
        case ast.MatchMapping(keys=ast_keys, patterns=ast_patterns, rest=rest):
            keys = [_visit_expr(ctx, k) for k in ast_keys]
            patterns = [_visit_match_pattern(ctx, p) for p in ast_patterns]
            return nodes.MatchMapping(
                kwd_patterns=immutabledict(zip(keys, patterns, strict=True)),
                rest=rest,
                source_location=loc,
            )
        case ast.MatchClass(
            cls=ast_cls, patterns=patterns, kwd_attrs=kwd_attrs, kwd_patterns=ast_kwd_patterns
        ):
            cls = _visit_expr(ctx, ast_cls)
            pos_patterns = [_visit_match_pattern(ctx, p) for p in patterns]
            kwd_patterns = [_visit_match_pattern(ctx, p) for p in ast_kwd_patterns]
            return nodes.MatchClass(
                cls=cls,
                patterns=tuple(pos_patterns),
                kwd_patterns=immutabledict(zip(kwd_attrs, kwd_patterns, strict=True)),
                source_location=loc,
            )
        case ast.MatchAs(pattern=maybe_ast_pattern, name=name):
            if maybe_ast_pattern is None:
                maybe_pattern = None
            else:
                maybe_pattern = _visit_match_pattern(ctx, maybe_ast_pattern)
            return nodes.MatchAs(
                pattern=maybe_pattern,
                name=name,
                source_location=loc,
            )
        case ast.MatchOr(patterns=ast_patterns):
            patterns = [_visit_match_pattern(ctx, p) for p in ast_patterns]
            return nodes.MatchOr(
                patterns=tuple(patterns),
                source_location=loc,
            )
        case _:
            raise CodeError(_UNSUPPORTED_SYNTAX_MSG, loc)


_TStatementVisitor = Callable[[_BuildContext, ast.stmt], nodes.Statement | None]


def _stmt_visitor_pair[TIn: ast.stmt, TOut: nodes.Statement](
    typ: type[TIn],
    func: Callable[[_BuildContext, TIn], TOut],
) -> tuple[type[ast.stmt], _TStatementVisitor]:
    # this cast should be safe, we have a pair of type and a func that takes that type,
    # and returns a specific type, and we're just casting to something more generic,
    # unfortunately there doesn't seem to be a way to express this as part of a mapping with
    # Python's type annotations
    visitor = typing.cast(_TStatementVisitor, func)
    return typ, visitor


def _unsupported_stmt(ctx: _BuildContext, stmt: ast.stmt) -> None:
    loc = ctx.loc(stmt)
    ctx.unsupported_syntax(loc)


_STATEMENT_HANDLERS: typing.Final[
    Mapping[type[ast.stmt], Callable[[_BuildContext, ast.stmt], nodes.Statement | None]]
] = dict(
    (
        # statements are listed here in the same order as the appear in:
        # https://docs.python.org/3/library/ast.html#abstract-grammar
        _stmt_visitor_pair(ast.FunctionDef, _visit_function_def),
        (ast.AsyncFunctionDef, _unsupported_stmt),
        _stmt_visitor_pair(ast.ClassDef, _visit_class_def),
        _stmt_visitor_pair(ast.Return, _visit_return),
        _stmt_visitor_pair(ast.Delete, _visit_delete),
        _stmt_visitor_pair(ast.Assign, _visit_assign),
        (ast.TypeAlias, _unsupported_stmt),
        _stmt_visitor_pair(ast.AugAssign, _visit_augmented_assign),
        _stmt_visitor_pair(ast.AnnAssign, _visit_annotated_assign),
        _stmt_visitor_pair(ast.For, _visit_for_loop),
        (ast.AsyncFor, _unsupported_stmt),
        _stmt_visitor_pair(ast.While, _visit_while_loop),
        _stmt_visitor_pair(ast.If, _visit_if),
        (ast.With, _unsupported_stmt),
        (ast.AsyncWith, _unsupported_stmt),
        _stmt_visitor_pair(ast.Match, _visit_match),
        (ast.Raise, _unsupported_stmt),
        (ast.Try, _unsupported_stmt),
        (ast.TryStar, _unsupported_stmt),
        _stmt_visitor_pair(ast.Assert, _visit_assert),
        _stmt_visitor_pair(ast.Import, _visit_import),
        _stmt_visitor_pair(ast.ImportFrom, _visit_import_from),
        (ast.Global, _unsupported_stmt),
        (ast.Nonlocal, _unsupported_stmt),
        _stmt_visitor_pair(ast.Expr, _visit_expression_statement),
        _stmt_visitor_pair(ast.Pass, _visit_pass),
        _stmt_visitor_pair(ast.Break, _visit_break),
        _stmt_visitor_pair(ast.Continue, _visit_continue),
    )
)


def _visit_expr_list(ctx: _BuildContext, exprs: list[ast.expr]) -> tuple[nodes.Expression, ...]:
    return tuple(_visit_expr(ctx, expr) for expr in exprs)


def _visit_expr(ctx: _BuildContext, node: ast.expr) -> nodes.Expression:
    node_type = type(node)
    try:
        handler = _EXPRESSION_HANDLERS[node_type]
    except KeyError:
        logger.debug(f"unknown expression node type: {node_type.__name__}")
        handler = _unsupported_expr_type
    return handler(ctx, node)


def _visit_optional_expr(ctx: _BuildContext, node: ast.expr | None) -> nodes.Expression | None:
    if node is None:
        return None
    return _visit_expr(ctx, node)


def _visit_constant(ctx: _BuildContext, constant: ast.Constant) -> nodes.Constant:
    loc = ctx.loc(constant)
    return nodes.Constant(
        value=constant.value,
        source_location=loc,
    )


def _visit_name(ctx: _BuildContext, name: ast.Name) -> nodes.Name:
    loc = ctx.loc(name)
    return nodes.Name(
        id=name.id,
        ctx=name.ctx,
        source_location=loc,
    )


def _visit_attribute(ctx: _BuildContext, attribute: ast.Attribute) -> nodes.Attribute:
    loc = ctx.loc(attribute)
    base = _visit_expr(ctx, attribute.value)
    return nodes.Attribute(
        base=base,
        attr=attribute.attr,
        ctx=attribute.ctx,
        source_location=loc,
    )


def _visit_subscript(ctx: _BuildContext, subscript: ast.Subscript) -> nodes.Subscript:
    loc = ctx.loc(subscript)
    base = _visit_expr(ctx, subscript.value)
    match subscript.slice:
        case ast.Tuple(elts=ast_indexes):
            pass
        case ast_index:
            ast_indexes = [ast_index]
    indexes = list[nodes.Expression | nodes.Slice]()
    for ast_index in ast_indexes:
        match ast_index:
            case ast.Slice():
                index_slice = _visit_slice(ctx, ast_index)
                indexes.append(index_slice)
            case _:
                index = _visit_expr(ctx, ast_index)
                indexes.append(index)
    return nodes.Subscript(
        base=base,
        indexes=tuple(indexes),
        ctx=subscript.ctx,
        source_location=loc,
    )


def _visit_slice(ctx: _BuildContext, slice_: ast.Slice) -> nodes.Slice:
    loc = ctx.loc(slice_)
    lower = _visit_optional_expr(ctx, slice_.lower)
    upper = _visit_optional_expr(ctx, slice_.upper)
    step = _visit_optional_expr(ctx, slice_.step)
    return nodes.Slice(
        lower=lower,
        upper=upper,
        step=step,
        source_location=loc,
    )


def _visit_bool_op(ctx: _BuildContext, bool_op: ast.BoolOp) -> nodes.BoolOp:
    loc = ctx.loc(bool_op)
    values = _visit_expr_list(ctx, bool_op.values)
    return nodes.BoolOp(
        op=bool_op.op,
        values=values,
        source_location=loc,
    )


def _visit_named_expr(ctx: _BuildContext, named_expr: ast.NamedExpr) -> nodes.NamedExpr:
    loc = ctx.loc(named_expr)
    target = _visit_name(ctx, named_expr.target)
    value = _visit_expr(ctx, named_expr.value)
    return nodes.NamedExpr(
        target=target,
        value=value,
        source_location=loc,
    )


def _visit_bin_op(ctx: _BuildContext, bin_op: ast.BinOp) -> nodes.BinOp:
    loc = ctx.loc(bin_op)
    left = _visit_expr(ctx, bin_op.left)
    right = _visit_expr(ctx, bin_op.right)
    return nodes.BinOp(
        left=left,
        op=bin_op.op,
        right=right,
        source_location=loc,
    )


def _visit_unary_op(ctx: _BuildContext, unary_op: ast.UnaryOp) -> nodes.UnaryOp:
    loc = ctx.loc(unary_op)
    operand = _visit_expr(ctx, unary_op.operand)
    return nodes.UnaryOp(
        op=unary_op.op,
        operand=operand,
        source_location=loc,
    )


def _visit_if_exp(ctx: _BuildContext, if_exp: ast.IfExp) -> nodes.IfExp:
    loc = ctx.loc(if_exp)
    test = _visit_expr(ctx, if_exp.test)
    true = _visit_expr(ctx, if_exp.body)
    false = _visit_expr(ctx, if_exp.orelse)
    return nodes.IfExp(
        test=test,
        true=true,
        false=false,
        source_location=loc,
    )


def _visit_compare(ctx: _BuildContext, compare: ast.Compare) -> nodes.Compare:
    loc = ctx.loc(compare)
    left = _visit_expr(ctx, compare.left)
    comparators = _visit_expr_list(ctx, compare.comparators)
    return nodes.Compare(
        left=left,
        ops=tuple(compare.ops),
        comparators=comparators,
        source_location=loc,
    )


def _visit_call(ctx: _BuildContext, call: ast.Call) -> nodes.Call:
    loc = ctx.loc(call)
    func = _visit_expr(ctx, call.func)
    args = _visit_expr_list(ctx, call.args)
    kwargs = _visit_keywords_list(ctx, call.keywords)
    return nodes.Call(
        func=func,
        args=args,
        kwargs=kwargs,
        source_location=loc,
    )


def _visit_formatted_value(
    ctx: _BuildContext, formatted_value: ast.FormattedValue
) -> nodes.FormattedValue:
    loc = ctx.loc(formatted_value)
    value = _visit_expr(ctx, formatted_value.value)
    match formatted_value.format_spec:
        case None:
            format_spec = None
        case ast.JoinedStr() as js:
            format_spec = _visit_joined_str(ctx, js)
        case node:
            raise InternalError(
                f"unexpected node {type(node).__name__} in FormattedValue.format_spec",
                ctx.loc(node),
            )
    conversion: typing.Literal["s", "r", "a"] | None
    match formatted_value.conversion:
        case -1:
            conversion = None
        case 115:
            conversion = "s"
        case 114:
            conversion = "r"
        case 97:
            conversion = "a"
        case unexpected:
            raise InternalError(f"unexpected conversion value: {unexpected}", loc)
    return nodes.FormattedValue(
        value=value,
        conversion=conversion,
        format_spec=format_spec,
        source_location=loc,
    )


def _visit_joined_str(ctx: _BuildContext, joined_str: ast.JoinedStr) -> nodes.JoinedStr:
    loc = ctx.loc(joined_str)
    values = list[nodes.Constant | nodes.FormattedValue]()
    for part in joined_str.values:
        match part:
            case ast.Constant():
                values.append(_visit_constant(ctx, part))
            case ast.FormattedValue():
                values.append(_visit_formatted_value(ctx, part))
            case _:
                raise InternalError(
                    f"unexpected node {type(part).__name__} in JoinedStr", ctx.loc(part)
                )
    return nodes.JoinedStr(
        values=tuple(values),
        source_location=loc,
    )


def _visit_dict_expr(ctx: _BuildContext, dict_expr: ast.Dict) -> nodes.DictExpr:
    loc = ctx.loc(dict_expr)
    keys = tuple(_visit_optional_expr(ctx, k) for k in dict_expr.keys)
    values = _visit_expr_list(ctx, dict_expr.values)
    pairs = tuple(zip(keys, values, strict=True))
    return nodes.DictExpr(
        pairs=pairs,
        source_location=loc,
    )


def _visit_list(ctx: _BuildContext, ast_list: ast.List) -> nodes.ListExpr:
    loc = ctx.loc(ast_list)
    elements = _visit_expr_list(ctx, ast_list.elts)
    return nodes.ListExpr(
        elements=elements,
        ctx=ast_list.ctx,
        source_location=loc,
    )


def _visit_tuple(ctx: _BuildContext, ast_tuple: ast.Tuple) -> nodes.TupleExpr:
    loc = ctx.loc(ast_tuple)
    elements = _visit_expr_list(ctx, ast_tuple.elts)
    return nodes.TupleExpr(
        elements=elements,
        ctx=ast_tuple.ctx,
        source_location=loc,
    )


_TExpressionVisitor = Callable[[_BuildContext, ast.expr], nodes.Expression]


def _expr_visitor_pair[TIn: ast.expr, TOut: nodes.Expression](
    typ: type[TIn],
    func: Callable[[_BuildContext, TIn], TOut],
) -> tuple[type[ast.expr], _TExpressionVisitor]:
    # see comments in _stmt_visitor_pair
    visitor = typing.cast(_TExpressionVisitor, func)
    return typ, visitor


def _unsupported_expr_type(ctx: _BuildContext, expr: ast.expr) -> typing.Never:
    loc = ctx.loc(expr)
    raise CodeError(_UNSUPPORTED_SYNTAX_MSG, loc) from None


_EXPRESSION_HANDLERS: typing.Final[
    Mapping[type[ast.expr], Callable[[_BuildContext, ast.expr], nodes.Expression]]
] = dict(
    (
        # expressions are listed here in the same order as the appear in:
        # https://docs.python.org/3/library/ast.html#abstract-grammar
        _expr_visitor_pair(ast.BoolOp, _visit_bool_op),
        _expr_visitor_pair(ast.NamedExpr, _visit_named_expr),
        _expr_visitor_pair(ast.BinOp, _visit_bin_op),
        _expr_visitor_pair(ast.UnaryOp, _visit_unary_op),
        (ast.Lambda, _unsupported_expr_type),
        _expr_visitor_pair(ast.IfExp, _visit_if_exp),
        _expr_visitor_pair(ast.Dict, _visit_dict_expr),
        (ast.Set, _unsupported_expr_type),
        (ast.ListComp, _unsupported_expr_type),
        (ast.SetComp, _unsupported_expr_type),
        (ast.DictComp, _unsupported_expr_type),
        (ast.GeneratorExp, _unsupported_expr_type),
        (ast.Await, _unsupported_expr_type),
        (ast.Yield, _unsupported_expr_type),
        (ast.YieldFrom, _unsupported_expr_type),
        _expr_visitor_pair(ast.Compare, _visit_compare),
        _expr_visitor_pair(ast.Call, _visit_call),
        _expr_visitor_pair(ast.FormattedValue, _visit_formatted_value),
        _expr_visitor_pair(ast.JoinedStr, _visit_joined_str),
        _expr_visitor_pair(ast.Constant, _visit_constant),
        _expr_visitor_pair(ast.Attribute, _visit_attribute),
        _expr_visitor_pair(ast.Subscript, _visit_subscript),
        (ast.Starred, _unsupported_expr_type),
        _expr_visitor_pair(ast.Name, _visit_name),
        _expr_visitor_pair(ast.List, _visit_list),
        _expr_visitor_pair(ast.Tuple, _visit_tuple),
        # !note Slice can only appear in Subscript, which we handle directly
        # if it starts appearing anywhere else, it's unsupported
        (ast.Slice, _unsupported_expr_type),
    )
)
