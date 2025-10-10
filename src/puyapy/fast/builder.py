import ast
import typing
from collections.abc import Callable, Mapping
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import log
from puya.errors import CodeError, InternalError, PuyaError
from puya.parse import SourceLocation
from puya.utils import coalesce, set_add, unique
from puyapy.fast import nodes

logger = log.get_logger(__name__)


_UNSUPPORTED_SYNTAX_MSG = "unsupported Python syntax"
_INVALID_SYNTAX_MSG = "invalid Python syntax"
_NO_TYPE_COMMENTS_MSG = "type comments are not supported"
_NO_TYPE_PARAMS_MSG = "type parameters are not supported"


@attrs.frozen
class FASTResult:
    ast: ast.Module | None
    module: nodes.Module | None


def parse_module(
    *,
    source: str,
    module_path: Path,
    module_name: str,
    feature_version: int | tuple[int, int] | None = None,
) -> FASTResult:
    mod: ast.Module | None
    try:
        mod = ast.parse(
            source, module_path, "exec", type_comments=True, feature_version=feature_version
        )
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
        mod = None
        fast = None
    else:
        fast = _convert_module(mod, module_path=module_path, module_name=module_name)
    return FASTResult(ast=mod, module=fast)


@attrs.define
class _BuildContext:
    module_name: str = attrs.field(on_setattr=attrs.setters.frozen)
    module_path: Path = attrs.field(on_setattr=attrs.setters.frozen)
    _failures: int = attrs.field(default=0, init=False)

    @property
    def failures(self) -> int:
        return self._failures

    def invalid_syntax(self, loc: SourceLocation | None, detail: str | None = None) -> None:
        if detail is None:
            message = _INVALID_SYNTAX_MSG
        else:
            message = f"{_INVALID_SYNTAX_MSG}: {detail}"
        # TODO: replace with call to _fail() once that's an error
        # self._fail(message, loc)
        logger.error(message, location=loc)
        self._failures += 1

    def unsupported_syntax(self, loc: SourceLocation | None, detail: str | None = None) -> None:
        if detail is None:
            message = _UNSUPPORTED_SYNTAX_MSG
        else:
            message = f"{_UNSUPPORTED_SYNTAX_MSG}: {detail}"
        self.fail(message, loc)

    def fail(self, message: str, loc: SourceLocation | None) -> None:
        # logger.error(message, location=loc)
        # TODO: delete next line, uncomment previous line
        logger.debug(f"<<FAST>> ({loc}) " + message)
        self._failures += 1

    def maybe_loc(self, node: ast.AST) -> SourceLocation | None:
        lineno = getattr(node, "lineno", None)
        if lineno is None:
            return None
        return SourceLocation(
            file=self.module_path,
            line=lineno,
            end_line=getattr(node, "end_lineno", lineno),
            column=getattr(node, "col_offset", None),
            end_column=getattr(node, "end_col_offset", None),
        )

    def loc(
        self, node: ast.expr | ast.stmt | ast.pattern | ast.alias | ast.arg | ast.keyword
    ) -> SourceLocation:
        return SourceLocation(
            file=self.module_path,
            line=node.lineno,
            end_line=node.end_lineno if node.end_lineno is not None else node.lineno,
            column=node.col_offset,
            end_column=node.end_col_offset,
        )


def _convert_module(
    module: ast.Module,
    *,
    module_path: Path,
    module_name: str,
) -> nodes.Module | None:
    ctx = _BuildContext(module_name=module_name, module_path=module_path)
    ast_body, docstring = _extract_docstring(module)
    body = _visit_stmt_list(ctx, ast_body)
    # Feature flag imports do technically exist as objects of type _Feature,
    # but there's no use case for being able to access these from Algorand Python,
    # so just collect them up as flags.
    future_flags = list[str]()
    while body:
        match body[0]:
            case nodes.FromImport(module="__future__", names=names) as future_import:
                body.pop(0)
                if names is None:
                    ctx.invalid_syntax(future_import.source_location)
                else:
                    for name in names:
                        # aliasing is technically allowed, but since we're not allowing access
                        # doesn't matter anyway
                        future_flags.append(name.name)
            case _:
                break

    if ctx.failures:
        return None
    return nodes.Module(
        name=module_name,
        path=module_path,
        docstring=docstring,
        future_flags=tuple(unique(future_flags)),
        body=tuple(body),
    )


