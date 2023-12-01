from collections.abc import Callable

import attrs

from wyvern.errors import Errors
from wyvern.options import WyvernOptions
from wyvern.parse import ParseResult


@attrs.define
class CompileContext:
    options: WyvernOptions
    parse_result: ParseResult
    errors: Errors
    read_source: Callable[[str], list[str] | None]
