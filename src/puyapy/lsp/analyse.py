import ast
import contextlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import attrs
import mypy.nodes
from pygls.workspace import Workspace

from puya.errors import log_exceptions
from puya.log import Log, LogLevel, get_logger, logging_context
from puya.parse import SourceLocation
from puya.service import AnalyseParams, PuyaClient
from puya.utils import StableSet
from puyapy.awst_build.main import transform_ast
from puyapy.lsp.code_fixes import CodeFix, code_fix_context
from puyapy.options import PuyaPyOptions
from puyapy.parse import ParseResult, SourceProvider, parse_python

logger = get_logger(__name__)


@attrs.frozen
class ImportedModule:
    """e.g import algopy.arc4 as bar"""

    alias: str


@attrs.frozen
class ImportedFrom:
    """Indicates a module used to import from"""

    insert_at: SourceLocation
    """Location to insert an additional import"""
    module_id: str


@attrs.frozen
class ImportAll:
    """Indicates all symbols in the module were imported"""


@attrs.frozen
class ImportSymbol:
    """e.g. from algopy import UInt64 as Foo"""

    alias: str


AlgopyImport = ImportedModule | ImportedFrom | ImportAll | ImportSymbol


@attrs.frozen
class DocumentAnalysis:
    version: int | None
    logs: list[Log] = attrs.field(factory=list)
    fixes: list[CodeFix] = attrs.field(factory=list)
    symbols: dict[str, AlgopyImport] = attrs.field(factory=dict)

    def get_alias_and_import_insert(
        self, full_name: str
    ) -> str | tuple[str, str, SourceLocation] | None:
        # if full symbol has an alias return that
        try:
            import_symbol = self.symbols[full_name]
        except KeyError:
            pass
        else:
            assert isinstance(import_symbol, ImportSymbol), "expected a symbol"
            return import_symbol.alias
        try:
            symbol_module, symbol = full_name.rsplit(".", maxsplit=1)
        except ValueError:
            # symbols should be scoped to a module?
            # give up
            return None

        try:
            module_alias = self.symbols[symbol_module]
        except KeyError:
            pass
        else:
            # if module was import all then can just use symbol
            if isinstance(module_alias, ImportAll):
                return symbol
            # if module itself was imported then can use that
            elif isinstance(module_alias, ImportedModule):
                return f"{module_alias.alias}.{symbol}"
            elif isinstance(module_alias, ImportedFrom):
                return symbol, f"from {symbol_module} import {symbol}", module_alias.insert_at
        return None