def _extract_docstring(
    node: ast.Module | ast.ClassDef | ast.FunctionDef,
) -> tuple[list[ast.stmt], str | None]:
    docstring = ast.get_docstring(node, clean=False)
    body = node.body
    if docstring is not None:
        body = node.body[1:]
    return body, docstring


def _visit_stmt_list(ctx: _BuildContext, stmts: list[ast.stmt]) -> list[nodes.Statement]:
    result = []
    for ast_stmt in stmts:
        stmt = _visit_stmt(ctx, ast_stmt)
        if stmt is not None:
            result.append(stmt)
    return result


def _visit_stmt(ctx: _BuildContext, node: ast.stmt) -> nodes.Statement | None:
    loc = ctx.loc(node)
    result = None
    try:
        handler = _STATEMENT_HANDLERS[type(node)]
    except KeyError:
        ctx.unsupported_syntax(loc)
    else:
        # with log_exceptions(loc):
        # TODO: delete try-except, uncomment previous line
        try:
            result = handler(ctx, node)
        except PuyaError as e:
            logger.debug(f"<<FAST>> ({loc}) " + e.msg)
        except NotImplementedError:
            pass
    return result


def _visit_function_def(ctx: _BuildContext, func_def: ast.FunctionDef) -> nodes.FunctionDef:
    loc = ctx.loc(func_def)
    if func_def.type_comment is not None:
        ctx.fail(_NO_TYPE_COMMENTS_MSG, loc)
    type_params = getattr(func_def, "type_params", None)
    if type_params:
        ctx.fail(_NO_TYPE_PARAMS_MSG, loc)
    decorators = _visit_decorator_list(ctx, func_def.decorator_list)
    params = _convert_arguments(ctx, func_def.args)
    return_annotation = None
    if func_def.returns is not None:
        return_annotation = _visit_expr(ctx, func_def.returns)
    ast_body, docstring = _extract_docstring(func_def)
    body = tuple(_visit_stmt_list(ctx, ast_body))
    return nodes.FunctionDef(
        decorators=decorators,
        name=func_def.name,
        params=params,
        return_annotation=return_annotation,
        docstring=docstring,
        body=body,
        source_location=loc,
    )


def _visit_decorator_list(
    ctx: _BuildContext, decorator_list: list[ast.expr]
) -> tuple[nodes.Decorator, ...]:
    result = []
    for decorator in decorator_list:
        callee: ast.expr
        args: tuple[ast.expr, ...] | None
        kwargs: immutabledict[str, ast.expr] | None
        match decorator:
            case ast.Call(func=callee, args=args_list, keywords=keywords):
                args = tuple(args_list)
                kwargs = _visit_keywords_list(ctx, keywords)
            case callee:
                args = None
                kwargs = None
        loc = ctx.loc(decorator)
        callee_name = _extract_dotted_name(ctx, callee)
        if callee_name is None:
            # see comments on nodes.Decorator for more context
            ctx.unsupported_syntax(loc)
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
            ctx.loc(args.vararg),
            "variadic arguments are not supported in user functions",
        )

    for a, kd in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        params.append(_make_parameter(ctx, a, kd, nodes.PassBy.NAME))

    # **kwarg
    if args.kwarg is not None:
        ctx.unsupported_syntax(
            ctx.loc(args.kwarg),
            "variadic arguments are not supported in user functions",
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
    decorators = _visit_decorator_list(ctx, class_def.decorator_list)
    bases = _visit_expr_list(ctx, class_def.bases)
    kwargs = _visit_keywords_list(ctx, class_def.keywords)
    ast_body, docstring = _extract_docstring(class_def)
    body = tuple(_visit_stmt_list(ctx, ast_body))
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
    names = [_visit_alias(ctx, alias) for alias in node.names]
    loc = ctx.loc(node)
    return nodes.ModuleImport(names=names, source_location=loc)


def _visit_alias(ctx: _BuildContext, alias: ast.alias) -> nodes.ImportAs:
    loc = ctx.loc(alias)
    return nodes.ImportAs(
        name=alias.name,
        as_name=alias.asname,
        source_location=loc,
    )


def _visit_import_from(ctx: _BuildContext, node: ast.ImportFrom) -> nodes.FromImport:
    match node.names:
        case [ast.alias("*", None)]:
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
    body = tuple(_visit_stmt_list(ctx, for_stmt.body))
    if not for_stmt.orelse:
        else_body = None
    else:
        else_body = tuple(_visit_stmt_list(ctx, for_stmt.orelse))
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
    body = tuple(_visit_stmt_list(ctx, while_stmt.body))
    if not while_stmt.orelse:
        else_body = None
    else:
        else_body = tuple(_visit_stmt_list(ctx, while_stmt.orelse))
    return nodes.While(
        test=test,
        body=body,
        else_body=else_body,
        source_location=loc,
    )


def _visit_if(ctx: _BuildContext, if_stmt: ast.If) -> nodes.If:
    loc = ctx.loc(if_stmt)
    test = _visit_expr(ctx, if_stmt.test)
    body = tuple(_visit_stmt_list(ctx, if_stmt.body))
    if not if_stmt.orelse:
        else_body = None
    else:
        else_body = tuple(_visit_stmt_list(ctx, if_stmt.orelse))
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
) -> immutabledict[str, ast.expr]:
    kwargs = {}
    for kw in keywords:
        if kw.arg is None:
            # if the arg names is None, it's a **kwargs unpacking
            ctx.unsupported_syntax(ctx.loc(kw))
        elif kw.arg in kwargs:
            ctx.invalid_syntax(ctx.loc(kw), f"keyword argument repeated: {kw.arg}")
        else:
            kwargs[kw.arg] = kw.value
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
        body = tuple(_visit_stmt_list(ctx, case.body))
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


