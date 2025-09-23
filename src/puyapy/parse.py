import ast
import codecs
import enum
import functools
import itertools
import operator
import os
import shutil
import subprocess
import sys
import sysconfig
import typing
from collections import defaultdict, deque
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence, Set
from functools import cached_property
from importlib import metadata
from pathlib import Path

import attrs
from mypy.build import BuildManager, Graph, load_graph, process_graph, sorted_components
from mypy.error_formatter import ErrorFormatter
from mypy.errors import SHOW_NOTE_CODES, Errors, MypyError
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.nodes import MypyFile
from mypy.options import Options as MypyOptions
from mypy.plugins.default import DefaultPlugin
from mypy.typestate import reset_global_state, type_state
from mypy.util import decode_python_encoding, find_python_encoding, read_py_file
from mypy.version import __version__ as mypy_version
from packaging import version

from puya import log
from puya.errors import CodeError, ConfigurationError, InternalError
from puya.parse import SourceLocation
from puya.utils import make_path_relative_to_cwd, set_add
from puyapy import interpreter_data
from puyapy.find_sources import ResolvedSource, create_source_list
from puyapy.modulefinder import FindModuleCache, ModuleNotFoundReason

logger = log.get_logger(__name__)

# this should contain the lowest version number that this compiler does NOT support
# i.e. the next minor version after what is defined in stubs/pyproject.toml:project.version
MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("3.1.0")
MIN_SUPPORTED_ALGOPY_VERSION = version.parse(f"{MAX_SUPPORTED_ALGOPY_VERSION_EX.major}.0.0")


class SourceDiscoveryMechanism(enum.Enum):
    explicit = enum.auto()
    dependency = enum.auto()


@attrs.frozen
class SourceModule:
    name: str
    node: MypyFile
    path: Path
    lines: Sequence[str] | None
    discovery_mechanism: SourceDiscoveryMechanism
    is_typeshed_file: bool


@attrs.frozen
class ParseResult:
    mypy_options: MypyOptions
    ordered_modules: Mapping[str, SourceModule]
    """All discovered modules, topologically sorted by dependencies.
    The sort order is from leaves (nodes without dependencies) to
    roots (nodes on which no other nodes depend)."""

    @cached_property
    def sources_by_path(self) -> Mapping[Path, Sequence[str] | None]:
        return {s.path: s.lines for s in self.ordered_modules.values()}

    @cached_property
    def explicit_source_paths(self) -> Set[Path]:
        return {
            sm.path
            for sm in self.ordered_modules.values()
            if sm.discovery_mechanism == SourceDiscoveryMechanism.explicit
        }


