import ast
import codecs
import enum
import functools
import operator
import os
import shutil
import subprocess
import sys
import sysconfig
import typing
from collections import deque
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence, Set
from functools import cached_property
from importlib import metadata
from pathlib import Path

import attrs
from mypy.build import (
    BuildManager,
    load_graph,
    order_ascc,
    process_stale_scc,
    sorted_components,
)
from mypy.error_formatter import ErrorFormatter
from mypy.errors import SHOW_NOTE_CODES, Errors, MypyError
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.nodes import MypyFile
from mypy.options import Options as MypyOptions
from mypy.plugins.default import DefaultPlugin
from mypy.typestate import reset_global_state, type_state
from mypy.util import decode_python_encoding, find_python_encoding, hash_digest, read_py_file
from mypy.version import __version__ as mypy_version
from packaging import version

from puya import log
from puya.errors import CodeError, ConfigurationError, InternalError
from puya.parse import SourceLocation
from puya.utils import make_path_relative_to_cwd, set_add
from puyapy import interpreter_data
from puyapy.find_sources import ResolvedSource, create_source_list
from puyapy.modulefinder import FindModuleCache

logger = log.get_logger(__name__)

# this should contain the lowest version number that this compiler does NOT support
# i.e. the next minor version after what is defined in stubs/pyproject.toml:project.version
MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("3.4.0")
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
    dependencies: frozenset[str]


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
    file_contents: Mapping[Path, str] | None = None,
    excluded_subdir_names: Sequence[str] | None = None,
) -> ParseResult:
    """Generate the ASTs from the build sources, and all imported modules (recursively)"""

    sources_by_module_name, package_roots = _create_and_check_source_list(
        paths, excluded_subdir_names=excluded_subdir_names
    )
    sources_by_module_name = dict(sorted(sources_by_module_name.items()))

    package_paths = _resolve_package_paths(package_search_paths)
    fs_cache = FileSystemCache()
    # prime the cache with supplied content overrides, so that mypy reads from our data instead
    if file_contents:
        for content_path, content in file_contents.items():
            fn = str(content_path)
            data = content.encode("utf-8")
            fs_cache.stat_or_none(fn)
            fs_cache.read_cache[fn] = data
            fs_cache.hash_cache[fn] = hash_digest(data)
    fmc = FindModuleCache(
        package_paths=package_paths,
        package_roots=package_roots,
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
    mypy_options = _get_mypy_options()
    typeshed_paths, algopy_sources = _typeshed_paths()

    mypy_search_paths = SearchPaths(
        python_path=(),
        package_path=(),
        typeshed_path=tuple(map(str, typeshed_paths)),
        mypy_path=(),
    )
    manager, sccs = _mypy_build(
        mypy_build_sources, mypy_options, mypy_search_paths, fs_cache, algopy_sources
    )
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
    for scc_module_names in sccs:
        for module_name in sorted(scc_module_names):
            module = manager.modules[module_name]
            state = graph[module_name]
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
                    dependencies=frozenset(state.dependencies_set),
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
                    dependencies=frozenset(state.dependencies_set),
                )

    return ParseResult(mypy_options=mypy_options, ordered_modules=ordered_modules)


