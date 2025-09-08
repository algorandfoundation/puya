import os
import sys
from pathlib import Path

from mypy.build import (
    BuildManager,
    Graph,
    default_data_dir,
    load_graph,
    process_graph,
)
from mypy.error_formatter import ErrorFormatter
from mypy.errors import SHOW_NOTE_CODES, Errors, MypyError
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, compute_search_paths
from mypy.options import Options
from mypy.plugin import Plugin
from mypy.plugins.default import DefaultPlugin
from mypy.typestate import reset_global_state, type_state
from mypy.util import read_py_file
from mypy.version import __version__ as mypy_version

from puya import log
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def mypy_build(
    sources: list[BuildSource], options: Options, fscache: FileSystemCache
) -> tuple[BuildManager, Graph]:
    """Simple wrapper around mypy.build.build

    Makes it so that check errors and parse errors are handled the same (ie with an exception)
    """
    data_dir = default_data_dir()

    search_paths = compute_search_paths(sources, options, data_dir, alt_lib_path=None)

    source_set = BuildSourceSet(sources)
    cached_read = fscache.read
    errors = Errors(options, read_source=lambda path: read_py_file(path, cached_read))
    plugin: Plugin = DefaultPlugin(options)

    def ignore_error(*_args: object) -> None:
        pass

    # Construct a build manager object to hold state during the build.
    #
    # Ignore current directory prefix in error messages.
    manager = BuildManager(
        data_dir,
        search_paths,
        ignore_prefix=os.getcwd(),  # noqa: PTH109
        source_set=source_set,
        reports=None,
        options=options,
        version_id=mypy_version,
        plugin=plugin,
        plugins_snapshot={},
        errors=errors,
        error_formatter=_LogReporter(),
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
                line=error.line,
                column=error.column,
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