_TStatementVisitor = Callable[[_BuildContext, ast.stmt], nodes.Statement]


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


_STATEMENT_HANDLERS: typing.Final[
    Mapping[type[ast.stmt], Callable[[_BuildContext, ast.stmt], nodes.Statement]]
] = dict(
    (
        # supported statements are listed here in the same order as the appear in:
        # https://docs.python.org/3.12/library/ast.html#abstract-grammar
        _stmt_visitor_pair(ast.FunctionDef, _visit_function_def),
        # <br>
        _stmt_visitor_pair(ast.ClassDef, _visit_class_def),
        _stmt_visitor_pair(ast.Return, _visit_return),
        # <br>
        _stmt_visitor_pair(ast.Delete, _visit_delete),
        _stmt_visitor_pair(ast.Assign, _visit_assign),
        _stmt_visitor_pair(ast.AugAssign, _visit_augmented_assign),
        _stmt_visitor_pair(ast.AnnAssign, _visit_annotated_assign),
        # <br>
        _stmt_visitor_pair(ast.For, _visit_for_loop),
        _stmt_visitor_pair(ast.While, _visit_while_loop),
        _stmt_visitor_pair(ast.If, _visit_if),
        # <br>
        _stmt_visitor_pair(ast.Match, _visit_match),
        # <br>
        _stmt_visitor_pair(ast.Assert, _visit_assert),
        # <br>
        _stmt_visitor_pair(ast.Import, _visit_import),
        _stmt_visitor_pair(ast.ImportFrom, _visit_import_from),
        # <br>
        _stmt_visitor_pair(ast.Expr, _visit_expression_statement),
        _stmt_visitor_pair(ast.Pass, _visit_pass),
        _stmt_visitor_pair(ast.Break, _visit_break),
        _stmt_visitor_pair(ast.Continue, _visit_continue),
    )
)


def _visit_expr_list(ctx: _BuildContext, exprs: list[ast.expr]) -> tuple[nodes.Expression, ...]:
    return tuple(_visit_expr(ctx, expr) for expr in exprs)


def _visit_expr(ctx: _BuildContext, node: ast.expr) -> nodes.Expression:
    try:
        handler = _EXPRESSION_HANDLERS[type(node)]
    except KeyError:
        loc = ctx.loc(node)
        raise CodeError(_UNSUPPORTED_SYNTAX_MSG, loc) from None
    else:
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
    base = _visit_expr(ctx, attribute.value)
    loc = ctx.loc(attribute)
    return nodes.Attribute(
        base=base,
        attr=attribute.attr,
        ctx=attribute.ctx,
        source_location=loc,
    )