def _create_and_check_source_list(
    paths: Sequence[Path],
    *,
    excluded_subdir_names: Sequence[str] | None,
) -> tuple[Mapping[str, ResolvedSource], Mapping[str, Path]]:
    build_sources = create_source_list(paths=paths, excluded_subdir_names=excluded_subdir_names)
    sources_by_module_name = dict[str, ResolvedSource]()
    sources_by_path = dict[Path, ResolvedSource]()
    base_dir_by_pkg = dict[str, Path | None]()
    package_roots = dict[str, Path]()
    errors = list[ConfigurationError]()
    for bs in build_sources:
        existing = sources_by_module_name.setdefault(bs.module, bs)
        if existing != bs:
            errors.append(
                ConfigurationError(
                    f"duplicate modules named in build sources:"
                    f" {make_path_relative_to_cwd(bs.path)} has same module name '{bs.module}'"
                    f" as {make_path_relative_to_cwd(existing.path)}"
                )
            )
        else:
            existing = sources_by_path.setdefault(bs.path, bs)
            if existing != bs:
                errors.append(
                    ConfigurationError(
                        f"source path {make_path_relative_to_cwd(bs.path)}"
                        f" was resolved to multiple module names, ensure each path is only"
                        f" specified once or add top-level __init__.py files to mark package roots"
                    )
                )
            else:
                pkg = bs.module.partition(".")[0]
                # TODO: use just package_roots instead of also having base_dir_by_pkg
                existing_base = base_dir_by_pkg.setdefault(pkg, bs.base_dir)
                if existing_base == bs.base_dir:
                    if bs.base_dir is None:
                        assert bs.path.suffix == ".py" and not bs.path.name.startswith("__init__.")
                        package_roots[pkg] = bs.path
                    else:
                        init_path = bs.base_dir / pkg / "__init__.py"
                        assert init_path.is_file()
                        package_roots[pkg] = init_path
                else:
                    if existing_base is None:
                        conflict_msg = (
                            f"module '{bs.module}' appears to be a package"
                            f" rooted at {bs.base_dir},"
                            f" which conflicts with a standalone module '{pkg}'"
                        )
                    elif bs.base_dir is None:
                        conflict_msg = (
                            f"module '{bs.module}' appears to be a standalone module,"
                            f" which conflicts with a package of the same name"
                            f" rooted at {existing_base}"
                        )
                    else:
                        conflict_msg = (
                            f"module '{bs.module}' appears to be a package"
                            f" rooted at {bs.base_dir},"
                            f" which conflicts with existing package root {existing_base}"
                        )
                    errors.append(ConfigurationError(conflict_msg))
    if errors:
        raise ExceptionGroup("source conflicts", errors)
    return sources_by_module_name, package_roots


def _resolve_package_paths(
    package_search_paths: Sequence[str] | typing.Literal["infer", "current"],
) -> list[Path]:
    match package_search_paths:
        case "current":
            sys_path = interpreter_data.get_sys_path()
        case "infer":
            sys_path = _infer_sys_path()
        case paths:
            sys_path = [os.path.abspath(p) for p in paths]  # noqa: PTH100
    logger.info(f"using python search path: {sys_path}")
    _check_algopy_version(sys_path)
    return [Path(p) for p in sys_path]


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
            return get_sys_path(python_exe)
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


_ALLOWED_STUBS: typing.Final = frozenset(("algopy", "abc", "typing", "typing_extensions"))


def _find_dependencies(
    sources: Collection[ResolvedSource], fs_cache: FileSystemCache, fmc: FindModuleCache
) -> Mapping[str, _ModuleData]:
    result_by_id = dict[str, _ModuleData]()
    source_queue = deque(sources)
    queued_id_set = {rs.module for rs in source_queue}
    initial_source_ids = {rs.module for rs in sources}
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
        dependencies = _resolve_import_dependencies(
            rs,
            fmc,
            module_imports=visitor.module_imports,
            from_imports=visitor.from_imports,
        )
        module_dep_ids = set[str]()
        for dep in dependencies:
            mod_path = dep.path
            module_dep_ids.add(dep.module_id)
            assert mod_path == mod_path.resolve()  # TODO: REMOVE ME
            # assert mod_path.suffix == ".py", mod_path  # TODO: reinstate me?
            if mod_path.suffix == ".py" and set_add(queued_id_set, dep.module_id):
                dep_rs = ResolvedSource(
                    path=mod_path,
                    module=dep.module_id,
                    base_dir=_infer_base_dir(mod_path, dep.module_id),
                )
                source_queue.append(dep_rs)
        module_dep_ids.discard(rs.module)  # TODO: is this required?
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
    module_id: str
    path: Path
    loc: SourceLocation | None
    implicit: bool


