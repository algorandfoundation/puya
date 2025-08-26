from algopy import Bytes, UInt64, op, subroutine
from algopy._hints import __pure


@__pure
@subroutine
def is_substring(item: Bytes, sequence: Bytes) -> bool:
    """
    Search for a shorter string in a larger one.
    """

    start = UInt64(0)
    while start + item.length <= sequence.length:
        if item == op.substring(sequence, start, start + item.length):
            return True
        start += 1
    return False
