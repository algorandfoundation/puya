import enum
import os
import shutil
import subprocess
import sysconfig
import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.errors import ConfigurationError, InternalError
from puya.utils import lazy_setdefault
from puyapy import interpreter_data

logger = log.get_logger(__name__)


@enum.unique
class PackageError(enum.Enum):
    UNTYPED_PACKAGE = enum.auto()
    STANDALONE_MODULE = enum.auto()
    POSSIBLE_NAMESPACE_PACKAGE = enum.auto()


LibPathResult = Path | PackageError


@attrs.frozen
class PackageResolverCache:
    """Resolver / cache for packages on sys.path"""

    package_paths: Sequence[Path]
    "List of path entries to search for third party packages"
    _entries_cache: dict[Path, Mapping[str, LibPathResult]] = attrs.field(factory=dict, init=False)

    def find_package(self, pkg: str) -> LibPathResult | None:
        possible_namespace_package = False
        for lib_path in self.package_paths:
            lib_path_entries = lazy_setdefault(self._entries_cache, lib_path, self._load_lib_path)
            reason_or_path = lib_path_entries.get(pkg)
            match reason_or_path:
                case None:
                    pass
                case PackageError.UNTYPED_PACKAGE | PackageError.STANDALONE_MODULE:
                    return reason_or_path
                case PackageError.POSSIBLE_NAMESPACE_PACKAGE:
                    possible_namespace_package = True
                case path:
                    typing.assert_type(path, Path)
                    return path
        if possible_namespace_package:
            return PackageError.POSSIBLE_NAMESPACE_PACKAGE
        return None

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
                        result[name] = PackageError.POSSIBLE_NAMESPACE_PACKAGE
                    elif not (dir_entry / "py.typed").is_file():
                        result[name] = PackageError.UNTYPED_PACKAGE
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
                    result[name] = PackageError.STANDALONE_MODULE
        return result


def resolve_package_paths(
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
