import ast
import typing

from puya.utils import valid_bytes, valid_int64


def parse_template_key_value(key_value_str: str) -> tuple[str, int | bytes]:
    try:
        name, value_str = key_value_str.split("=", maxsplit=1)
    except ValueError:
        raise ValueError(f"invalid template var definition: {key_value_str!r}") from None

    if value_str.startswith("0x"):
        value: int | bytes = bytes.fromhex(value_str[2:])
    else:
        try:
            literal = ast.literal_eval(value_str)
        except ValueError:
            literal = None
        match literal:
            case str(str_value):
                value = str_value.encode("utf8")
            case bool(bool_value):
                value = int(bool_value)
            case int(value):
                pass
            case _:
                raise ValueError(f"invalid template var definition: {key_value_str!r}")
    match value:
        case int(int_result):
            too_big = not valid_int64(int_result)
        case bytes(bytes_result):
            too_big = not valid_bytes(bytes_result)
        case unexpected:
            typing.assert_never(unexpected)
    if too_big:
        raise ValueError(f"template value {name!r} too big: {value_str}")
    return name, value