def parse_python(
    paths: Sequence[Path],
    *,
    package_search_paths: Sequence[str] | typing.Literal["infer", "current"] = "current",
    excluded_subdir_names: Sequence[str] | None = None,
    # equivalent to a module-level singleton default, but at least it's self-contained here
    fs_cache: FileSystemCache = FileSystemCache(),  # noqa: B008
) -> ParseResult:
    """Generate the ASTs from the build sources, and all imported modules (recursively)"""

    sources_by_module_name = _create_and_check_source_list(
        paths, excluded_subdir_names=excluded_subdir_names
    )
    sources_by_module_name = dict(sorted(sources_by_module_name.items()))

    source_roots = [bs.base_dir for bs in sources_by_module_name.values()]
    source_roots.append(Path.cwd())

    python_path = tuple(dict.fromkeys(map(str, source_roots)))
    package_paths = tuple(_resolve_package_paths(package_search_paths))
    typeshed_paths = _typeshed_paths()
    mypy_search_paths = SearchPaths(
        python_path=python_path,
        package_path=package_paths,
        typeshed_path=typeshed_paths,
        mypy_path=(),
    )
    mypy_options = _get_mypy_options()
    mypy_build_sources = [
        BuildSource(path=str(bs.path), module=bs.module, base_dir=str(bs.base_dir))
        for bs in sources_by_module_name.values()
    ]
    fmc = FindModuleCache(
        mypy_search_paths, fs_cache, mypy_options, source_set=BuildSourceSet(mypy_build_sources)
    )
    module_data = _find_dependencies(sources_by_module_name.values(), fs_cache, fmc)
    mypy_build_sources = [
        BuildSource(
            path=str(md.source.path),  # TODO: figure out why omitting this fails in pytest only
            module=module,
            text=md.data,
            followed=md.followed,
        )
        for module, md in module_data.items()
    ]
    manager, graph = _mypy_build(mypy_build_sources, mypy_options, mypy_search_paths, fs_cache)
    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    manager.errors.set_file("<puyapy>", module=None, scope=None, options=mypy_options)
    missing_module_names = sources_by_module_name.keys() - manager.modules.keys()
    # Note: this shouldn't happen, provided we've successfully disabled the mypy cache
    assert (
        not missing_module_names
    ), f"mypy parse failed, missing modules: {', '.join(missing_module_names)}"

    # order modules by dependency, and also sanity check the contents
    ordered_modules = {}
    for scc_module_names in sorted_components(graph):
        for module_name in scc_module_names:
            module = manager.modules[module_name]
            assert (
                module_name == module.fullname
            ), f"mypy module mismatch, expected {module_name}, got {module.fullname}"
            assert module.path, f"no path for mypy module: {module_name}"
            module_path = Path(module.path).resolve()
            if module.is_stub:
                assert module.name not in module_data, "shouldn't have stub as input"
                file_bytes = fs_cache.read(str(module_path))
                _check_encoding(file_bytes, module_path)
                lines = decode_python_encoding(file_bytes).splitlines()
                ordered_modules[module_name] = SourceModule(
                    name=module_name,
                    node=module,
                    path=module_path,
                    lines=lines,
                    discovery_mechanism=SourceDiscoveryMechanism.dependency,
                    is_typeshed_file=module.is_typeshed_file(mypy_options),
                )
            elif module_path.is_dir():
                # this module is a module directory with no __init__.py, ie it contains
                # nothing and is only in the graph as a reference
                pass
            else:
                md = module_data[module_name]
                lines = md.data.splitlines()
                if md.followed:
                    discovery_mechanism = SourceDiscoveryMechanism.dependency
                else:
                    discovery_mechanism = SourceDiscoveryMechanism.explicit
                ordered_modules[module_name] = SourceModule(
                    name=module_name,
                    node=module,
                    path=module_path,
                    lines=lines,
                    discovery_mechanism=discovery_mechanism,
                    is_typeshed_file=False,
                )

    return ParseResult(mypy_options=mypy_options, ordered_modules=ordered_modules)


def _create_and_check_source_list(
    paths: Sequence[Path],
    *,
    excluded_subdir_names: Sequence[str] | None,
) -> Mapping[str, ResolvedSource]:
    build_sources = create_source_list(paths=paths, excluded_subdir_names=excluded_subdir_names)
    sources_by_module_name = dict[str, ResolvedSource]()
    sources_by_path = dict[Path, ResolvedSource]()
    duplicate_errors = list[ConfigurationError]()
    for bs in build_sources:
        existing = sources_by_module_name.setdefault(bs.module, bs)
        if existing != bs:
            duplicate_errors.append(
                ConfigurationError(
                    f"duplicate modules named in build sources:"
                    f" {make_path_relative_to_cwd(bs.path)} has same module name '{bs.module}'"
                    f" as {make_path_relative_to_cwd(existing.path)}"
                )
            )
        else:
            existing = sources_by_path.setdefault(bs.path, bs)
            if existing != bs:
                duplicate_errors.append(
                    ConfigurationError(
                        f"source path {make_path_relative_to_cwd(bs.path)}"
                        f" was resolved to multiple module names, ensure each path is only"
                        f" specified once or add top-level __init__.py files to mark package roots"
                    )
                )
    if duplicate_errors:
        raise ExceptionGroup("duplicate module errors", duplicate_errors)
    return sources_by_module_name


def _resolve_package_paths(
    package_search_paths: Sequence[str] | typing.Literal["infer", "current"],
) -> list[str]:
    match package_search_paths:
        case "current":
            sys_path = interpreter_data.get_sys_path()
        case "infer":
            sys_path = _infer_sys_path()
        case paths:
            sys_path = [os.path.abspath(p) for p in paths]  # noqa: PTH100
    logger.info(f"using python search path: {sys_path}")
    _check_algopy_version(sys_path)
    return sys_path


