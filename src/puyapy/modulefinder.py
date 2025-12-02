import enum
import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault

logger = log.get_logger(__name__)


@enum.unique
class ModuleNotFoundReason(enum.Enum):
    PACKAGE_NOT_FOUND = enum.auto()
    SUBMODULE_NOT_FOUND = enum.auto()
    UNTYPED_PACKAGE = enum.auto()
    STANDALONE_MODULE = enum.auto()
    POSSIBLE_NAMESPACE_PACKAGE = enum.auto()


ModuleSearchResult = Path | ModuleNotFoundReason
LibPathResult = (
    Path
    | typing.Literal[
        ModuleNotFoundReason.UNTYPED_PACKAGE,
        ModuleNotFoundReason.STANDALONE_MODULE,
        ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE,
    ]
)

_LibPath = Sequence[Path]


@attrs.frozen(kw_only=True)
class FindModuleCache:
    package_roots: Mapping[str, Path]
    "Known packages and their root module (either a standalone module or a pacakge __init__.py)"
    package_paths: _LibPath
    "List of path entries to search for third party packages"
    _results: dict[str, ModuleSearchResult] = attrs.field(factory=dict, init=False)
    _lib_path_cache: dict[Path, Mapping[str, LibPathResult]] = attrs.field(
        factory=dict, init=False
    )

    def __attrs_post_init__(self) -> None:
        assert all(p.is_file() and p.suffixes == [".py"] for p in self.package_roots.values())

    def find_module(
        self, module_id: str, import_loc: SourceLocation | None, import_base_dir: Path
    ) -> Path | None:
        path_or_reason = self.try_find_module(module_id, import_base_dir)
        match path_or_reason:
            case ModuleNotFoundReason.PACKAGE_NOT_FOUND:
                logger.error(
                    f'unable to resolve imported module "{module_id}": could not locate package',
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.SUBMODULE_NOT_FOUND:
                logger.error(
                    f'unable to resolve imported module "{module_id}": could not locate submodule',
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.UNTYPED_PACKAGE:
                logger.error(
                    f'imported module "{module_id}" comes from an untyped package,'
                    f" or a package with separate type stubs",
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.STANDALONE_MODULE:
                logger.error(
                    f'imported module "{module_id}" comes from an standalone module',
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE:
                logger.error(
                    f'imported module "{module_id}" appears to come from'
                    f" an implicit namespace package, which is not supported currently",
                    location=import_loc,
                )
                return None
            case path:
                return path

    def try_find_module(self, module_id: str, import_base_dir: Path) -> ModuleSearchResult:
        result = lazy_setdefault(self._results, module_id, self._find_module)
        # this is a fallback for previously supported behaviour, where files co-located with
        # input sources but not part of those packages were importable
        if result is ModuleNotFoundReason.PACKAGE_NOT_FOUND:
            pkg, _sep, sub_id = module_id.partition(".")
            pkg_init_path = import_base_dir / pkg / "__init__.py"
            standalone_module_path = (import_base_dir / pkg).with_suffix(".py")
            pkg_root = None
            if pkg_init_path.is_file():
                if standalone_module_path.is_file():
                    logger.error(
                        f"{standalone_module_path} is shadowed by package {pkg_init_path}"
                    )
                pkg_root = pkg_init_path
            elif standalone_module_path.is_file():
                pkg_root = standalone_module_path
            if pkg_root is not None:
                return self._find_submodule(pkg_root, sub_id)
        return result

    def _find_module(self, module_id: str) -> ModuleSearchResult:
        pkg, _sep, sub_id = module_id.partition(".")
        if pkg_root := self.package_roots.get(pkg):
            return self._find_submodule(pkg_root, sub_id)
        possible_namespace_package = False
        for lib_path in self.package_paths:
            lib_path_entries = lazy_setdefault(self._lib_path_cache, lib_path, self._load_lib_path)
            reason_or_path = lib_path_entries.get(pkg)
            match reason_or_path:
                case None:
                    pass
                case ModuleNotFoundReason.UNTYPED_PACKAGE | ModuleNotFoundReason.STANDALONE_MODULE:
                    return reason_or_path
                case ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE:
                    possible_namespace_package = True
                case path:
                    typing.assert_type(path, Path)
                    return self._find_submodule(path, sub_id)
        if possible_namespace_package:
            return ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE
        return ModuleNotFoundReason.PACKAGE_NOT_FOUND

    @staticmethod
    def _find_submodule(pkg_root: Path, sub_id: str) -> ModuleSearchResult:
        assert pkg_root.is_file() and pkg_root.suffixes == [".py"]
        if not sub_id:
            return pkg_root
        if pkg_root.name != "__init__.py":
            return ModuleNotFoundReason.SUBMODULE_NOT_FOUND
        mod_path = pkg_root.parent.joinpath(*sub_id.split("."))
        if mod_path.is_dir():
            mod_init_path = mod_path / "__init__.py"
            if mod_init_path.is_file():
                return mod_init_path
            else:
                return mod_path
        else:
            mod_path = mod_path.with_suffix(".py")
            if mod_path.is_file():
                return mod_path
            else:
                return ModuleNotFoundReason.SUBMODULE_NOT_FOUND

    @staticmethod
    def _load_lib_path(lib_path: Path) -> Mapping[str, LibPathResult]:
        # ref: https://peps.python.org/pep-0420/#specification
        if not lib_path.is_dir():
            logger.debug(f"package path entry is not a directory: {lib_path}")
            return {}
        # sort entries, this will ensure directories come before python files and also
        # provide a consistent ordering
        result = dict[str, LibPathResult]()
        for dir_entry in sorted(lib_path.iterdir(), key=lambda x: x.name):
            if dir_entry.is_dir():
                name = dir_entry.name
                if dir_entry.name.isidentifier():
                    init_path = dir_entry / "__init__.py"
                    if not init_path.is_file():
                        result[name] = ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE
                    elif not (dir_entry / "py.typed").is_file():
                        result[name] = ModuleNotFoundReason.UNTYPED_PACKAGE
                    else:
                        result[name] = init_path
            # The following files seem to determine what is a valid extension module via
            # defining _PyImport_DynLoadFiletab:
            #   - https://github.com/python/cpython/blob/3.12/Python/dynload_shlib.c
            #   - https://github.com/python/cpython/blob/3.12/Python/dynload_win.c
            #   - https://github.com/python/cpython/blob/3.12/Python/dynload_hpux.c
            # If we had easy access to the interpreter we could just use:
            #   https://docs.python.org/3/library/importlib.html#importlib.machinery.all_suffixes
            # We can't just use the current interpreter values because even though it should
            # be the correct platform it might be the wrong Python version.
            # But excluding HP-UX and cygwin, these extensions together with only looking
            # at the filename up to the first . should suffice
            elif dir_entry.is_file() and dir_entry.suffix in (".py", ".pyc", ".so", ".pyd"):
                name = dir_entry.name.partition(".")[0]
                if name in result:
                    logger.debug(f"module '{name}' is shadowed by package on path {lib_path}")
                else:
                    result[name] = ModuleNotFoundReason.STANDALONE_MODULE
        return result
