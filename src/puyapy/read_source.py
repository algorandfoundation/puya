import codecs
import typing
from collections.abc import Mapping
from pathlib import Path

from mypy.util import (  # TODO: replace with our own functions
    decode_python_encoding,
    find_python_encoding,
)

from puya import log
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault, make_path_relative_to_cwd
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.builder import parse_module

logger = log.get_logger(__name__)


class SourceProvider:
    def __init__(
        self,
        file_contents: Mapping[Path, str],
        *,
        feature_version: int | tuple[int, int] | None = None,
    ):
        self._file_contents: typing.Final = {k: v for k, v in file_contents.items()}
        self._feature_version: typing.Final = feature_version
        self._parsed: typing.Final = dict[Path, fast_nodes.Module | None]()

    def read_source(self, module_path: Path) -> str:
        return lazy_setdefault(self._file_contents, module_path, _read_and_decode)

    def parse_source(self, module_path: Path, module_name: str) -> fast_nodes.Module | None:
        try:
            return self._parsed[module_path]
        except KeyError:
            pass
        source = self.read_source(module_path)
        result = parse_module(
            source=source,
            module_path=module_path,
            module_name=module_name,
            feature_version=self._feature_version,
        )
        self._parsed[module_path] = result
        return result


def _read_and_decode(module_path: Path) -> str:
    source = module_path.read_bytes()
    # below is based on mypy/util.py:decode_python_encoding
    # check for BOM UTF-8 encoding
    if not source.startswith(b"\xef\xbb\xbf"):
        # otherwise look at first two lines and check if PEP-263 coding is present
        encoding, _ = find_python_encoding(source)
        # find the codec for this encoding and check it is utf-8
        codec = codecs.lookup(encoding)
        if codec.name != "utf-8":
            module_rel_path = make_path_relative_to_cwd(module_path)
            module_loc = SourceLocation(file=module_path, line=1)
            logger.warning(
                "UH OH SPAGHETTI-O's,"
                " darn tootin' non-utf8(?!) encoded file encountered:"
                f" {module_rel_path} encoded as {encoding}",
                location=module_loc,
            )
    return decode_python_encoding(source)