def _infer_sys_path() -> list[str]:
    # 1) Look for VIRTUAL_ENV as we want the venv puyapy is being run against (i.e. the project).
    # 2) If no venv is active, then fallback to the python interpreter on the system path.
    # 3) Failing that, use the current interpreter.
    # In the future, we might want to make it 1 -> 3 -> error, since searching the system path
    # for a python executable is just as likely to be incorrect as using the currently running one,
    # with extra downside that it's less predictable.
    # To continue to support the current method, we could add a --python-executable=... CLI option.
    try:
        venv = os.environ["VIRTUAL_ENV"]
    except KeyError:
        logger.debug("no active python virtual env")
        venv_scripts = None
    else:
        logger.debug(f"found active python virtual env: {venv}")
        venv_paths = sysconfig.get_paths(vars={"base": venv})
        venv_scripts = venv_paths["scripts"]
    for python in ("python3", "python"):
        logger.debug(f"attempting to locate '{python}' in {venv_scripts or 'system path'}")
        python_exe = shutil.which(python, path=venv_scripts)
        if python_exe:
            logger.debug(f"using python search path from interpreter: {python_exe}")
            return _get_sys_path(python_exe)
    if venv_scripts:
        raise ConfigurationError(
            "found an active python virtual env, but could not find an expected python interpreter"
        )
    logger.debug("using python search path from current interpreter")
    return interpreter_data.get_sys_path()


@attrs.frozen
class _ModuleData:
    source: ResolvedSource
    data: str
    dependencies: frozenset[str]
    tree: ast.Module
    followed: bool


def _find_dependencies(
    sources: Collection[ResolvedSource], fs_cache: FileSystemCache, fmc: FindModuleCache
) -> Mapping[str, _ModuleData]:
    result_by_id = dict[str, _ModuleData]()
    source_queue = deque(sources)
    queued_id_set = {rs.module for rs in source_queue}
    initial_source_ids = {rs.module for rs in sources}
    # module_paths = dict[str, Path | None]()
    while source_queue:
        rs = source_queue.popleft()
        assert rs.module not in result_by_id
        file_bytes = fs_cache.read(str(rs.path))
        _check_encoding(file_bytes, rs.path)
        source = decode_python_encoding(file_bytes)
        tree = ast.parse(
            source,
            rs.path,
            "exec",
            type_comments=True,
            feature_version=sys.version_info[:2],  # TODO: get this from target interpreter
        )
        visitor = _ImportCollector(rs)
        visitor.visit(tree)

        import_data = _all_imported_modules_in_file(
            rs, visitor.module_imports, visitor.from_imports
        )
        module_dep_ids = set[str]()
        for dep, is_definite in import_data.ordered:
            # if dep.id in module_paths:
            #     if is_definite or module_paths.get(dep.id) is not None:
            #         module_dep_ids.add(dep.id)
            #     continue  # already resolved or attempted to resolve
            path_or_reason = fmc.find_module(dep.id, fast_path=True)
            if isinstance(path_or_reason, str):
                module_dep_ids.add(dep.id)
                mod_path = Path(path_or_reason)
                # module_paths[dep.id] = mod_path
                assert mod_path == mod_path.resolve()  # TODO: REMOVE ME
                if mod_path.suffix == ".py" and set_add(queued_id_set, dep.id):
                    dep_rs = ResolvedSource(
                        path=mod_path,
                        module=dep.id,
                        base_dir=_infer_base_dir(mod_path, dep.id),
                    )
                    source_queue.append(dep_rs)
            else:  # noqa: PLR5501
                # module_paths[dep.id] = None
                if is_definite:
                    module_dep_ids.add(dep.id)
                    if path_or_reason is ModuleNotFoundReason.NOT_FOUND:
                        logger.error(
                            f'unable to resolve imported module "{dep.id}"', location=dep.loc
                        )
        result_by_id[rs.module] = _ModuleData(
            source=rs,
            data=source,
            tree=tree,
            dependencies=frozenset(module_dep_ids),
            followed=rs.module not in initial_source_ids,
        )
    return result_by_id


def _infer_base_dir(path: Path, module: str) -> Path:
    # /a/pkg/foo.py, pkg.foo -> /a/
    # /a/pkg/foo/__init__.py, pkg.foo -> /a/
    # /a/foo.py, foo -> /a/
    parts = module.count(".")
    if path.stem == "__init__" and path.suffix in (".py", ".pyi"):
        parts += 1
    return path.parents[parts]


@attrs.frozen
class ImportAs:
    loc: SourceLocation
    name: str
    as_name: str | None


