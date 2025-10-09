import ast
import typing
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import log
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import coalesce, unique
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
            raise CodeError("type comments are not supported", loc)
        type_params = getattr(func_def, "type_params", None)
        if type_params:
            raise CodeError("type parameters are not supported", loc)
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
        raise NotImplementedError

    @typing.override
    def visit_ClassDef(self, class_def: ast.ClassDef) -> nodes.ClassDef:
        loc = self._loc(class_def)
        type_params = getattr(class_def, "type_params", None)
        if type_params:
            raise CodeError("type parameters are not supported", loc)
        decorators = self._visit_decorator_list(class_def.decorator_list)
        bases = tuple(self._visit_expr_list(class_def.bases))
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

    def _visit_expr_list(self, exprs: list[ast.expr]) -> list[nodes.Expression]:
        result = []
        for expr in exprs:
            transformed = self._visit_expr(expr)
            if transformed is not None:
                result.append(transformed)
        return result

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

    def _loc(self, node: ast.expr | ast.stmt | ast.alias | ast.keyword) -> SourceLocation:
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
