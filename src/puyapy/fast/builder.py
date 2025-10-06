import ast
import typing
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation
from puyapy.fast import nodes

logger = log.get_logger(__name__)


@attrs.frozen
class FASTBuilder(ast.NodeVisitor):
    module_name: str
    module_path: Path

    @typing.override
    def visit(self, node: ast.AST) -> typing.Any:
        # unlike the parent method, this will error if the visitor method is not defined
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, None)
        if visitor is None:
            node_loc = self._loc(node)
            logger.error("unsupported ", location=node_loc)
            return None
        else:
            return visitor(node)

    @typing.override
    def visit_alias(self, alias: ast.alias) -> nodes.ImportAs:
        return nodes.ImportAs(
            name=alias.name,
            as_name=alias.asname,
            source_location=self._loc(alias),
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

    def _loc(self, node: ast.AST) -> SourceLocation:
        return SourceLocation(
            file=self.module_path,
            line=node.lineno,
            end_line=node.end_lineno if node.end_lineno is not None else node.lineno,
            column=node.col_offset,
            end_column=node.end_col_offset,
        )


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
