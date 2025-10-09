import ast
import contextlib
import contextvars
import platform
import re
import typing
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from urllib.parse import unquote, urlparse

import attrs
from lsprotocol import types as lsp
from pygls.workspace import Workspace

from puya.compile import awst_to_teal
from puya.errors import PuyaExitError, log_exceptions
from puya.log import Log, LogLevel, get_logger, logging_context
from puya.parse import SourceLocation
from puya.utils import StableSet, coalesce, get_cwd, set_cwd
from puyapy import code_fixes
from puyapy.awst_build.main import transform_ast
from puyapy.options import PuyaPyOptions
from puyapy.parse import SourceModule, parse_python

logger = get_logger(__name__)


@attrs.frozen
class DocumentAnalysis:
    uri: str
    """uri of document"""
    version: int | None
    """version of document when it was analysed"""
    diagnostics: list[lsp.Diagnostic]
    """warning or errors present in document"""
    actions: list[tuple[lsp.Range, lsp.CodeAction]]
    """possible code actions suggested in document"""


@attrs.define
class CodeAnalyser:
    """Handles analysing specified paths, and tracking dependencies between modules"""

    _package_search_paths: list[str]
    _workspace: Workspace
    _dependencies: dict[Path, list[Path]] = attrs.field(factory=dict)
    """
    Dependencies are inverted to reflect what files should also be analysed when a file changes

    e.g. if module A imports module B then mapping will be
    { B: [A] }
    """

    def analyse(self, changed_uris: Sequence[str]) -> Mapping[str, DocumentAnalysis]:
        logger.debug(f"analyse changed_uris={', '.join(map(str, changed_uris))}")

        # get all algopy paths and related dependencies from supplied uris
        paths = self._get_algopy_related_files(changed_uris)

        if not paths:
            logger.debug("no algopy related files were changed, nothing to do")
            return {}
        logger.debug(f"analysing algopy related paths={', '.join(map(str, paths))}")

        root_path = Path(self._workspace.root_path)
        with set_cwd(root_path):
            return self._compile_and_capture_symbols_fixes_and_logs(paths)

    def _compile_and_capture_symbols_fixes_and_logs(
        self, paths: Sequence[Path]
    ) -> dict[str, DocumentAnalysis]:
        # parse Typed AST
        puyapy_options = PuyaPyOptions(
            log_level=LogLevel.info,
            paths=paths,
            # don't need optimization for analysis
            optimization_level=0,
            debug_level=0,
            optimizations_override={
                "perform_subroutine_inlining": False,
                "merge_chained_aggregate_reads": True,
                "replace_aggregate_box_ops": True,
            },
        )
        try:
            with logging_context() as parse_ctx:
                parse_result = parse_python(
                    puyapy_options.paths,
                    package_search_paths=self._package_search_paths,
                    file_contents=self._get_file_contents(),
                )
        except Exception as ex:
            # TODO: how should we recover if mypy has critical errors
            logger.debug(f"error during parsing: {ex}")
            return {}
        logger.debug("AST parse complete")
        modules = parse_result.ordered_modules
        # capture dependencies for future passes so we can refresh modules that may require
        # updating when their dependencies change
        self._analyse_dependencies(modules)
        fixes = list[code_fixes.CodeFix]()
        logs = list(parse_ctx.logs)
        # lower Typed AST to AWST
        if not parse_ctx.num_errors:
            logger.debug("transforming AST to AWST")
            with (
                logging_context() as awst_ctx,
                contextlib.suppress(PuyaExitError),
                log_exceptions(),
                _code_fix_context() as fixes,
            ):
                awst, compilation_targets = transform_ast(parse_result, puyapy_options)
            logs.extend(awst_ctx.logs)

            # if no errors, then attempt to lower to TEAL and extend logs with any
            # further results
            if not awst_ctx.num_errors:
                logger.debug("lowering AWST to TEAL")
                dummy = get_cwd()
                compilation_set = {t: dummy for t in compilation_targets}
                with (
                    logging_context() as awst_ctx,
                    contextlib.suppress(PuyaExitError),
                    log_exceptions(),
                ):
                    awst_to_teal(
                        awst_ctx,
                        options=puyapy_options,
                        compilation_set=compilation_set,
                        sources_by_path={},
                        awst=awst,
                        write=False,
                    )
                logs.extend(awst_ctx.logs)
        logger.debug("compile complete")
        modules_by_path = {m.path: m for m in modules.values()}
        result = {}

        # need to be able to map Paths back to their original uri's as simply calling
        # .as_uri() may not give back the original uri
        path_to_uri_version = dict[Path, tuple[str, int | None]]()
        for uri, doc in self._workspace.text_documents.items():
            path = _uri_to_path(uri)
            if path is not None:
                path_to_uri_version[path] = uri, doc.version

        for path in puyapy_options.paths:
            try:
                uri, version = path_to_uri_version[path]
            except KeyError:
                uri = path.as_uri()
                version = None
            module = modules_by_path[path]
            path_logs = [
                log
                for log in logs
                if log.level > LogLevel.info and log.location and log.location.file == path
            ]
            path_fixes = [fix for fix in fixes if fix.location.file == path]
            path_actions = []
            if path_fixes:
                symbol_resolver = _AlgopySymbolResolver.create(module)
                path_actions = [
                    (
                        _source_location_to_range(fix.location),
                        symbol_resolver.fix_to_code_action(uri, fix),
                    )
                    for fix in fixes
                    if fix.location.file == path
                ]
            logger.debug(
                f"analysis found {path} has {len(path_actions)} actions, {len(path_logs)} logs"
            )
            result[uri] = DocumentAnalysis(
                uri=uri,
                version=version,
                actions=path_actions,
                diagnostics=list(map(_log_to_diagnostic, path_logs)),
            )
        return result

    def _get_file_contents(self) -> Mapping[Path, str]:
        result = {}
        # iterate text_documents directly here, as we are only concerned with documents
        # the workspace is tracking
        for uri, doc in self._workspace.text_documents.items():
            path = _uri_to_path(uri)
            if path is None:
                continue
            # exclude any in memory user modifications to lib files
            if self._is_in_package_path(path):
                continue
            result[path] = doc.source
        return result

    def _analyse_dependencies(self, modules: Mapping[str, SourceModule]) -> None:
        # TODO: how do we discover dependencies before they are opened in the workspace
        path_dependencies = defaultdict[Path, list[Path]](list)
        for module_id, module in modules.items():
            if module.path.suffix.lower() != ".py":
                continue
            non_stub_dependencies = [
                dep.path
                for dep_id in sorted(module.dependencies)
                if (dep := modules.get(dep_id)) is not None and dep.path.suffix.lower() == ".py"
            ]
            if non_stub_dependencies:
                logger.debug(
                    f"{module_id} depends on ({', '.join(map(str, non_stub_dependencies))})"
                )
            for dependency_path in non_stub_dependencies:
                path_dependencies[dependency_path].append(module.path)
        self._dependencies.update(path_dependencies)

    def _get_algopy_related_files(self, uris: Sequence[str]) -> Sequence[Path]:
        """
        Discover all paths containing puyapy compatible code that
        references or is referenced by the provided paths

        Filters out any paths that are in package_search_paths e.g. lib files
        """

        puyapy_paths = StableSet[Path]()
        for uri in uris:
            path = _uri_to_path(uri)
            if path is None:  # ignore non-file uris
                continue
            doc = self._workspace.get_text_document(uri)
            try:
                source = doc.source
            except UnicodeDecodeError:  # 🍝
                continue

            is_compatible = _is_puyapy_compatible_src(source)
            if is_compatible is None:
                logger.debug(f"could not parse {path}")
            elif is_compatible:
                logger.debug(f"found compatible source: {path}")
                puyapy_paths.add(path)
                for dependency in self._get_dependencies(path):
                    logger.debug(f"found dependent source: {dependency}")
                    puyapy_paths.add(dependency)
        return [path for path in puyapy_paths if not self._is_in_package_path(path)]

    def _is_in_package_path(self, path: Path) -> bool:
        return any(path.is_relative_to(search_path) for search_path in self._package_search_paths)

    def _get_dependencies(self, path: Path) -> Iterable[Path]:
        for dependency in self._dependencies.get(path, []):
            yield dependency
            yield from self._get_dependencies(dependency)