@attrs.frozen
class ModuleImport:
    loc: SourceLocation
    names: list[ImportAs] = attrs.field(validator=attrs.validators.min_len(1))


@attrs.frozen
class FromImport:
    loc: SourceLocation
    module: str
    names: list[ImportAs] | None = attrs.field(
        validator=attrs.validators.optional(attrs.validators.min_len(1))
    )
    """if None, then import all (ie star import)"""


AnyImport = ModuleImport | FromImport


@attrs.define
class _ImportCollector(ast.NodeVisitor):
    source: ResolvedSource
    module_imports: list[ModuleImport] = attrs.field(factory=list, init=False)
    from_imports: list[FromImport] = attrs.field(factory=list, init=False)

    @typing.override
    def visit_Import(self, node: ast.Import) -> None:
        names = [
            ImportAs(
                name=alias.name,
                as_name=alias.asname,
                loc=self._loc(alias),
            )
            for alias in node.names
        ]
        self.module_imports.append(
            ModuleImport(
                names=names,
                loc=self._loc(node),
            )
        )

    @typing.override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        match node.names:
            case [ast.alias("*", None)]:
                names = None
            case _:
                names = list[ImportAs](
                    ImportAs(
                        name=alias.name,
                        as_name=alias.asname,
                        loc=self._loc(alias),
                    )
                    for alias in node.names
                )

        node_loc = self._loc(node)
        if not node.level:
            assert node.module
            module = node.module
        else:
            module = self._correct_relative_import(
                module=node.module, level=node.level, loc=node_loc
            )

        self.from_imports.append(
            FromImport(
                module=module,
                names=names,
                loc=node_loc,
            )
        )

    def _correct_relative_import(self, module: str | None, level: int, loc: SourceLocation) -> str:
        """Function to correct for relative imports."""
        file_id = self.source.module
        rel = level
        assert level > 0
        if self.source.path.stem == "__init__":
            rel -= 1
        if rel != 0:
            file_id = ".".join(file_id.split(".")[:-rel])

        if module:
            new_id = file_id + "." + module
        else:
            new_id = file_id

        if not new_id:
            # TODO: log and exit at end of discovery
            raise CodeError("no parent module, cannot perform relative import", loc)

        return new_id

    @typing.override
    def visit_If(self, node: ast.If) -> None:
        condition_value = _infer_condition_value(node.test, self.source.path)
        if condition_value is not ALWAYS_FALSE:
            for if_body_stmt in node.body:
                self.generic_visit(if_body_stmt)
        if condition_value is not ALWAYS_FALSE:
            for else_body_stmt in node.orelse:
                self.generic_visit(else_body_stmt)

    @typing.override
    def visit_IfExp(self, node: ast.IfExp) -> None:
        condition_value = _infer_condition_value(node.test, self.source.path)
        if condition_value is not ALWAYS_FALSE:
            self.generic_visit(node.body)
        if condition_value is not ALWAYS_TRUE:
            self.generic_visit(node.orelse)

    def _loc(self, node: ast.expr | ast.stmt | ast.alias) -> SourceLocation:
        return _ast_source_location(node, self.source.path)


def _ast_source_location(node: ast.expr | ast.stmt | ast.alias, file: Path) -> SourceLocation:
    return SourceLocation(file=file, line=node.lineno)


@enum.unique
class ConditionValue(enum.Enum):
    UNKNOWN = enum.auto()
    ALWAYS_TRUE = enum.auto()
    ALWAYS_FALSE = enum.auto()
    TYPE_CHECKING_TRUE = enum.auto()
    TYPE_CHECKING_FALSE = enum.auto()

    @cached_property
    def negated(self) -> "ConditionValue":
        match self:
            case ConditionValue.UNKNOWN:
                return TRUTH_VALUE_UNKNOWN
            case ConditionValue.ALWAYS_TRUE:
                return ALWAYS_FALSE
            case ConditionValue.ALWAYS_FALSE:
                return ALWAYS_TRUE
            case ConditionValue.TYPE_CHECKING_TRUE:
                return TYPE_CHECKING_FALSE
            case ConditionValue.TYPE_CHECKING_FALSE:
                return TYPE_CHECKING_TRUE


