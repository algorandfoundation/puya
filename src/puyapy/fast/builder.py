import ast
import typing
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import log
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import coalesce, set_add, unique
from puyapy.fast import nodes

logger = log.get_logger(__name__)


@attrs.frozen
class FASTBuilder(ast.NodeVisitor):
    module_name: str
    module_path: Path

    @classmethod
    def parse_module(
        cls,
        *,
        source: str,
        module_path: Path,
        module_name: str,
        feature_version: int | tuple[int, int] | None = None,
    ) -> nodes.Module:
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
            raise CodeError(f"invalid Python syntax: {e.msg}", loc) from e

        builder = cls(module_name=module_name, module_path=module_path)
        return builder.visit_Module(mod)

    @typing.override
    def visit(self, node: ast.AST | None) -> nodes.Node | None:
        if node is None:
            return None
        # unlike the parent method, this will error if the visitor method is not defined
        method = "visit_" + node.__class__.__name__
        try:
            visitor = getattr(self, method)
        except AttributeError:
            loc = self._maybe_loc(node)
            if loc is not None:
                logger.error("unsupported Python syntax", location=loc)  # noqa: TRY400
            else:
                logger.error(f"unsupported Python syntax: {ast.unparse(node)}")  # noqa: TRY400
            return None
        else:
            result = visitor(node)
            assert isinstance(result, nodes.Node)
            return result

    @typing.override
    def visit_Module(self, module: ast.Module) -> nodes.Module:
        ast_body, docstring = _extract_docstring(module)
        body = self._visit_stmt_list(ast_body)
        future_flags = list[str]()
        while body:
            match body[0]:
                case nodes.FromImport(module="__future__", names=names) as future_import:
                    body.pop(0)
                    if names is None:
                        raise CodeError("invalid Python syntax", future_import.source_location)
                    for name in names:
                        if name.as_name:
                            raise CodeError("invalid Python syntax", name.source_location)
                        future_flags.append(name.name)
                case _:
                    break

        return nodes.Module(
            name=self.module_name,
            path=self.module_path,
            docstring=docstring,
            future_flags=tuple(unique(future_flags)),
            body=tuple(body),
        )

    @typing.override
    def visit_FunctionDef(self, func_def: ast.FunctionDef) -> nodes.FunctionDef:
        loc = self._loc(func_def)
        if func_def.type_comment is not None:
            logger.error("type comments are not supported", location=loc)
        type_params = getattr(func_def, "type_params", None)
        if type_params:
            logger.error("type parameters are not supported", location=loc)
        decorators = self._visit_decorator_list(func_def.decorator_list)
        params = self.visit_arguments(func_def.args)
        return_annotation = None
        if func_def.returns is not None:
            return_annotation = self._visit_expr(func_def.returns)
        ast_body, docstring = _extract_docstring(func_def)
        body = tuple(self._visit_stmt_list(ast_body))
        return nodes.FunctionDef(
            decorators=decorators,
            name=func_def.name,
            params=params,
            return_annotation=return_annotation,
            docstring=docstring,
            body=body,
            source_location=loc,
        )

    @typing.override
    def visit_arguments(self, args: ast.arguments) -> tuple[nodes.Parameter, ...]:
        params = []
        args_args = args.posonlyargs + args.args
        num_no_defaults = len(args_args) - len(args.defaults)
        defaults = ([None] * num_no_defaults) + args.defaults

        for i, (a, d) in enumerate(zip(args_args, defaults, strict=True)):
            if i < len(args.posonlyargs):
                pass_by = nodes.PassBy.POSITION
            else:
                pass_by = nodes.PassBy.POSITION | nodes.PassBy.NAME
            params.append(self._make_parameter(a, d, pass_by))

        # *arg
        if args.vararg is not None:
            logger.error(
                "variadic arguments are not supported in user functions",
                location=self._loc(args.vararg),
            )

        for a, kd in zip(args.kwonlyargs, args.kw_defaults, strict=True):
            params.append(self._make_parameter(a, kd, nodes.PassBy.NAME))

        # **kwarg
        if args.kwarg is not None:
            logger.error(
                "variadic arguments are not supported in user functions",
                location=self._loc(args.kwarg),
            )

        seen_names = set[str]()
        for param in params:
            if not set_add(seen_names, param.name):
                logger.error(
                    "invalid Python syntax:"
                    f" duplicate argument {param.name!r} in function definition",
                    location=param.source_location,
                )

        return tuple(params)

    def _make_parameter(
        self, arg: ast.arg, default: ast.expr | None, pass_by: nodes.PassBy
    ) -> nodes.Parameter:
        name = arg.arg
        annotation = self._visit_expr(arg.annotation)
        default_value = self._visit_expr(default)
        loc = self._loc(arg)
        if arg.type_comment:
            logger.error("type comments are not supported", location=loc)
        return nodes.Parameter(
            name=name,
            annotation=annotation,
            default=default_value,
            pass_by=pass_by,
            source_location=loc,
        )

    @typing.override
    def visit_ClassDef(self, class_def: ast.ClassDef) -> nodes.ClassDef:
        loc = self._loc(class_def)
        type_params = getattr(class_def, "type_params", None)
        if type_params:
            logger.error("type parameters are not supported", location=loc)
        decorators = self._visit_decorator_list(class_def.decorator_list)
        bases, _ = self._visit_expr_list(class_def.bases)
        kwargs = self._visit_keywords_list(class_def.keywords)
        ast_body, docstring = _extract_docstring(class_def)
        body = tuple(self._visit_stmt_list(ast_body))
        return nodes.ClassDef(
            decorators=decorators,
            name=class_def.name,
            bases=bases,
            kwargs=kwargs,
            docstring=docstring,
            body=body,
            source_location=loc,
        )

    @typing.override
    def visit_alias(self, alias: ast.alias) -> nodes.ImportAs:
        loc = self._loc(alias)
        return nodes.ImportAs(
            name=alias.name,
            as_name=alias.asname,
            source_location=loc,
        )

    @typing.override
    def visit_Import(self, node: ast.Import) -> nodes.ModuleImport:
        names = [self.visit_alias(alias) for alias in node.names]
        loc = self._loc(node)
        return nodes.ModuleImport(names=names, source_location=loc)

    @typing.override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> nodes.FromImport:
        match node.names:
            case [ast.alias("*", None)]:
                names = None
            case _:
                names = [self.visit_alias(alias) for alias in node.names]
        loc = self._loc(node)
        module_is_init = self.module_path.stem == "__init__"
        module = correct_relative_import(
            node.level,
            current_module=self.module_name,
            target_module=node.module,
            module_is_init=module_is_init,
            import_loc=loc,
        )
        return nodes.FromImport(
            module=module,
            names=names,
            source_location=loc,
        )

    @typing.override
    def visit_Return(self, ret: ast.Return) -> nodes.Return:
        value = self._visit_expr(ret.value)
        loc = self._loc(ret)
        return nodes.Return(value=value, source_location=loc)

    @typing.override
    def visit_Delete(self, delete: ast.Delete) -> nodes.Delete | None:
        targets, targets_ok = self._visit_expr_list(delete.targets)
        if not targets_ok:
            return None
        loc = self._loc(delete)
        return nodes.Delete(
            targets=tuple(targets),
            source_location=loc,
        )

    @typing.override
    def visit_Assign(self, assign: ast.Assign) -> nodes.Assign | nodes.MultiAssign | None:
        loc = self._loc(assign)
        if assign.type_comment is not None:
            logger.error("type comments are not supported", location=loc)
        value = self._visit_expr(assign.value)
        targets, targets_ok = self._visit_expr_list(assign.targets)
        if value is None or not targets_ok:
            return None
        elif len(targets) > 1:
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

    @typing.override
    def visit_AnnAssign(
        self, ann_assign: ast.AnnAssign
    ) -> nodes.AnnotationStatement | nodes.Assign | None:
        loc = self._loc(ann_assign)
        target: nodes.Name | nodes.Attribute | nodes.Subscript | None
        match ann_assign.target:
            case ast.Name() as name_expr:
                target = self.visit_Name(name_expr)
            case ast.Attribute() as attribute_expr:
                target = self.visit_Attribute(attribute_expr)
            case ast.Subscript() as subscript_expr:
                target = self.visit_Subscript(subscript_expr)
            case unexpected:
                typing.assert_never(unexpected)
        annotation = self._visit_expr(ann_assign.annotation)
        value = self._visit_expr(ann_assign.value)
        if annotation is None or target is None:
            return None
        elif value is None:
            return nodes.AnnotationStatement(
                target=target,
                annotation=annotation,
                source_location=loc,
            )
        else:
            return nodes.Assign(
                target=target,
                value=value,
                annotation=annotation,
                source_location=loc,
            )

    @typing.override
    def visit_AugAssign(self, aug_assign: ast.AugAssign) -> nodes.AugAssign | None:
        loc = self._loc(aug_assign)
        target: nodes.Name | nodes.Attribute | nodes.Subscript | None
        match aug_assign.target:
            case ast.Name() as name_expr:
                target = self.visit_Name(name_expr)
            case ast.Attribute() as attribute_expr:
                target = self.visit_Attribute(attribute_expr)
            case ast.Subscript() as subscript_expr:
                target = self.visit_Subscript(subscript_expr)
            case unexpected:
                typing.assert_never(unexpected)
        value = self._visit_expr(aug_assign.value)
        if value is None or target is None:
            return None
        return nodes.AugAssign(
            target=target,
            op=aug_assign.op,
            value=value,
            source_location=loc,
        )

    @typing.override
    def visit_Name(self, name: ast.Name) -> nodes.Name:
        loc = self._loc(name)
        return nodes.Name(
            id=name.id,
            ctx=name.ctx,
            source_location=loc,
        )

    @typing.override
    def visit_Attribute(self, attribute: ast.Attribute) -> nodes.Attribute | None:
        base = self._visit_expr(attribute.value)
        if base is None:
            return None
        loc = self._loc(attribute)
        return nodes.Attribute(
            base=base,
            attr=attribute.attr,
            ctx=attribute.ctx,
            source_location=loc,
        )

    @typing.override
    def visit_Subscript(self, subscript: ast.Subscript) -> nodes.Subscript | None:
        base = self._visit_expr(subscript.value)
        match subscript.slice:
            case ast.Tuple(elts=ast_indexes):
                pass
            case ast_index:
                ast_indexes = [ast_index]
        if base is None:
            return None
        indexes = list[nodes.Expression | nodes.Slice]()
        for ast_index in ast_indexes:
            match ast_index:
                case ast.Slice():
                    index_slice = self.visit_Slice(ast_index)
                    indexes.append(index_slice)
                case _:
                    index = self._visit_expr(ast_index)
                    if index is not None:
                        indexes.append(index)
        loc = self._loc(subscript)
        return nodes.Subscript(
            base=base,
            indexes=tuple(indexes),
            ctx=subscript.ctx,
            source_location=loc,
        )

    @typing.override
    def visit_Slice(self, slice: ast.Slice) -> nodes.Slice:
        lower = self._visit_expr(slice.lower)
        upper = self._visit_expr(slice.upper)
        step = self._visit_expr(slice.step)
        loc = self._loc(slice)
        return nodes.Slice(
            lower=lower,
            upper=upper,
            step=step,
            source_location=loc,
        )

    @typing.override
    def visit_For(self, for_stmt: ast.For) -> nodes.For | None:
        loc = self._loc(for_stmt)
        if for_stmt.type_comment is not None:
            logger.error("type comments are not supported", location=loc)
        target = self._visit_expr(for_stmt.target)
        iterable = self._visit_expr(for_stmt.iter)
        if target is None or iterable is None:
            return None
        body = self._visit_stmt_list(for_stmt.body)
        else_body = self._visit_stmt_list(for_stmt.orelse)
        return nodes.For(
            target=target,
            iterable=iterable,
            body=tuple(body),
            else_body=tuple(else_body),
            source_location=loc,
        )

    @typing.override
    def visit_While(self, while_stmt: ast.While) -> nodes.While | None:
        loc = self._loc(while_stmt)
        test = self._visit_expr(while_stmt.test)
        body = self._visit_stmt_list(while_stmt.body)
        else_body = self._visit_stmt_list(while_stmt.orelse)
        if test is None:
            return None
        return nodes.While(
            test=test,
            body=tuple(body),
            else_body=tuple(else_body),
            source_location=loc,
        )

    @typing.override
    def visit_If(self, if_stmt: ast.If) -> nodes.If | None:
        loc = self._loc(if_stmt)
        test = self._visit_expr(if_stmt.test)
        body = self._visit_stmt_list(if_stmt.body)
        else_body = self._visit_stmt_list(if_stmt.orelse)
        if test is None:
            return None
        return nodes.If(
            test=test,
            body=tuple(body),
            else_body=tuple(else_body),
            source_location=loc,
        )

    @typing.override
    def visit_Constant(self, constant: ast.Constant) -> nodes.Constant:
        loc = self._loc(constant)
        return nodes.Constant(
            value=constant.value,
            source_location=loc,
        )

    def _visit_expr_list(self, exprs: list[ast.expr]) -> tuple[tuple[nodes.Expression, ...], bool]:
        result = []
        ok = True
        for expr in exprs:
            transformed = self._visit_expr(expr)
            if transformed is not None:
                result.append(transformed)
            else:
                ok = False
        return tuple(result), ok

    def _visit_expr(self, expr: ast.expr | None) -> nodes.Expression | None:
        result = self.visit(expr)
        assert isinstance(result, nodes.Expression | None)
        return result

    def _visit_stmt_list(self, stmts: list[ast.stmt]) -> list[nodes.Statement]:
        result = []
        for ast_stmt in stmts:
            stmt = self.visit(ast_stmt)
            match stmt:
                case None:
                    pass  # error should already have been reported
                case nodes.Statement():
                    result.append(stmt)
                case _:
                    raise InternalError(
                        f"unexpected node type transformation, expected a Statement:"
                        f" {_type_name(type(ast_stmt))} -> {_type_name(type(stmt))}",
                        self._loc(ast_stmt),
                    )
        return result

    def _visit_keywords_list(self, keywords: list[ast.keyword]) -> immutabledict[str, ast.expr]:
        kwargs = {}
        for kw in keywords:
            if kw.arg is None:
                logger.error(
                    "keyword argument unpacking in base list is not supported",
                    location=self._loc(kw),
                )
            elif kw.arg in kwargs:
                logger.error(
                    f"invalid Python syntax: keyword argument repeated: {kw.arg}",
                    location=self._loc(kw),
                )
            else:
                kwargs[kw.arg] = kw.value
        return immutabledict(kwargs)

    def _visit_decorator_list(self, decorator_list: list[ast.expr]) -> tuple[nodes.Decorator, ...]:
        result = []
        for decorator in decorator_list:
            callee: ast.expr
            args: tuple[ast.expr, ...] | None
            kwargs: immutabledict[str, ast.expr] | None
            match decorator:
                case ast.Call(func=callee, args=args_list, keywords=keywords):
                    args = tuple(args_list)
                    kwargs = self._visit_keywords_list(keywords)
                case callee:
                    args = None
                    kwargs = None
            loc = self._loc(decorator)
            callee_name = self._extract_dotted_name(callee)
            if callee_name is None:
                logger.error("unsupported decorator syntax", location=loc)
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

    def _extract_dotted_name(self, expr: ast.expr) -> str | None:
        match expr:
            case ast.Name(id=name):
                return name
            case ast.Attribute(value=base, attr=name):
                base_name = self._extract_dotted_name(base)
                if base_name is None:
                    return None
                return f"{base_name}.{name}"
            case _:
                return None

    def _maybe_loc(self, node: ast.AST) -> SourceLocation | None:
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

    def _loc(
        self, node: ast.expr | ast.stmt | ast.alias | ast.arg | ast.keyword
    ) -> SourceLocation:
        return SourceLocation(
            file=self.module_path,
            line=node.lineno,
            end_line=node.end_lineno if node.end_lineno is not None else node.lineno,
            column=node.col_offset,
            end_column=node.end_col_offset,
        )


def _extract_docstring(
    node: ast.Module | ast.ClassDef | ast.FunctionDef,
) -> tuple[list[ast.stmt], str | None]:
    docstring = ast.get_docstring(node, clean=False)
    body = node.body
    if docstring is not None:
        body = node.body[1:]
    return body, docstring


def correct_relative_import(
    relative: int,
    *,
    current_module: str,
    target_module: str | None,
    module_is_init: bool,
    import_loc: SourceLocation,
) -> str:
    if not relative:
        assert target_module is not None, "non-relative from-import without identifier"
        return target_module

    if module_is_init:
        relative -= 1
    parts = current_module.split(".")
    if len(parts) < relative:
        logger.error("no parent module, cannot perform relative import", location=import_loc)
    if relative == 0:
        base = current_module
    else:
        base = ".".join(parts[:-relative])
    if target_module is None:
        absolute = base
    else:
        absolute = f"{base}.{target_module}"
    return absolute


def _type_name(t: type) -> str:
    return ".".join((t.__module__, t.__qualname__))