@attrs.frozen
class _AlgopySymbolResolver:
    _lines: Sequence[str]
    _symbols: dict[str, str]
    _import_block_end: int

    @classmethod
    def create(cls, module: SourceModule) -> typing.Self:
        module_symbols = dict[str, str]()
        for name, sym in module.node.names.items():
            fullname = sym.fullname or ""
            root_module, _, _ = fullname.partition(".")
            if root_module == "algopy":
                module_symbols[fullname] = name

        import_block_end = max(
            (
                coalesce(i.end_line, i.line) + 1
                for i in module.node.imports
                if i.is_top_level and not i.is_mypy_only and not i.is_unreachable
            ),
            default=1,
        )
        assert module.lines is not None, f"missing source for {module.name}"
        return cls(
            lines=module.lines,
            symbols=module_symbols,
            import_block_end=import_block_end,
        )

    def fix_to_code_action(self, uri: str, fix: code_fixes.CodeFix) -> lsp.CodeAction:
        title = ""
        edits = list[lsp.TextEdit | None]()
        loc = _source_location_to_range(fix.location)
        match fix.edit:
            case code_fixes.WrapWithSymbol(symbol=symbol):
                title = f"Use {_friendly_algopy(symbol)}"
                symbol_alias, maybe_add_import = self._resolve_symbol(symbol)
                edits = [
                    maybe_add_import,
                    lsp.TextEdit(range=lsp.Range(loc.end, loc.end), new_text=")"),
                    lsp.TextEdit(
                        range=lsp.Range(loc.start, loc.start), new_text=f"{symbol_alias}("
                    ),
                ]
            case code_fixes.ReplaceWithSymbol(symbol=symbol):
                title = f"Use {_friendly_algopy(symbol)}"

                symbol_alias, maybe_add_import = self._resolve_symbol(symbol)
                edits = [maybe_add_import, lsp.TextEdit(range=loc, new_text=symbol_alias)]
            case code_fixes.DecorateFunction(symbol=symbol):
                title = f"Use @{_friendly_algopy(symbol)}"

                symbol_alias, maybe_add_import = self._resolve_symbol(symbol)
                func_line = loc.start.line
                func_column = loc.start.character
                insert_line = func_line - 1
                insert_dec_pos = lsp.Position(line=insert_line, character=0)
                insert_dec_loc = lsp.Range(insert_dec_pos, insert_dec_pos)

                # use the same whitespace as function for consistent indentation
                whitespace = self._lines[func_line][:func_column]
                edits = [
                    maybe_add_import,
                    lsp.TextEdit(
                        range=insert_dec_loc,
                        new_text=f"\n{whitespace}@{symbol_alias}",
                    ),
                ]
            case code_fixes.AppendMember(member=member):
                title = f"Add {member}"
                append_loc = lsp.Range(start=loc.end, end=loc.end)
                edits = [lsp.TextEdit(range=append_loc, new_text=member)]
            case _:
                typing.assert_never(fix.edit)
        return lsp.CodeAction(
            title=title,
            kind=lsp.CodeActionKind.QuickFix,
            edit=lsp.WorkspaceEdit(
                changes={
                    uri: list(filter(None, edits)),
                }
            ),
        )

    def _resolve_symbol(self, full_name: str) -> tuple[str, lsp.TextEdit | None]:
        """
        Give the algopy import symbols in a document, return the appropriate alias for a
        fully qualified symbol in that document, and optionally an edit to add an import stmt
        """

        # if full symbol has an alias return that
        try:
            import_symbol = self._symbols[full_name]
        except KeyError:
            pass
        else:
            assert isinstance(import_symbol, str), "expected a symbol"
            return import_symbol, None

        # use the friendly name of the symbol so we don't attempt to use a private module
        full_name = _friendly_algopy(full_name)
        symbol_module, _, symbol = full_name.rpartition(".")

        try:
            module = self._symbols[symbol_module]
        except KeyError:
            # add an import for symbol
            line_pos = lsp.Position(line=self._import_block_end - 1, character=0)
            insert_at = lsp.Range(start=line_pos, end=line_pos)
            edit = lsp.TextEdit(
                new_text=f"from {symbol_module} import {symbol}\n", range=insert_at
            )
            return symbol, edit
        else:
            # if module itself was imported then reference symbol relative to that
            return f"{module}.{symbol}", None


