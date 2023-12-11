from collections.abc import Callable

import attrs

from puya.errors import Errors
from puya.options import PuyaOptions
from puya.parse import ParseResult


@attrs.define
class CompileContext:
    options: PuyaOptions
    parse_result: ParseResult
    errors: Errors
    read_source: Callable[[str], list[str] | None]
