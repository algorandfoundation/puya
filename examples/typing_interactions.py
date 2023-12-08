import typing

from algopy import Account, Bytes, UInt64, subroutine

SOME_ADDRESS = "VCMJKWOY5P5P7SKMZFFOCEROPJCZOTIJMNIYNUCKH7LRO45JMJP6UYBIJA"
SOME_ADDRESS_PADDED = SOME_ADDRESS + "=="


@subroutine
def typing_interactions() -> None:
    typing.reveal_type(UInt64(1))
    typing.reveal_type((UInt64(1), Bytes(b"")))
    typing.assert_type(UInt64(1), UInt64)
    # Note this is technically invalid, we're just here to get our warning and leave
    assert typing.cast(Bytes, Account(SOME_ADDRESS)) == Bytes.from_base64(SOME_ADDRESS_PADDED)