def _resolve_import_dependencies(
    source: ResolvedSource,
    fmc: FindModuleCache,
    *,
    module_imports: Sequence[ModuleImport],
    from_imports: Sequence[FromImport],
) -> list[_Dependency]:
    dependencies = []
    import_base_dir = source.base_dir or source.path.parent
    for mod_imp in module_imports:
        for alias in mod_imp.names:
            if alias.name.partition(".")[0] in _ALLOWED_STUBS:
                continue

            path_str = fmc.find_module(alias.name, alias.loc, import_base_dir=import_base_dir)
            if path_str is None:
                continue

            path = Path(path_str)
            dependencies.append(_Dependency(alias.name, path, alias.loc, implicit=False))
            for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
                alias.name, path
            ):
                dependencies.append(
                    _Dependency(ancestor_module_id, ancestor_init_path, alias.loc, implicit=True)
                )
    for from_imp in from_imports:
        module_id = from_imp.module
        if module_id.partition(".")[0] in _ALLOWED_STUBS:
            continue

        # note: there is a case that this doesn't handle, where module_id points to a directory of
        # an implicit namespace package without an __init__.py, in that case however a from-import
        # behaves differently depending on what has already been imported, which adds significant
        # complexity here - so just error altogether for now.
        path_str = fmc.find_module(module_id, from_imp.loc, import_base_dir=import_base_dir)
        if path_str is None:
            continue

        path = Path(path_str)
        sub_deps = []
        any_unresolved = False
        # If not resolving to an init file, then all imported symbols must be from that file.
        # Similarly, when a `from x.y import *` resolves to x/y/__init__.py, all imported symbols
        # must be from that file.
        if path.name == "__init__.py" and from_imp.names is not None:
            # There are two complications at this point:
            # The first is that if x/__init__.py defines a variable foo, but there is also a
            # file x/foo.py, then `from x import foo` will actually refer to the variable.
            # This is okay, at worst we create spurious dependencies.
            # The second complication is that symbols in the __init__.py could be modules from
            # another location, this is okay because as long as there is a dependency to the
            # __init__.py file then the importer will also depend transitively on that imported
            # module.
            mod_dir = path.parent
            for alias in from_imp.names:
                maybe_path = mod_dir / alias.name
                if maybe_path.is_dir():
                    maybe_path = maybe_path / "__init__.py"
                else:
                    maybe_path = maybe_path.with_suffix(".py")
                if maybe_path.is_file():
                    submodule_id = ".".join((module_id, alias.name))
                    sub_deps.append(
                        _Dependency(submodule_id, maybe_path, alias.loc, implicit=False)
                    )
                else:
                    any_unresolved = True
        dependencies.append(
            _Dependency(module_id, path, from_imp.loc, implicit=not any_unresolved)
        )
        dependencies.extend(sub_deps)
        for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(module_id, path):
            dependencies.append(
                _Dependency(ancestor_module_id, ancestor_init_path, from_imp.loc, implicit=True)
            )

    for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
        source.module, source.path
    ):
        dependencies.append(
            _Dependency(ancestor_module_id, ancestor_init_path, None, implicit=True)
        )
    return dependencies


def _expand_init_dependencies(module_id: str, path: Path) -> Iterator[tuple[str, Path]]:
    """Check that all packages containing id have a __init__ file."""
    ancestors = list(_expand_ancestors(module_id))
    if path.name == "__init__.py":
        path = path.parent
    else:
        ancestors.pop(0)
    for ancestor in ancestors:
        path = path.parent
        init_file = path / "__init__.py"
        if init_file.is_file():
            yield ancestor, init_file


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
    mypy_opts.fast_module_lookup = True  # look modules up in source set first

    return mypy_opts


