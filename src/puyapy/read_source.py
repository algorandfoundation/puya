import codecs
from collections.abc import Mapping
from pathlib import Path

from mypy.util import (  # TODO: replace with our own functions
    decode_python_encoding,
    find_python_encoding,
)

from puya import log
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault, make_path_relative_to_cwd

logger = log.get_logger(__name__)


class SourceProvider:
    def __init__(self, file_contents: Mapping[Path, str]):
        self._file_contents = {k: v for k, v in file_contents.items()}

    def read_source(self, path: Path) -> str:
        return lazy_setdefault(self._file_contents, path, _read_and_decode)


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
