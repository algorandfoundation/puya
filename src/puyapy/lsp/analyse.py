import ast
import contextlib
import contextvars
import platform
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from urllib.parse import unquote, urlparse

import attrs
import mypy.nodes
from pygls.workspace import Workspace

from puya.compile import awst_to_teal
from puya.errors import PuyaExitError, log_exceptions
from puya.log import Log, LogLevel, get_logger, logging_context
from puya.utils import StableSet, coalesce, get_cwd, set_cwd
from puyapy.awst_build.main import transform_ast
from puyapy.code_fixes import CodeFix
from puyapy.options import PuyaPyOptions
from puyapy.parse import ParseResult, parse_python

logger = get_logger(__name__)


@attrs.frozen
class DocumentAnalysis:
    uri: str
    """uri of document"""
    version: int | None
    """version of document when it was analysed"""
    symbols: dict[str, str | int]
    """a mapping of symbols (incl. modules) to their aliases or the line after their import stmt"""
    logs: list[Log]
    """warning or errors present in document"""
    fixes: list[CodeFix]
    """possible fixes suggested in document"""


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
            analysis_results = self._compile_and_capture_symbols_fixes_and_logs(paths)

        # if there are no results then there was a parsing error so don't update anything
        if analysis_results is None:
            return {}
        # need to be able to map Paths back to their original uri's as simply calling
        # .as_uri() may not give back the original uri
        path_to_uri_version = dict[Path, tuple[str, int | None]]()
        for uri, doc in self._workspace.text_documents.items():
            path = _uri_to_path(uri)
            if path is not None:
                path_to_uri_version[path] = uri, doc.version

        analysis = {}
        for path in paths:
            try:
                uri, version = path_to_uri_version[path]
            except KeyError:
                uri = path.as_uri()
                version = None
            symbols, fixes, logs = analysis_results[path]
            analysis[uri] = DocumentAnalysis(
                uri=uri,
                version=version,
                symbols=symbols,
                fixes=fixes,
                logs=logs,
            )

        return analysis

    def _compile_and_capture_symbols_fixes_and_logs(
        self, paths: Sequence[Path]
    ) -> dict[Path, tuple[dict[str, str | int], list[CodeFix], list[Log]]] | None:
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
            return None
        logger.debug("AST parse complete")
        symbols = self._analyse_imports(parse_result)
        fixes = list[CodeFix]()
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
        result = {}
        for path in puyapy_options.paths:
            path_symbols = symbols.get(path, {})
            path_fixes = [fix for fix in fixes if fix.location.file == path]
            path_logs = [
                log
                for log in logs
                if log.level > LogLevel.info and log.location and log.location.file == path
            ]
            result[path] = path_symbols, path_fixes, path_logs
            logger.debug(
                f"analysis found {path} has"
                f" {len(path_symbols)} symbols {len(path_fixes)} fixes, {len(path_logs)} logs"
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

    def _analyse_imports(self, parse_result: ParseResult) -> dict[Path, dict[str, str | int]]:
        # TODO: how do we discover dependencies before they are opened in the workspace
        modules = parse_result.ordered_modules
        path_dependencies = defaultdict[Path, list[Path]](list)
        path_algopy_symbols = dict[Path, dict[str, str | int]]()
        for module_id, module in modules.items():
            if module.is_typeshed_file:
                continue
            dependencies = StableSet[str]()
            symbols = dict[str, str | int]()
            for import_ in module.node.imports:
                if isinstance(import_, mypy.nodes.Import):
                    for id_, alias in import_.ids:
                        # modules directly imported can be added to the dependency graph
                        dependencies.add(id_)
                        if id_.startswith("algopy.") or id_ == "algopy":
                            symbols[id_] = alias or id_
                elif isinstance(import_, mypy.nodes.ImportFrom):
                    # import from can contain modules or other symbols
                    # update graph with any names that are in modules
                    # also need to resolve relative imports to full namespace
                    import_module_id = _correct_relative_import(
                        file_id=module_id, file_path=module.path, import_=import_
                    )
                    dependencies.add(import_module_id)

                    symbols[import_module_id] = coalesce(import_.end_line, import_.line) + 1
                    for name, alias in import_.names:
                        maybe_sub_module_id = f"{import_module_id}.{name}"
                        symbols[maybe_sub_module_id] = alias or name
                        if maybe_sub_module_id in modules:
                            dependencies.add(maybe_sub_module_id)
                elif isinstance(import_, mypy.nodes.ImportAll):
                    import_module_id = _correct_relative_import(
                        file_id=module_id, file_path=module.path, import_=import_
                    )
                    symbols[import_module_id] = ""
                    # include any known submodules as a dependency
                    sub_module_pattern = re.compile(f"{import_module_id}\\.\\w+$")
                    for maybe_sub_module_id in modules:
                        if sub_module_pattern.match(maybe_sub_module_id):
                            dependencies.add(maybe_sub_module_id)
            # convert module ids to paths
            module_path = module.path
            non_stub_dependencies = [
                dep
                for dep in dependencies
                if dep in modules
                and not modules[dep].is_typeshed_file
                and not modules[dep].node.is_stub
            ]
            if non_stub_dependencies:
                logger.debug(f"{module_id} depends on ({', '.join(non_stub_dependencies)})")
            for dependency in non_stub_dependencies:
                dependency_path = modules[dependency].path
                path_dependencies[dependency_path].append(module_path)
            if symbols:
                path_algopy_symbols[module_path] = symbols
        self._dependencies.update(path_dependencies)
        return path_algopy_symbols

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


def _correct_relative_import(
    *, file_id: str, file_path: Path, import_: mypy.nodes.ImportFrom | mypy.nodes.ImportAll
) -> str:
    """Function to correct for relative imports."""
    if import_.relative:
        rel = import_.relative
        assert rel > 0
        if file_path.stem == "__init__":
            rel -= 1
        if rel != 0:
            file_id = ".".join(file_id.split(".")[:-rel])

        if import_.id:
            new_id = file_id + "." + import_.id
        else:
            new_id = file_id

        logger.debug(f"resolved relative import {import_} to {new_id}")
        return new_id
    else:
        import_module_id = import_.id
    return import_module_id


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


_CODE_FIXES = contextvars.ContextVar[list[CodeFix]]("_CODE_FIXES")


@contextlib.contextmanager
def _code_fix_context() -> Iterator[list[CodeFix]]:
    fixes = list[CodeFix]()
    token = _CODE_FIXES.set(fixes)
    try:
        yield fixes
    finally:
        _CODE_FIXES.reset(token)


def get_code_fix_context() -> list[CodeFix]:
    return _CODE_FIXES.get()