_ALGOPY_FRIENDLY_SUB = re.compile(r"algopy\._[^.]+")


def _friendly_algopy(symbol: str) -> str:
    # algopy._private.foo => algopy.foo
    return _ALGOPY_FRIENDLY_SUB.sub("algopy", symbol)


def _log_to_diagnostic(log: Log) -> lsp.Diagnostic:
    assert log.location, "expected non none locations when converting to a diagnostic"
    return lsp.Diagnostic(
        message=log.message,
        severity=_log_level_to_severity(log.level),
        range=_source_location_to_range(log.location),
        source="puyapy",
    )


def _log_level_to_severity(log_level: LogLevel) -> lsp.DiagnosticSeverity:
    if log_level == LogLevel.error:
        return lsp.DiagnosticSeverity.Error
    if log_level == LogLevel.warning:
        return lsp.DiagnosticSeverity.Warning
    return lsp.DiagnosticSeverity.Information


def _source_location_to_range(loc: SourceLocation) -> lsp.Range:
    # positions lines are 0-indexed while SourceLocation are 1-indexed
    line = loc.line - 1
    column = loc.column or 0
    end_line = loc.end_line - 1
    end_column = loc.end_column
    if end_column is None:
        end_line += 1
        end_column = 0
    return lsp.Range(
        start=lsp.Position(line=line, character=column),
        end=lsp.Position(line=end_line, character=end_column),
    )


