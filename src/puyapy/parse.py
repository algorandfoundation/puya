from __future__ import annotations

import codecs
import enum
import os
import re
import typing
from functools import cached_property
from pathlib import Path

import attrs
import docstring_parser
import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import mypy.types
import mypy.util

from puya import log
from puya.awst.nodes import MethodDocumentation
from puya.parse import SourceLocation
from puya.utils import coalesce, make_path_relative_to_cwd

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence, Set

logger = log.get_logger(__name__)
_PUYAPY_SRC_ROOT = Path(__file__).parent
_PUYA_SRC_ROOT = _PUYAPY_SRC_ROOT.parent / "puya"
TYPESHED_PATH = _PUYAPY_SRC_ROOT / "_typeshed"
_MYPY_FSCACHE = mypy.fscache.FileSystemCache()
_MYPY_SEVERITY_TO_LOG_LEVEL = {
    "error": log.LogLevel.error,
    "warning": log.LogLevel.warning,
    "note": log.LogLevel.info,
}


@attrs.frozen
class EmbeddedSource:
    path: Path
    mypy_module_name: str
    puya_module_name: str

    @classmethod
    def from_path(cls, filename: str, *, module_override: str | None = None) -> typing.Self:
        path = _PUYA_SRC_ROOT / "lib_embedded" / filename
        return cls(
            path=path,
            mypy_module_name=path.stem,
            puya_module_name=module_override or path.stem,
        )


class SourceDiscoveryMechanism(enum.Enum):
    explicit_file = enum.auto()
    explicit_directory_walk = enum.auto()
    dependency = enum.auto()


@attrs.frozen
class SourceModule:
    name: str
    node: mypy.nodes.MypyFile
    path: Path
    lines: Sequence[str] | None
    discovery_mechanism: SourceDiscoveryMechanism


@attrs.frozen
class ParseResult:
    mypy_options: mypy.options.Options
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
            if sm.discovery_mechanism != SourceDiscoveryMechanism.dependency
        }


def parse_and_typecheck(
    paths: Sequence[Path], mypy_options: mypy.options.Options
) -> tuple[mypy.build.BuildManager, dict[str, SourceModule]]:
    """Generate the ASTs from the build sources, and all imported modules (recursively)"""

    # ensure we have the absolute, canonical paths to the files
    resolved_input_paths = {p.resolve() for p in paths}
    # creates a list of BuildSource objects from the contract Paths
    mypy_build_sources = mypy.find_sources.create_source_list(
        paths=[str(p) for p in resolved_input_paths],
        options=mypy_options,
        fscache=_MYPY_FSCACHE,
    )
    build_source_paths = {
        Path(m.path).resolve() for m in mypy_build_sources if m.path and not m.followed
    }
    result = _mypy_build(mypy_build_sources, mypy_options, _MYPY_FSCACHE)
    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    result.manager.errors.set_file("<puyapy>", module=None, scope=None, options=mypy_options)
    missing_module_names = {s.module for s in mypy_build_sources} - result.manager.modules.keys()
    # Note: this shouldn't happen, provided we've successfully disabled the mypy cache
    assert (
        not missing_module_names
    ), f"mypy parse failed, missing modules: {', '.join(missing_module_names)}"

    # order modules by dependency, and also sanity check the contents
    ordered_modules = {}
    for scc_module_names in mypy.build.sorted_components(result.graph):
        for module_name in scc_module_names:
            module = result.manager.modules[module_name]
            assert (
                module_name == module.fullname
            ), f"mypy module mismatch, expected {module_name}, got {module.fullname}"
            assert module.path, f"no path for mypy module: {module_name}"
            module_path = Path(module.path).resolve()
            if module_path.is_dir():
                # this module is a module directory with no __init__.py, ie it contains
                # nothing and is only in the graph as a reference
                pass
            else:
                _check_encoding(_MYPY_FSCACHE, module_path)
                lines = mypy.util.read_py_file(str(module_path), _MYPY_FSCACHE.read)
                if module_path in resolved_input_paths:
                    discovery_mechanism = SourceDiscoveryMechanism.explicit_file
                elif module_path in build_source_paths:
                    discovery_mechanism = SourceDiscoveryMechanism.explicit_directory_walk
                else:
                    discovery_mechanism = SourceDiscoveryMechanism.dependency
                ordered_modules[module_name] = SourceModule(
                    name=module_name,
                    node=module,
                    path=module_path,
                    lines=lines,
                    discovery_mechanism=discovery_mechanism,
                )

    return result.manager, ordered_modules


def _check_encoding(mypy_fscache: mypy.fscache.FileSystemCache, module_path: Path) -> None:
    module_rel_path = make_path_relative_to_cwd(module_path)
    module_loc = SourceLocation(file=module_path, line=1)
    try:
        source = mypy_fscache.read(str(module_path))
    except OSError:
        logger.warning(
            f"Couldn't read source for {module_rel_path}",
            location=module_loc,
        )
        return
    # below is based on mypy/util.py:decode_python_encoding
    # check for BOM UTF-8 encoding
    if source.startswith(b"\xef\xbb\xbf"):
        return
    # otherwise look at first two lines and check if PEP-263 coding is present
    encoding, _ = mypy.util.find_python_encoding(source)
    # find the codec for this encoding and check it is utf-8
    codec = codecs.lookup(encoding)
    if codec.name != "utf-8":
        logger.warning(
            "UH OH SPAGHETTI-O's,"
            " darn tootin' non-utf8(?!) encoded file encountered:"
            f" {module_rel_path} encoded as {encoding}",
            location=module_loc,
        )


