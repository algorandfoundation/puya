import base64
from collections.abc import Sequence

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.ir.types_ import AVMBytesEncoding


def escape_utf8_string(s: str) -> str:
    """Escape a UTF-8 string for use in TEAL assembly.

    Args:
        s: A UTF-8 string to escape.

    Returns:
        An escaped version of the input string. This version will be surrounded in double quotes,
        all special characters (such as \\n) will be escaped with additional backslashes, and all
        Unicode characters beyond the latin-1 encoding will be encoded in hex escapes (e.g. \\xf0).
    """
    # The point of this conversion is to escape all special characters and turn all Unicode
    # characters into hex-escaped characters in the input string.
    #
    # The first step breaks up large Unicode characters into multiple UTF-8 hex characters:
    #     s_1 = s.encode("utf-8").decode("latin-1")
    # e.g. "\n 😀" => "\n ð\x9f\x98\x80"
    #
    # The next step escapes all special characters:
    #     s_1.encode("unicode-escape").decode("latin-1")
    # e.g. "\n ð\x9f\x98\x80" => "\\n \\xf0\\x9f\\x98\\x80"
    #
    # If we skipped the first step we would end up with Unicode codepoints instead of hex escaped
    # characters, which TEAL assembly cannot process:
    #     s.encode("unicode-escape").decode("latin-1")
    # e.g. "\n 😀" => "\\n \\U0001f600'"
    s = s.encode("utf-8").decode("latin-1").encode("unicode-escape").decode("latin-1")

    # Escape double quote characters (not covered by unicode-escape) but leave in single quotes
    s = s.replace('"', '\\"')

    # Surround string in double quotes
    return '"' + s + '"'


def format_bytes(b: bytes, encoding: AVMBytesEncoding) -> str:
    match encoding:
        case AVMBytesEncoding.utf8:
            return escape_utf8_string(b.decode())
        case AVMBytesEncoding.base32:
            return base64.b32encode(b).decode("ascii").rstrip("=")
        case AVMBytesEncoding.base64:
            return base64.b64encode(b).decode("ascii")
        case AVMBytesEncoding.base16 | AVMBytesEncoding.unknown:
            return f"0x{b.hex()}"


def format_tuple_index(var_type: wtypes.WTuple, base_name: str, index_or_name: int | str) -> str:
    # If a named tuple is indexed numerical, convert this to the item name
    if isinstance(index_or_name, int) and var_type.names is not None:
        index_or_name = var_type.names[index_or_name]
    return f"{base_name}.{index_or_name}"


def lvalue_items(tup: awst_nodes.TupleExpression) -> Sequence[awst_nodes.Lvalue]:
    items = list[awst_nodes.Lvalue]()
    for item in tup.items:
        assert isinstance(item, awst_nodes.Lvalue)
        items.append(item)
    return items


def format_error_comment(op: str, error_message: str) -> str:
    if op in ("err", "assert"):
        return error_message
    else:
        return f"on error: {error_message}"