TRUTH_VALUE_UNKNOWN: typing.Final = ConditionValue.UNKNOWN
ALWAYS_TRUE: typing.Final = ConditionValue.ALWAYS_TRUE
ALWAYS_FALSE: typing.Final = ConditionValue.ALWAYS_FALSE
TYPE_CHECKING_TRUE: typing.Final = ConditionValue.TYPE_CHECKING_TRUE
TYPE_CHECKING_FALSE: typing.Final = ConditionValue.TYPE_CHECKING_FALSE


def _infer_condition_value(expr: ast.expr, file: Path) -> ConditionValue:
    match expr:
        case ast.Constant(value):
            if value:
                return ALWAYS_TRUE
            else:
                return ALWAYS_FALSE
        case ast.Attribute(_, "TYPE_CHECKING", ast.Load()):
            return TYPE_CHECKING_TRUE
        case ast.Name("TYPE_CHECKING", ast.Load()):
            return TYPE_CHECKING_TRUE
        case ast.UnaryOp(ast.Not(), operand):
            nested = _infer_condition_value(operand, file)
            return nested.negated
        case ast.BoolOp(ast.Or(), operands):
            results = {_infer_condition_value(operand, file) for operand in operands}
            if len(results) == 1:
                return results.pop()
            if ALWAYS_TRUE in results:
                return ALWAYS_TRUE
            elif TYPE_CHECKING_TRUE in results:
                return TYPE_CHECKING_TRUE
            elif results <= {ALWAYS_FALSE, TYPE_CHECKING_FALSE}:
                return ALWAYS_FALSE
            else:
                return TRUTH_VALUE_UNKNOWN
        case ast.BoolOp(ast.And(), operands):
            results = {_infer_condition_value(operand, file) for operand in operands}
            if len(results) == 1:
                return results.pop()
            if ALWAYS_FALSE in results:
                return ALWAYS_FALSE
            elif TYPE_CHECKING_FALSE in results:
                return TYPE_CHECKING_FALSE
            elif results <= {ALWAYS_TRUE, TYPE_CHECKING_TRUE}:
                return TYPE_CHECKING_TRUE
            else:
                return TRUTH_VALUE_UNKNOWN
        # TODO: ?
        # case ast.BinOp(left=ast.Constant(left), op=bin_op, right=ast.Constant(right)):
        #     try:
        #         op_impl = _AST_BIN_OP_TO_OP[type(op)]
        #     except KeyError:
        #         raise InternalError(
        #             f"unknown operator: {op}", _ast_source_location(expr, file)
        #         ) from None
        #     try:
        #         result = op_impl(left, right)
        #     except Exception:
        #         logger.error()
        #         return None
        #     else:
        #         return None
        # TODO: ast.Compare ?
        case _:
            return TRUTH_VALUE_UNKNOWN


_AST_BIN_OP_TO_OP: Mapping[type[ast.operator], Callable] = {  # type: ignore[type-arg]
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.BitAnd: operator.and_,
    ast.MatMult: operator.matmul,
}