def _mypy_build(
    sources: list[mypy.modulefinder.BuildSource],
    options: mypy.options.Options,
    fscache: mypy.fscache.FileSystemCache | None,
) -> mypy.build.BuildResult:
    """Simple wrapper around mypy.build.build

    Makes it so that check errors and parse errors are handled the same (ie with an exception)
    """

    all_messages = list[str]()

    def flush_errors(
        _filename: str | None,
        new_messages: list[str],
        _is_serious: bool,  # noqa: FBT001
    ) -> None:
        all_messages.extend(msg for msg in new_messages if os.devnull not in msg)

    try:
        result = mypy.build.build(
            sources=sources,
            options=options,
            flush_errors=flush_errors,
            fscache=fscache,
        )
    finally:
        _log_mypy_messages(all_messages)
    return result


def _log_mypy_message(message: log.Log | None, related_lines: list[str]) -> None:
    if not message:
        return
    logger.log(
        message.level, message.message, location=message.location, related_lines=related_lines
    )


def _log_mypy_messages(messages: list[str]) -> None:
    first_message: log.Log | None = None
    related_messages = list[str]()
    for message_str in messages:
        message = _parse_log_message(message_str)
        if not first_message:
            first_message = message
        elif not message.location:
            # collate related error messages and log together
            related_messages.append(message.message)
        else:
            _log_mypy_message(first_message, related_messages)
            related_messages = []
            first_message = message
    _log_mypy_message(first_message, related_messages)


_MYPY_LOG_MESSAGE = re.compile(
    r"""^
    (?P<filename>([A-Z]:\\)?[^:]*)(:(?P<line>\d+))?
    :\s(?P<severity>error|warning|note)
    :\s(?P<msg>.*)$""",
    re.VERBOSE,
)


def _parse_log_message(log_message: str) -> log.Log:
    match = _MYPY_LOG_MESSAGE.match(log_message)
    if match:
        matches = match.groupdict()
        return _try_parse_log_parts(
            matches.get("filename"),
            matches.get("line") or "",
            matches.get("severity") or "error",
            matches["msg"],
        )
    return log.Log(
        level=log.LogLevel.error,
        message=log_message,
        location=None,
    )


def _try_parse_log_parts(
    path_str: str | None, line_str: str, severity_str: str, msg: str
) -> log.Log:
    if not path_str:
        location = None
    else:
        try:
            line = int(line_str)
        except ValueError:
            line = 1
        location = SourceLocation(file=Path(path_str).resolve(), line=line)
    level = _MYPY_SEVERITY_TO_LOG_LEVEL[severity_str]
    return log.Log(message=msg, level=level, location=location)


def _join_single_new_line(doc: str) -> str:
    return doc.strip().replace("\n", " ")


def parse_docstring(docstring_raw: str | None) -> MethodDocumentation:
    if docstring_raw is None:
        return MethodDocumentation()
    docstring = docstring_parser.parse(docstring_raw)
    method_desc = "\n".join(
        _join_single_new_line(line)
        for lines in filter(None, (docstring.short_description, docstring.long_description))
        for line in lines.split("\n\n")
    )
    return MethodDocumentation(
        description=method_desc if method_desc else None,
        args={
            p.arg_name: _join_single_new_line(p.description)
            for p in docstring.params
            if p.description
        },
        returns=(
            _join_single_new_line(docstring.returns.description)
            if docstring.returns and docstring.returns.description
            else None
        ),
    )


def source_location_from_mypy(file: Path | None, node: mypy.nodes.Context) -> SourceLocation:
    assert node.line is not None
    assert node.line >= 1

    match node:
        case (
            mypy.nodes.FuncDef(body=body)
            | mypy.nodes.Decorator(func=mypy.nodes.FuncDef(body=body))
        ):
            # end_line of a function node includes the entire body
            # try to get just the signature
            end_line = node.line
            # no body means the end_line is ok to use
            if body is None:
                end_line = max(end_line, node.end_line or node.line)
            # if there is a body, attempt to use the first line before the body as the end
            else:
                end_line = max(end_line, body.line - 1)
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=end_line,
            )
        case mypy.nodes.ClassDef(decorators=class_decorators, defs=class_body):
            line = node.line
            for dec in class_decorators:
                line = min(dec.line, line)
            end_line = max(line, class_body.line - 1)
            return SourceLocation(
                file=file,
                line=line,
                end_line=end_line,
            )
        case mypy.nodes.WhileStmt(body=compound_body) | mypy.nodes.ForStmt(body=compound_body):
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=compound_body.line - 1,
            )
        case mypy.nodes.IfStmt(body=[*bodies], else_body=else_body):
            body_start: int | None = None
            if else_body is not None:
                bodies.append(else_body)
            for body in bodies:
                if body_start is None:
                    body_start = body.line
                else:
                    body_start = min(body_start, body.line)
            if body_start is None:
                # this shouldn't happen, there should be at least one body in one branch,
                # but this serves okay as a fallback
                end_line = node.end_line or node.line
            else:
                end_line = body_start - 1
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=end_line,
            )
        case mypy.types.Type():
            # mypy types seem to not have an end_column specified, which ends up implying to
            # end of line, so instead make end_column end after column so it is just a
            # single character reference

            if node.column < 0:
                typ_column: int | None = None
                typ_end_column: int | None = None
            else:
                typ_column = node.column
                typ_end_column = coalesce(node.end_column, typ_column + 1)
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=(
                    node.end_line
                    if (node.end_line is not None and node.end_line >= 1)
                    else node.line
                ),
                column=typ_column,
                end_column=typ_end_column,
            )
    return SourceLocation(
        file=file,
        line=node.line,
        end_line=(
            node.end_line if (node.end_line is not None and node.end_line >= 1) else node.line
        ),
        column=node.column if (node.column is not None and node.column >= 0) else 0,
        end_column=(
            node.end_column if (node.end_column is not None and node.end_column >= 0) else None
        ),
    )
