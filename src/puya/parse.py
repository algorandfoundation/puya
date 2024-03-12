import os
import re
import sys
import typing
from collections.abc import Sequence
from pathlib import Path
from typing import Self

import attrs
import docstring_parser
import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import mypy.util
import structlog

from puya.logging_config import mypy_severity_to_loglevel
from puya.utils import make_path_relative_to_cwd

logger = structlog.get_logger()
_SRC_ROOT = Path(__file__).parent
TYPESHED_PATH = _SRC_ROOT / "_typeshed"


@attrs.frozen
class EmbeddedSource:
    path: Path
    mypy_module_name: str
    puya_module_name: str

    @classmethod
    def from_path(cls, filename: str, *, module_override: str | None = None) -> typing.Self:
        path = _SRC_ROOT / "lib_embedded" / filename
        return cls(
            path=path,
            mypy_module_name=path.stem,
            puya_module_name=module_override or path.stem,
        )


_MYPY_EMBEDDED_MODULES = {
    es.mypy_module_name: es
    for es in (
        EmbeddedSource.from_path("_puyapy_.py", module_override="puyapy"),
        EmbeddedSource.from_path("puyapy_lib_arc4.py"),
        EmbeddedSource.from_path("puyapy_lib_bytes.py"),
    )
}

EMBEDDED_MODULES = tuple(es.puya_module_name for es in _MYPY_EMBEDDED_MODULES.values())


@attrs.frozen
class ParseSource:
    path: Path
    module_name: str
    is_explicit: bool


@attrs.frozen(kw_only=True, repr=False, str=False)
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

        match node:
            case mypy.nodes.FuncDef(body=body) | mypy.nodes.Decorator(
                func=mypy.nodes.FuncDef(body=body)
            ):
                if body is None:
                    # TODO: we can probably improve this, but for now just pass through unmodified.
                    #       It'll only be for functions with empty bodies anyway
                    end_line = node.end_line
                else:
                    end_line = body.line - 1
                return cls(
                    file=file,
                    line=node.line,
                    end_line=end_line,
                    mypy_src_node=type(node).__name__,
                )
            case mypy.nodes.ClassDef(decorators=class_decorators, defs=class_body):
                line = node.line
                for dec in class_decorators:
                    line = min(dec.line, line)
                end_line = class_body.line - 1
                return cls(
                    file=file,
                    line=line,
                    end_line=end_line,
                    mypy_src_node=type(node).__name__,
                )
            case (
                mypy.nodes.WhileStmt(body=compound_body) | mypy.nodes.ForStmt(body=compound_body)
            ):
                return cls(
                    file=file,
                    line=node.line,
                    end_line=compound_body.line - 1,
                    mypy_src_node=type(node).__name__,
                )
            case (mypy.nodes.IfStmt(body=[*bodies], else_body=else_body)):
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
                    end_line2 = node.end_line
                else:
                    end_line2 = body_start - 1
                return cls(
                    file=file,
                    line=node.line,
                    end_line=end_line2,
                    mypy_src_node=type(node).__name__,
                )
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

    def __str__(self) -> str:
        relative_path = make_path_relative_to_cwd(self.file)
        result = f"{relative_path}:{self.line}"
        if self.end_line is not None and self.end_line != self.line:
            result += f"-{self.end_line}"
        return result

    def __repr__(self) -> str:
        result = str(self)
        if self.column is not None:
            result += f":{self.column}"
            if self.end_column is not None:
                result += f"-{self.end_column}"
        return result

    def __add__(self, other: "SourceLocation | None") -> "SourceLocation":
        from puya.errors import InternalError

        if other is None:
            return self

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
    sources: Sequence[ParseSource]
    manager: mypy.build.BuildManager
    ordered_modules: Sequence[mypy.nodes.MypyFile]
    """All discovered modules, topologically sorted by dependencies.
    The sort order is from leaves (nodes without dependencies) to
    roots (nodes on which no other nodes depend)."""


def get_parse_sources(
    paths: Sequence[Path],
    mypy_fscache: mypy.fscache.FileSystemCache,
    mypy_options: mypy.options.Options,
) -> list[ParseSource]:
    resolved_input_paths = {p.resolve(): None for p in paths}
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
    return sources


def parse_and_typecheck(paths: Sequence[Path], mypy_options: mypy.options.Options) -> ParseResult:
    from puya.errors import InternalError

    mypy_fscache = mypy.fscache.FileSystemCache()
    # ensure we have the absolute, canonical paths to the files
    resolved_input_paths = {p.resolve() for p in paths}
    # creates a list of BuildSource objects from the contract Paths
    mypy_build_sources = mypy.find_sources.create_source_list(
        paths=[str(p) for p in resolved_input_paths],
        options=mypy_options,
        fscache=mypy_fscache,
    )
    sources = get_parse_sources(paths, mypy_fscache, mypy_options)

    # insert embedded lib, after source list that is returned has been constructed,
    # so we don't try to output it
    mypy_build_sources.extend(
        [
            mypy.build.BuildSource(
                # present a 'tidy' path to the user
                path=str(Path("<puya>") / f"{module.puya_module_name}.py"),
                module=module.mypy_module_name,
                text=module.path.read_text("utf8"),
            )
            for module in _MYPY_EMBEDDED_MODULES.values()
        ]
    )
    result = _mypy_build(mypy_build_sources, mypy_options, mypy_fscache)
    missing_module_names = {s.module_name for s in sources} - result.manager.modules.keys()
    if missing_module_names:
        # Note: this shouldn't happen, provided we've successfully disabled the mypy cache
        raise InternalError(
            f"mypy parse failed, missing modules: {', '.join(missing_module_names)}"
        )

    # order modules by dependency, and also sanity check the contents
    ordered_modules = []
    for scc_module_names in mypy.build.sorted_components(result.graph):
        for module_name in scc_module_names:
            module = result.manager.modules.get(module_name)
            if module is None:
                raise InternalError(f"mypy failed to parse: {module_name}")
            if module_name != module.fullname:
                raise InternalError(
                    f"mypy parsed wrong module, expected '{module_name}': {module.fullname}"
                )
            if not module.path:
                raise InternalError(f"No path for module: {module_name}")

            if embedded_src := _MYPY_EMBEDDED_MODULES.get(module_name):
                module._fullname = embedded_src.puya_module_name  # noqa: SLF001
                module_path = embedded_src.path
            else:
                module_path = Path(module.path)

            if module_path.is_dir():
                # this module is a module directory with no __init__.py, ie it contains
                # nothing and is only in the graph as a reference
                pass
            else:
                _check_encoding(mypy_fscache, module_path)
                ordered_modules.append(module)

    return ParseResult(
        sources=sources,
        manager=result.manager,
        ordered_modules=ordered_modules,
    )


def _check_encoding(mypy_fscache: mypy.fscache.FileSystemCache, module_path: Path) -> None:
    module_rel_path = make_path_relative_to_cwd(module_path)
    module_loc = SourceLocation(file=str(module_path), line=1)
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
    if encoding != "utf8":
        logger.warning(
            f"UH OH SPAGHETTI-O's,"
            f" darn tootin' non-utf8(?!) encoded file encountered:"
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
        _filename: str | None, new_messages: list[str], is_serious: bool  # noqa: FBT001
    ) -> None:
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
    description: str | None = None
    args: dict[str, str] = attrs.field(factory=dict)
    returns: str | None = None


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
