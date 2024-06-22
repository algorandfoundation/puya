from algopy_testing.primitives.bytes import Bytes
from algopy_testing.primitives.uint64 import UInt64
from algopy_testing.protocols import BytesBacked
from algopy_testing.utils import int_to_bytes


def log(
    *args: UInt64 | Bytes | BytesBacked | str | bytes | int,
    sep: Bytes | bytes | str = b"",
) -> None:
    """Concatenates and logs supplied args as a single bytes value.

    UInt64 args are converted to bytes and each argument is separated by `sep`.
    Literal `str` values will be encoded as UTF8.
    """

    from algopy_testing.context import get_test_context

    context = get_test_context()
    logs: list[bytes] = []

    for arg in args:
        if isinstance(arg, UInt64):
            logs.append(int_to_bytes(arg.value))
        elif isinstance(arg, Bytes):
            logs.append(arg.value)
        elif isinstance(arg, str):
            logs.append(arg.encode("utf8"))
        elif isinstance(arg, bytes):
            logs.append(arg)
        elif isinstance(arg, int):
            logs.append(int_to_bytes(arg))
        else:
            logs.append(arg.bytes.value)

    separator = b""
    if isinstance(sep, Bytes):
        separator = sep.value
    elif isinstance(sep, str):
        separator = sep.encode("utf8")
    else:
        separator = sep

    context.logs.append(separator.join(logs))