def _is_puyapy_compatible_src(src: str) -> bool | None:
    """Determines if the provided file contents contain puyapy compatible python"""

    # there are a few reasons for narrowing the source files we examine
    # 1.) Getting a bunch of PuyaPy errors from regular python code is not desirable
    # 2.) The MyPy parsing is slow, so we want to minimize what is being parsed
    # 3.) MyPy can actually sometimes crash on more complex code bases e.g. puyapy itself

    # compatible src will have either:
    # 1.) no imports, just constants. This case can be ignored as it will be picked up if
    #     referenced by algopy code # TODO: can we ignore this case?
    # 2.) an algopy import TODO: what about testing lib false positives?
    #     at present a puyapy compatible src that does anything of note will need to import algopy
    #     even if it is using a third party library as all methods must be decorated
    #     TODO: this assumption is not valid if a third-party module re-exports algopy
    #           under a different name
    # an initial check just looks for something that is likely to have an algopy import
    if "algopy" in src:
        # parse the src to be sure there is an algopy import
        try:
            module = ast.parse(src)
        except SyntaxError:
            # if the AST is unparseable, not worth processing further
            return None

        # NOTE: only considering top level imports
        for stmt in module.body:
            match stmt:
                case ast.Import(names=names) if any(alias.name == "algopy" for alias in names):
                    return True
                case ast.ImportFrom(module="algopy"):
                    return True
    return False


_IS_WINDOWS = platform.system() == "Windows"
_RE_DRIVE_LETTER_PATH = re.compile(r"^/[a-zA-Z]:")


def _uri_to_path(uri: str) -> Path | None:
    # scheme://netloc/path;parameters?query#fragment
    scheme, netloc, path, _, _, _ = urlparse(uri)

    if scheme != "file":
        return None

    path = unquote(path)  # vs code seems to urlquote the colon in windows drive names
    if netloc and path:
        value = f"//{netloc}{path}"
    elif _RE_DRIVE_LETTER_PATH.match(path):
        value = path[1:]
    else:
        value = path

    # an assumption is language server is only used on the same machine the uris refer to
    if _IS_WINDOWS:
        value = value.replace("/", "\\")
    return Path(value)


_CODE_FIXES = contextvars.ContextVar[list[code_fixes.CodeFix]]("_CODE_FIXES")


@contextlib.contextmanager
def _code_fix_context() -> Iterator[list[code_fixes.CodeFix]]:
    fixes = list[code_fixes.CodeFix]()
    token = _CODE_FIXES.set(fixes)
    try:
        yield fixes
    finally:
        _CODE_FIXES.reset(token)


def get_code_fix_context() -> list[code_fixes.CodeFix]:
    return _CODE_FIXES.get()
