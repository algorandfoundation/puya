import contextlib
from collections.abc import Iterable

from puya.errors import PuyaError
from puya.utils import valid_bytes, valid_int64


def parse_template_vars(template_vars: Iterable[str], prefix: str) -> dict[str, int | bytes]:
    return {
        prefix + name: _parse_template_value(name, value)
        for name, value in map(_split_template_line, template_vars)
    }


def _split_template_line(line: str) -> tuple[str, str]:
    try:
        name, value_str = line.split("=", maxsplit=1)
    except ValueError as ex:
        raise PuyaError(f"Invalid template var definition: {line=!r}") from ex
    return name, value_str


def _parse_str(value: str) -> str | None:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    else:
        return None


def _parse_bytes(value_str: str) -> bytes | None:
    value = None
    if value_str.startswith("0x"):
        with contextlib.suppress(ValueError):
            value = bytes.fromhex(value_str[2:])
    return value


def _parse_int(value_str: str) -> int | None:
    try:
        return int(value_str)
    except ValueError:
        return None


def _parse_template_value(name: str, value_str: str) -> int | bytes:
    value: int | bytes | None = None
    too_big = False
    if (str_ := _parse_str(value_str)) is not None:
        value = str_.encode("utf8")
        too_big = not valid_bytes(value)
    elif (bytes_ := _parse_bytes(value_str)) is not None:
        value = bytes_
        too_big = not valid_bytes(value)
    elif int_ := _parse_int(value_str):
        value = int_
        too_big = not valid_int64(value)
    if value is None:
        raise PuyaError(f"Invalid template var definition: {value_str}")
    if too_big:
        raise PuyaError(f"Template value {name!r} too big: {value_str}")
    return value
