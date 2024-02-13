import base64

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
            return base64.b32encode(b).decode("ascii")
        case AVMBytesEncoding.base64:
            return base64.b64encode(b).decode("ascii")
        case _:
            return f"0x{b.hex()}"
