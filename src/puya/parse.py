import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Self

import attrs
import docstring_parser
import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import structlog

from puya.logging_config import mypy_severity_to_loglevel
from puya.utils import make_path_relative_to_cwd

logger = structlog.get_logger()
TYPESHED_PATH = Path(__file__).parent / "_typeshed"


@attrs.frozen
class ParseSource:
    path: Path
    module_name: str
    is_explicit: bool


@attrs.frozen(kw_only=True, repr=False)
class SourceLocation:
    file: str
    line: int
    # TODO: much better validation below
    end_line: int | None = None
    column: int | None = None
    end_column: int | None = None
    mypy_src_node: str | None = None

    @classmethod
    def from_mypy(cls, file: str, node: mypy.nodes.Context) -> Self:
        assert node.line is not None
        assert node.line >= 1
        return cls(
            file=file,
            line=node.line,
            end_line=node.end_line if (node.end_line is not None and node.end_line >= 1) else None,
            column=node.column if (node.column is not None and node.column >= 0) else 0,
            end_column=(
                node.end_column if (node.end_column is not None and node.end_column >= 0) else None
            ),
            mypy_src_node=type(node).__name__,
        )

    @property
    def clickable_str(self) -> str:
        relative_path = make_path_relative_to_cwd(self.file)
        return f'File "{relative_path}", line {self.line}'

    def __repr__(self) -> str:
        return self.clickable_str

    def __add__(self, other: "SourceLocation") -> "SourceLocation":
        from puya.errors import InternalError

        if self.file != other.file:
            raise InternalError("uh oh")
        # BEGIN: YIKES
        lines = list(filter(None, (self.line, other.line, self.end_line, other.end_line)))
        start_line = min(lines)
        end_line = max(lines)
        columns = [
            (self.line, self.column),
            (self.end_line, self.end_column),
            (other.line, other.column),
            (other.end_line, other.end_column),
        ]
        start_column = sys.maxsize
        end_column = -1
        for line, column in columns:
            if column is not None:
                if line == start_line:
                    start_column = min(start_column, column)
                elif line == end_line:
                    end_column = max(end_column, column)
        return SourceLocation(
            file=self.file,
            line=start_line,
            end_line=end_line,
            column=None if start_column == sys.maxsize else start_column,
            end_column=None if end_column == -1 else end_column,
        )
        # END: YIKES


@attrs.frozen
class ParseResult:
    sources: list[ParseSource]
    manager: mypy.build.BuildManager
    graph: mypy.build.Graph

    def build_dep_graph(self) -> dict[str, Any]:
        """Generate an inspect-able module dependency graph.

        This is a helper function to use when debugging.
        """
        result = {
            id: dict.fromkeys(sorted(state.dependencies_set)) for id, state in self.graph.items()
        }
        for deps in result.values():
            for dep_id in deps:
                deps[dep_id] = result[dep_id]
        return result


def parse_and_typecheck(paths: Sequence[Path], mypy_options: mypy.options.Options) -> ParseResult:
    mypy_fscache = mypy.fscache.FileSystemCache()
    # ensure we have the absolute, canonical paths to the files
    resolved_input_paths = {p.resolve() for p in paths}
    # creates a list of BuildSource objects from the contract Paths
    mypy_build_sources = mypy.find_sources.create_source_list(
        paths=[str(p) for p in resolved_input_paths],
        options=mypy_options,
        fscache=mypy_fscache,
    )
    sources: list[ParseSource] = []
    for src in mypy_build_sources:
        if not src.path:
            # all build sources should have a path value
            raise ValueError("Unexpected empty source path")
        src_path = Path(src.path).resolve()
        sources.append(
            ParseSource(
                path=src_path,
                module_name=src.module,
                is_explicit=src_path in resolved_input_paths,
            )
        )
    # insert embedded lib, after source list that is returned has been constructed,
    # so we don't try to output it
    puyapy_lib_path = Path(__file__).parent / "lib_embedded" / "_puyapy_.py"
    mypy_build_sources.append(
        mypy.build.BuildSource(
            path=str(Path("<puya>") / "puyapy.py"),
            module="_puyapy_",
            text=puyapy_lib_path.read_text(),
        )
    )
    result = _mypy_build(mypy_build_sources, mypy_options, mypy_fscache)
    missing_module_names = {s.module_name for s in sources} - result.manager.modules.keys()
    if missing_module_names:
        # Note: this shouldn't happen, provided we've successfully disabled the mypy cache
        raise Exception(f"mypy parse failed, missing modules: {', '.join(missing_module_names)}")
    return ParseResult(
        sources=sources,
        manager=result.manager,
        graph=result.graph,
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

    def flush_errors(new_messages: list[str], is_serious: bool) -> None:  # noqa: FBT001
        if new_messages:
            all_messages.extend(msg for msg in new_messages if os.devnull not in msg)
            if is_serious:
                raise mypy.errors.CompileError(all_messages)

    result = mypy.build.build(
        sources=sources,
        options=options,
        flush_errors=flush_errors,
        fscache=fscache,
    )
    if any(
        msg.severity != "note"
        for file_name, file_messages in result.manager.errors.error_info_map.items()
        for msg in file_messages
        if not file_name.startswith(os.devnull)
    ):
        raise mypy.errors.CompileError(all_messages)
    else:
        for message in all_messages:
            path, line, severity, msg = split_log_message(message)
            level = mypy_severity_to_loglevel(severity.strip())
            location = SourceLocation(file=path, line=int(line))
            logger.log(level, msg, location=location)
    return result


def split_log_message(message: str) -> tuple[str, str, str, str]:
    # if the messages starts with a drive letter (eg c:\) we're probably on windows
    if re.match(r"^[A-Z]:\\", message, flags=re.RegexFlag.IGNORECASE):
        drive, path, line, severity, msg = message.split(":", maxsplit=4)
        return f"{drive}:{path}", line, severity, msg
    path, line, severity, msg = message.split(":", maxsplit=3)
    return path, line, severity, msg


@attrs.define
class MethodDocumentation:
    description: str | None = attrs.field(default=None)
    args: dict[str, str] = attrs.field(factory=dict)
    returns: str | None = attrs.field(default=None)


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