@attrs.define
class CodeAnalyser:
    """Handles analysing specified paths, and tracking dependencies between modules"""

    _python_executable: Path
    _puya_service: PuyaClient
    _workspace: Workspace
    _dependencies: dict[Path, list[Path]] = attrs.field(factory=dict)
    """
    Dependencies are inverted to reflect what files should also be analysed when a file changes

    e.g. if module A imports module B then mapping will be
    { B: [A] }
    """
    _source_provider: SourceProvider = attrs.field()

    @_source_provider.default
    def _source_provider_factory(self) -> SourceProvider:
        return _WorkspaceSourceProvider(self._workspace)

    async def analyse(self, uris: Sequence[str]) -> Mapping[str, DocumentAnalysis]:
        logger.debug(f"parse: uris={', '.join(uris)}")

        # get all algopy paths and related dependencies from supplied uri
        paths = self._get_algopy_related_files(uris)

        logger.debug(f"parse: algopy related paths={', '.join(map(str, paths))}")
        if not paths:
            return {}
        options = PuyaPyOptions(
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
        logs, fixes, uri_symbols = await self._parse_and_log(options)
        analysis = {
            p.as_uri(): DocumentAnalysis(self._workspace.get_text_document(p.as_uri()).version)
            for p in paths
        }
        for uri, symbols in uri_symbols.items():
            if uri in analysis:
                analysis[uri].symbols.update(symbols)

        for log in logs:
            if log.level <= LogLevel.info or log.location is None or log.location.file is None:
                continue
            uri = log.location.file.as_uri()
            # only concerned with log output of input files
            with contextlib.suppress(KeyError):
                analysis[uri].logs.append(log)

        for fix in fixes:
            assert fix.loc.file is not None
            uri = fix.loc.file.as_uri()
            # only concerned with fixes of input files
            with contextlib.suppress(KeyError):
                analysis[uri].fixes.append(fix)
        return analysis

    async def _parse_and_log(
        self, puyapy_options: PuyaPyOptions
    ) -> tuple[Sequence[Log], Sequence[CodeFix], dict[str, dict[str, AlgopyImport]]]:
        # parse Typed AST
        try:
            with logging_context(output_log=False) as parse_ctx:
                parse_result = parse_python(
                    puyapy_options.paths,
                    python_executable=self._python_executable,
                    source_provider=self._source_provider,
                )
        except Exception as ex:
            # TODO: how should we recover if mypy has critical errors
            logger.debug(f"error during parsing: {ex}")
            return [], [], {}
        uri_symbols = self._analyse_imports(parse_result)
        logs = list(parse_ctx.logs)
        fixes = list[CodeFix]()
        # lower Typed AST to AWST
        if not parse_ctx.num_errors:
            logger.debug("transforming AST to AWST")
            with (
                logging_context(output_log=False) as awst_ctx,
                log_exceptions(),
                code_fix_context() as fixes,
            ):
                awst_ctx.source_provider = parse_result.source_provider
                awst, compilation_targets = transform_ast(parse_result, puyapy_options)
            logs.extend(awst_ctx.logs)
            # if no errors, then attempt to lower further and extend diagnostics with any
            # further results

            # lower AWST to TEAL
            logger.debug("lowering AWST to TEAL")
            if not awst_ctx.num_errors:
                response = await self._puya_service.analyse_async(AnalyseParams(awst=awst))
                logs.extend(response.logs)
        logger.debug("parse and log complete")
        return logs, fixes, uri_symbols

    def _analyse_imports(self, parse_result: ParseResult) -> dict[str, dict[str, AlgopyImport]]:
        # TODO: how do we discover dependencies before they are opened in the workspace
        modules = parse_result.ordered_modules
        path_dependencies = defaultdict[Path, list[Path]](list)
        uri_algopy_symbols = dict[str, dict[str, AlgopyImport]]()
        for module_id, module in modules.items():
            uri = module.path.as_uri()
            dependencies = StableSet[str]()
            symbols = dict[str, AlgopyImport]()
            for import_ in module.node.imports:
                if isinstance(import_, mypy.nodes.Import):
                    for id_, alias in import_.ids:
                        # modules directly imported can be added to the dependency graph
                        dependencies.add(id_)
                        if id_.startswith("algopy.") or id_ == "algopy":
                            symbols[id_] = ImportedModule(alias=alias or id_)
                elif isinstance(import_, mypy.nodes.ImportFrom):
                    # import from can contain modules or other symbols
                    # update graph with any names that are in modules
                    # also need to resolve relative imports to full namespace
                    import_module_id = _resolve_relative_import(module_id, import_)
                    if import_module_id == import_.id:
                        dependencies.add(import_module_id)

                    insert_at = SourceLocation(
                        file=module.path,
                        line=(import_.end_line or import_.line) + 1,
                        column=0,
                    )
                    symbols[import_module_id] = ImportedFrom(
                        module_id=import_module_id, insert_at=insert_at
                    )
                    for name, alias in import_.names:
                        maybe_sub_module_id = f"{import_module_id}.{name}"
                        symbols[maybe_sub_module_id] = ImportSymbol(alias=alias or name)
                        if maybe_sub_module_id in modules:
                            dependencies.add(maybe_sub_module_id)
                elif isinstance(import_, mypy.nodes.ImportAll):
                    import_module_id = _resolve_relative_import(module_id, import_)
                    # for import * indicate the module alias as an empty string
                    symbols[import_module_id] = ImportAll()
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
                uri_algopy_symbols[uri] = symbols
        self._dependencies.update(path_dependencies)
        return uri_algopy_symbols

    def _get_algopy_related_files(self, uris: Sequence[str]) -> Sequence[Path]:
        """
        Discover all paths containing puyapy compatible code that
        references or is referenced by the provided paths
        """

        puyapy_paths = StableSet[Path]()
        for uri in uris:
            doc = self._workspace.get_text_document(uri)
            try:
                source = doc.source
            except UnicodeDecodeError:  # 🍝
                continue

            if _is_puyapy_compatible_src(uri, source):
                logger.debug(f"found compatible source: {uri}")
                path_str = doc.path
                assert path_str is not None
                path = Path(path_str)
                puyapy_paths.add(path)
                for dependency in self._get_dependencies(path):
                    logger.debug(f"found dependent source: {dependency}")
                    puyapy_paths.add(dependency)
        return list(puyapy_paths)

    def _get_dependencies(self, path: Path) -> Iterable[Path]:
        for dependency in self._dependencies.get(path, []):
            yield dependency
            yield from self._get_dependencies(dependency)


def _resolve_relative_import(
    module_id: str, import_: mypy.nodes.ImportFrom | mypy.nodes.ImportAll
) -> str:
    if import_.relative:
        import_module_id = module_id
        if import_.relative > 1:
            traverse_up = import_.relative - 1
            import_module_id = ".".join(import_module_id.split(".")[:-traverse_up])
        if import_.id:
            import_module_id = f"{import_module_id}.{import_.id}"
    else:
        import_module_id = import_.id
    return import_module_id


def _is_puyapy_compatible_src(uri: str, src: str) -> bool:
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
            logger.debug(f"could not parse: {uri}")
            return False

        # NOTE: only considering top level imports
        for stmt in module.body:
            match stmt:
                case ast.Import(names=names) if any(alias.name == "algopy" for alias in names):
                    return True
                case ast.ImportFrom(module="algopy"):
                    return True
    return False


@attrs.frozen
class _WorkspaceSourceProvider(SourceProvider):
    _workspace: Workspace

    def get_source(self, path: Path) -> list[str] | None:
        uri = path.as_uri()
        try:
            source = self._workspace.text_documents[uri].source
        except KeyError:
            return None
        assert isinstance(source, str)
        return source.splitlines()
