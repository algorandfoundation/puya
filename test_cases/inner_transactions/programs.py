LOG_1ST_ARG_AND_APPROVE = (
    b"\x0A"  # pragma version 10
    b"\x36\x1A\x00"  # txna ApplicationArgs 0
    b"\xB0"  # log
    b"\x81\x01"  # pushint 1
)
ALWAYS_APPROVE = (
    b"\x0A"  # pragma version 10
    b"\x81\x01"  # pushint 1
)
HELLO_WORLD_CLEAR = ALWAYS_APPROVE
HELLO_WORLD_APPROVAL_HEX = (
    "0a200101311b410026800402bece1136"
    "1a008e0100010031191444311844361a"
    "018800158004151f7c754c50b0224331"
    "1914443118144422438a01018bff5702"
    "00800748656c6c6f2c204c5049151657"
    "06004c5089"
)