def _mypy_build(
    sources: list[BuildSource],
    options: MypyOptions,
    search_paths: SearchPaths,
    fscache: FileSystemCache,
    algopy_sources: Mapping[str, Path],
) -> tuple[BuildManager, list[Set[str]]]:
    """Simple wrapper around mypy.build.build

    Makes it so that check errors and parse errors are handled the same (ie with an exception)
    """
    algopy_build_sources = [
        BuildSource(path=str(v), module=k, followed=True) for k, v in algopy_sources.items()
    ]
    source_set = BuildSourceSet(sources + algopy_build_sources)
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
    for algopy_module, algopy_module_path in algopy_sources.items():
        graph[algopy_module].ignore_all = True
        manager.errors.ignored_files.add(str(algopy_module_path))
    # process_graph(graph, manager)
    sccs = sorted_components(graph)
    # We're processing SCCs from leaves (those without further
    # dependencies) to roots (those from which everything else can be
    # reached).
    for ascc in sccs:
        # Order the SCC's nodes using a heuristic.
        # Note that ascc is a set, and scc is a list.
        scc = order_ascc(graph, ascc)
        # Make the order of the SCC that includes 'builtins' and 'typing',
        # among other things, predictable. Various things may  break if
        # the order changes.
        if "builtins" in ascc:
            scc = sorted(scc, reverse=True)
            # If builtins is in the list, move it last.  (This is a bit of
            # a hack, but it's necessary because the builtins module is
            # part of a small cycle involving at least {builtins, abc,
            # typing}.  Of these, builtins must be processed last or else
            # some builtin objects will be incompletely processed.)
            scc.remove("builtins")
            scc.append("builtins")
        process_stale_scc(graph, scc, manager)

    type_state.reset_all_subtype_caches()
    return manager, sccs


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
def _typeshed_paths() -> tuple[tuple[Path, ...], Mapping[str, Path]]:
    """Return default standard library search paths. Guaranteed to be normalised."""
    custom_typeshed_dir = _CUSTOM_TYPESHED_PATH.resolve()
    if not custom_typeshed_dir.is_dir():
        raise InternalError("puyapy install is corrupted - missing typeshed directory")
    typeshed_dir = custom_typeshed_dir / "stdlib"
    if not typeshed_dir.is_dir():
        raise InternalError("puyapy install is corrupted - missing typeshed stlib directory")
    versions_file = typeshed_dir / "VERSIONS"
    if not versions_file.is_file():
        raise InternalError("puyapy install is corrupted - missing typeshed VERSIONS file")
    mypy_extensions_dir = custom_typeshed_dir / "stubs" / "mypy-extensions"
    if not mypy_extensions_dir.is_dir():
        raise InternalError(
            "puyapy install is corrupted - missing typeshed mypy-extensions directory"
        )

    algopy_stubs = typeshed_dir / "algopy"
    # TODO: remove below hack once mypy migration is complete
    if not algopy_stubs.exists():
        logger.info("algopy-stubs not installed in typeshed, assuming puyapy development mode")
        puyapy_dir = Path(__file__).parent
        vcs_root = puyapy_dir.parent.parent
        stubs_dir = vcs_root / "stubs"
        algopy_stubs = stubs_dir / "algopy-stubs"
    if not algopy_stubs.is_dir():
        raise InternalError("puyapy install is corrupted - algopy stubs not a directory")
    algopy_sources = dict[str, Path]()
    for algopy_stub_file in sorted(algopy_stubs.glob("*.pyi")):
        if algopy_stub_file.stem == "__init__":
            module_name = "algopy"
        else:
            module_name = f"algopy.{algopy_stub_file.stem}"
        algopy_sources[module_name] = algopy_stub_file
    return (typeshed_dir, mypy_extensions_dir), algopy_sources


def get_sys_path(python_executable: str) -> list[str]:
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
    if pyinfo_result.returncode != 0:
        if pyinfo_result.stderr:
            raise ConfigurationError(pyinfo_result.stderr)
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
