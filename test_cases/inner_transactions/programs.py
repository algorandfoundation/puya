LOG_1ST_ARG_AND_APPROVE = (
    b"\x09"  # pragma version 9
    b"\x36\x1A\x00"  # txna ApplicationArgs 0
    b"\xB0"  # log
    b"\x81\x01"  # pushint 1
)
ALWAYS_APPROVE = (
    b"\x09"  # pragma version 9
    b"\x81\x01"  # pushint 1
)