def _visit_subscript(ctx: _BuildContext, subscript: ast.Subscript) -> nodes.Subscript:
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
    loc = ctx.loc(subscript)
    return nodes.Subscript(
        base=base,
        indexes=tuple(indexes),
        ctx=subscript.ctx,
        source_location=loc,
    )


def _visit_slice(ctx: _BuildContext, slice_: ast.Slice) -> nodes.Slice:
    lower = _visit_optional_expr(ctx, slice_.lower)
    upper = _visit_optional_expr(ctx, slice_.upper)
    step = _visit_optional_expr(ctx, slice_.step)
    loc = ctx.loc(slice_)
    return nodes.Slice(
        lower=lower,
        upper=upper,
        step=step,
        source_location=loc,
    )


def _visit_bool_op(ctx: _BuildContext, bool_op: ast.BoolOp) -> typing.Never:
    raise NotImplementedError


def _visit_named_expr(ctx: _BuildContext, named_expr: ast.NamedExpr) -> typing.Never:
    raise NotImplementedError


def _visit_bin_op(ctx: _BuildContext, bin_op: ast.BinOp) -> typing.Never:
    raise NotImplementedError


def _visit_unary_op(ctx: _BuildContext, unary_op: ast.UnaryOp) -> typing.Never:
    raise NotImplementedError


def _visit_if_exp(ctx: _BuildContext, if_exp: ast.IfExp) -> typing.Never:
    raise NotImplementedError


def _visit_compare(ctx: _BuildContext, compare: ast.Compare) -> typing.Never:
    raise NotImplementedError


def _visit_call(ctx: _BuildContext, call: ast.Call) -> typing.Never:
    raise NotImplementedError


def _visit_formatted_value(
    ctx: _BuildContext, formatted_value: ast.FormattedValue
) -> typing.Never:
    raise NotImplementedError


def _visit_joined_str(ctx: _BuildContext, joined_str: ast.JoinedStr) -> typing.Never:
    raise NotImplementedError


def _visit_list(ctx: _BuildContext, list_: ast.List) -> typing.Never:
    raise NotImplementedError


def _visit_tuple(ctx: _BuildContext, tuple_: ast.Tuple) -> typing.Never:
    raise NotImplementedError


_TExpressionVisitor = Callable[[_BuildContext, ast.expr], nodes.Expression]


def _expr_visitor_pair[TIn: ast.expr, TOut: nodes.Expression](
    typ: type[TIn],
    func: Callable[[_BuildContext, TIn], TOut],
) -> tuple[type[ast.expr], _TExpressionVisitor]:
    # see comments in _stmt_visitor_pair
    visitor = typing.cast(_TExpressionVisitor, func)
    return typ, visitor


_EXPRESSION_HANDLERS: typing.Final[
    Mapping[type[ast.expr], Callable[[_BuildContext, ast.expr], nodes.Expression]]
] = dict(
    (
        # supported statements are listed here in the same order as the appear in:
        # https://docs.python.org/3.12/library/ast.html#abstract-grammar
        _expr_visitor_pair(ast.BoolOp, _visit_bool_op),
        _expr_visitor_pair(ast.NamedExpr, _visit_named_expr),
        _expr_visitor_pair(ast.BinOp, _visit_bin_op),
        _expr_visitor_pair(ast.UnaryOp, _visit_unary_op),
        _expr_visitor_pair(ast.IfExp, _visit_if_exp),
        _expr_visitor_pair(ast.Compare, _visit_compare),
        _expr_visitor_pair(ast.Call, _visit_call),
        _expr_visitor_pair(ast.FormattedValue, _visit_formatted_value),
        _expr_visitor_pair(ast.JoinedStr, _visit_joined_str),
        _expr_visitor_pair(ast.Constant, _visit_constant),
        # <br>
        _expr_visitor_pair(ast.Attribute, _visit_attribute),
        _expr_visitor_pair(ast.Subscript, _visit_subscript),
        _expr_visitor_pair(ast.Name, _visit_name),
        _expr_visitor_pair(ast.List, _visit_list),  # *only* supported when ctx=ast.Store
        _expr_visitor_pair(ast.Tuple, _visit_tuple),
        # <br>
        # Slice - note this can only appear in Subscript, which we handle directly
    )
)