_AST_CMP_TO_OP: Mapping[type[ast.cmpop], Callable] = {  # type: ignore[type-arg]
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


@attrs.frozen
class _Dependency:
    id: str
    loc: SourceLocation | None


@attrs.frozen
class _ImportData:
    source: ResolvedSource
    module_dependencies: list[_Dependency] = attrs.field(factory=list)
    maybe_module_dependencies: list[_Dependency] = attrs.field(factory=list)

    @cached_property
    def ordered(self) -> Sequence[tuple[_Dependency, bool]]:
        all_locs = defaultdict[str, list[SourceLocation]](list)
        definite_modules = set[str]()
        all_ids = set[str]()
        for dep in self.module_dependencies:
            assert dep.loc is not None
            all_locs[dep.id].append(dep.loc)
            definite_modules.add(dep.id)
            all_ids.add(dep.id)
        for dep in self.maybe_module_dependencies:
            assert dep.loc is not None
            all_locs[dep.id].append(dep.loc)
            all_ids.add(dep.id)
        # TODO: simplify this
        for ancestor_id in itertools.islice(_expand_ancestors(self.source.module), 1, None):
            ancestor_path = self.source.base_dir
            for part in ancestor_id.split("."):
                ancestor_path = ancestor_path / part
            ancestor_path = ancestor_path / "__init__.py"
            if ancestor_path.is_file():
                all_ids.add(ancestor_id)
                definite_modules.add(ancestor_id)

        result = []
        for id in sorted(all_ids, key=lambda x: (-x.count("."), x)):
            first_loc = min(all_locs[id], key=lambda y: y.line, default=None)
            result.append((_Dependency(id=id, loc=first_loc), id in definite_modules))
        return result


def _all_imported_modules_in_file(
    source: ResolvedSource,
    module_imports: list[ModuleImport],
    from_imports: list[FromImport],
) -> _ImportData:
    result = _ImportData(source)
    for mod_imp in module_imports:
        for alias in mod_imp.names:
            for module_id in _expand_ancestors(alias.name):
                result.module_dependencies.append(_Dependency(id=module_id, loc=mod_imp.loc))
    for from_imp in from_imports:
        from_module = from_imp.module
        for module_id in _expand_ancestors(from_module):
            result.module_dependencies.append(_Dependency(id=module_id, loc=from_imp.loc))
        # Also add any imported names that might be submodules.
        for alias in from_imp.names or ():
            maybe_submodule_id = from_module + "." + alias.name
            result.maybe_module_dependencies.append(
                _Dependency(id=maybe_submodule_id, loc=from_imp.loc)
            )
    return result


def _expand_ancestors(module_id: str) -> Iterator[str]:
    """
    Given a module_id like "a.b.c", will yield in turn: "a.b.c", "a.b", "a"
    """
    while module_id:
        yield module_id
        module_id, *_ = module_id.rpartition(".")


def _check_encoding(source: bytes, module_path: Path) -> None:
    module_rel_path = make_path_relative_to_cwd(module_path)
    module_loc = SourceLocation(file=module_path, line=1)
    # below is based on mypy/util.py:decode_python_encoding
    # check for BOM UTF-8 encoding
    if source.startswith(b"\xef\xbb\xbf"):
        return
    # otherwise look at first two lines and check if PEP-263 coding is present
    encoding, _ = find_python_encoding(source)
    # find the codec for this encoding and check it is utf-8
    codec = codecs.lookup(encoding)
    if codec.name != "utf-8":
        logger.warning(
            "UH OH SPAGHETTI-O's,"
            " darn tootin' non-utf8(?!) encoded file encountered:"
            f" {module_rel_path} encoded as {encoding}",
            location=module_loc,
        )


_CUSTOM_TYPESHED_PATH = Path(__file__).parent / "_typeshed"


def _get_mypy_options() -> MypyOptions:
    mypy_opts = MypyOptions()

    # improve mypy parsing performance by using a cut-down typeshed
    mypy_opts.custom_typeshed_dir = str(_CUSTOM_TYPESHED_PATH)
    mypy_opts.abs_custom_typeshed_dir = str(_CUSTOM_TYPESHED_PATH.resolve())

    # not required, we compute search paths ourselves
    mypy_opts.python_executable = None
    mypy_opts.preserve_asts = True
    mypy_opts.include_docstrings = True
    # next two options disable caching entirely.
    # slows things down but prevents intermittent failures.
    mypy_opts.incremental = False
    mypy_opts.cache_dir = os.devnull

    # strict mode flags, need to review these and all others too
    mypy_opts.disallow_any_generics = True
    mypy_opts.disallow_subclassing_any = True
    mypy_opts.disallow_untyped_calls = True
    mypy_opts.disallow_untyped_defs = True
    mypy_opts.disallow_incomplete_defs = True
    mypy_opts.check_untyped_defs = True
    mypy_opts.disallow_untyped_decorators = True
    mypy_opts.warn_redundant_casts = True
    mypy_opts.warn_unused_ignores = True
    mypy_opts.warn_return_any = True
    mypy_opts.strict_equality = True
    mypy_opts.strict_concatenate = True

    # disallow use of any
    mypy_opts.disallow_any_unimported = True
    # should be True but: https://github.com/python/mypy/issues/18770
    mypy_opts.disallow_any_expr = False
    mypy_opts.disallow_any_decorated = True
    mypy_opts.disallow_any_explicit = True

    mypy_opts.pretty = True  # show source in output

    return mypy_opts


def _mypy_build(
    sources: list[BuildSource],
    options: MypyOptions,
    search_paths: SearchPaths,
    fscache: FileSystemCache,
) -> tuple[BuildManager, Graph]:
    """Simple wrapper around mypy.build.build

    Makes it so that check errors and parse errors are handled the same (ie with an exception)
    """

    source_set = BuildSourceSet(sources)
    cached_read = fscache.read
    errors = Errors(options, read_source=lambda path: read_py_file(path, cached_read))
    plugin = DefaultPlugin(options)
    reporter = _LogReporter()

    def ignore_error(*_args: object) -> None:
        pass

    # Construct a build manager object to hold state during the build.
    #
    # Ignore current directory prefix in error messages.
    manager = BuildManager(
        data_dir=os.devnull,
        search_paths=search_paths,
        ignore_prefix=os.getcwd(),  # noqa: PTH109
        source_set=source_set,
        reports=None,
        options=options,
        version_id=mypy_version,
        plugin=plugin,
        plugins_snapshot={},
        errors=errors,
        error_formatter=reporter,
        flush_errors=ignore_error,
        fscache=fscache,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    reset_global_state()
    graph = load_graph(sources, manager)
    process_graph(graph, manager)
    type_state.reset_all_subtype_caches()
    return manager, graph


class _LogReporter(ErrorFormatter):
    """Formatter for basic JSON output format."""

    def report_error(self, error: MypyError) -> str:
        if error.file_path != os.devnull:
            match error.severity:
                case "note":
                    level = log.LogLevel.info
                case level_str:
                    level = log.LogLevel[level_str]
            resolved_path = Path(error.file_path).resolve()
            location = SourceLocation(
                file=resolved_path,
                line=max(error.line, 1),
                column=error.column if error.column >= 0 else None,
            )
            message = error.message
            if error.errorcode and (
                error.severity != "note" or error.errorcode in SHOW_NOTE_CODES
            ):
                # If note has an error code, it is related to a previous error. Avoid
                # displaying duplicate error codes.
                message = f"{message}  [{error.errorcode.code}]"
            logger.log(level, message, location=location)
        return ""


@functools.cache
def _typeshed_paths() -> tuple[str, str]:
    """Return default standard library search paths. Guaranteed to be normalised."""
    custom_typeshed_dir = _CUSTOM_TYPESHED_PATH.resolve()
    typeshed_dir = custom_typeshed_dir / "stdlib"
    versions_file = typeshed_dir / "VERSIONS"
    if not typeshed_dir.is_dir() or not versions_file.is_file():
        raise InternalError("puyapy install is corrupted - missing typeshed directories")
    # Get mypy-extensions stubs from typeshed, since we treat it as an
    # "internal" library, similar to typing and typing-extensions.
    mypy_extensions_dir = custom_typeshed_dir / "stubs" / "mypy-extensions"
    return str(typeshed_dir), str(mypy_extensions_dir)


def _get_sys_path(python_executable: str) -> list[str]:
    # Use subprocess to get the package directory of given Python
    # executable
    env = os.environ.copy() | {"PYTHONSAFEPATH": "1"}
    try:
        pyinfo_result = subprocess.run(  # noqa: S603
            [python_executable, interpreter_data.__file__],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as err:
        assert err.errno is not None
        reason = os.strerror(err.errno)
        raise ConfigurationError(
            f"invalid python executable '{python_executable}': {reason}"
        ) from err
    if pyinfo_result.stderr:
        raise ConfigurationError(pyinfo_result.stderr)
    if pyinfo_result.returncode != 0:
        raise InternalError(f"failed to inspect python environment for {python_executable}")
    sys_path = pyinfo_result.stdout.splitlines()
    return sys_path


_STUBS_PACKAGE_NAME = "algorand-python"


def _check_algopy_version(site_packages: list[str]) -> None:
    pkgs = metadata.Distribution.discover(name=_STUBS_PACKAGE_NAME, path=site_packages)
    try:
        (algopy,) = pkgs
    except ValueError:
        logger.warning("could not determine algopy version")
        return
    algopy_version = version.parse(algopy.version)
    logger.debug(f"found algopy: {algopy_version}")

    if not (MIN_SUPPORTED_ALGOPY_VERSION <= algopy_version < MAX_SUPPORTED_ALGOPY_VERSION_EX):
        logger.warning(
            f"{_STUBS_PACKAGE_NAME} version {algopy_version} is outside the supported range:"
            f" >={MIN_SUPPORTED_ALGOPY_VERSION}, <{MAX_SUPPORTED_ALGOPY_VERSION_EX}",
            important=True,
            related_lines=[
                "This will cause typing errors if there are incompatibilities in the API used.",
                "Please update your algorand-python package to be in the supported range.",
            ],
        )
