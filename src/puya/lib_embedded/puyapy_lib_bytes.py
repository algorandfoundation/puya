from puyapy import Bytes, UInt64, subroutine, substring


@subroutine
def is_substring(item: Bytes, sequence: Bytes) -> bool:
    """
    Search for a shorter string in a larger one.
    """

    start = UInt64(0)
    while start + item.length <= sequence.length:
        if item == substring(sequence, start, start + item.length):
            return True
        start += 1
    return False
