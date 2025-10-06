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
    def visit_Import(self, node: ast.Import) -> nodes.ModuleImport:
        names = [self.visit_alias(alias) for alias in node.names]
        loc = self._loc(node)
        return nodes.ModuleImport(names=names, source_location=loc)

    @typing.override
    def visit_alias(self, alias: ast.alias) -> nodes.ImportAs:
        return nodes.ImportAs(
            name=alias.name,
            as_name=alias.asname,
            source_location=self._loc(alias),
        )

    @typing.override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> nodes.FromImport | None:
        match node.names:
            case [ast.alias("*", None)]:
                names = None
            case _:
                names = [self.visit_alias(alias) for alias in node.names]

        node_loc = self._loc(node)
        if not node.level:
            assert node.module
            module = node.module
        else:
            is_module_init = self.module_path.stem == "__init__"
            module, relative_okay = correct_relative_import(
                self.module_name, node.level, node.module, cur_mod_is_init=is_module_init
            )
            if not relative_okay:
                logger.error("no parent module, cannot perform relative import", location=node_loc)
                return None

        return nodes.FromImport(
            module=module,
            names=names,
            source_location=node_loc,
        )

    def _loc(self, node: ast.expr | ast.stmt | ast.alias) -> SourceLocation:
        return SourceLocation(
            file=self.module_path,
            line=node.lineno,
            end_line=node.end_lineno if node.end_lineno is not None else node.lineno,
            column=node.col_offset,
            end_column=node.end_col_offset,
        )


def correct_relative_import(
    cur_mod_id: str, relative: int, target: str | None, *, cur_mod_is_init: bool
) -> tuple[str, bool]:
    assert relative > 0
    parts = cur_mod_id.split(".")
    rel = relative
    if cur_mod_is_init:
        rel -= 1
    ok = len(parts) >= rel
    if rel != 0:
        cur_mod_id = ".".join(parts[:-rel])
    suffix = ("." + target) if target else ""
    return cur_mod_id + suffix, ok
