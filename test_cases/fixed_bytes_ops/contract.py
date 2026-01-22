import typing

from algopy import (
    Account,
    Box,
    Bytes,
    Contract,
    FixedArray,
    FixedBytes,
    LocalState,
    UInt64,
    log,
    size_of,
    subroutine,
    uenumerate,
    zero_bytes,
)
from algopy.op import Txn


class FixedBytesOps(Contract):
    def __init__(self) -> None:
        self.local = LocalState(FixedBytes[typing.Literal[4]])
        self.box = Box(FixedBytes[typing.Literal[5]])

    def approval_program(self) -> bool:
        if Txn.num_app_args > 0:
            method = Txn.application_args(0)
            if Txn.num_app_args == 1:
                if method == b"get_state_data_or_assert":
                    log(self.get_state_data_or_assert(Txn.sender))
                elif method == b"get_box_data":
                    log(self.box.value)
            elif Txn.num_app_args == 2:
                if method == b"set_state_data":
                    self.set_state_data(
                        Txn.sender,
                        FixedBytes[typing.Literal[4]].from_bytes(Txn.application_args(1)),
                    )
                elif method == b"set_box_data":
                    self.box.value = FixedBytes[typing.Literal[5]](Txn.application_args(1))
                elif method == b"validate_fixed_bytes_3":
                    self.validate_fixed_bytes_3(
                        FixedBytes[typing.Literal[3]].from_bytes(Txn.application_args(1))
                    )
            elif Txn.num_app_args == 3:
                if method == b"test_augmented_or_assignment_with_bytes":
                    self.test_augmented_or_assignment_with_bytes(
                        FixedBytes[typing.Literal[1]].from_bytes(Txn.application_args(1)),
                        Txn.application_args(2),
                    )
                elif method == b"test_augmented_and_assignment_with_bytes":
                    self.test_augmented_and_assignment_with_bytes(
                        FixedBytes[typing.Literal[1]].from_bytes(Txn.application_args(1)),
                        Txn.application_args(2),
                    )
                elif method == b"test_augmented_xor_assignment_with_bytes":
                    self.test_augmented_xor_assignment_with_bytes(
                        FixedBytes[typing.Literal[1]].from_bytes(Txn.application_args(1)),
                        Txn.application_args(2),
                    )
        else:
            test_binary_ops(FixedBytes.from_hex("FF"), FixedBytes.from_hex("0F"))

            test_binary_ops_with_fixed_bytes_of_different_size(
                FixedBytes.from_hex("FF"), FixedBytes.from_hex("0F0F")
            )

            test_binary_ops_with_bytes_of_different_size(
                FixedBytes.from_hex("FF"), Bytes.from_hex("0F0F")
            )

            test_binary_ops_with_literal_bytes(FixedBytes.from_hex("FF"))

            test_augmented_assignment_with_invalid_lengths(
                FixedBytes[typing.Literal[3]].from_bytes(b"\xf0\xf0\xf0\xf0"),
                FixedBytes[typing.Literal[3]].from_bytes(Bytes.from_hex("0f0f")),
            )

            test_augmented_assignment(FixedBytes.from_hex("F0"), FixedBytes.from_hex("0F"))

            test_augmented_assignment_with_bytes(FixedBytes.from_hex("F0"), Bytes.from_hex("0F"))

            test_augmented_assignment_with_literal_bytes(FixedBytes.from_hex("F0"))

            test_unary_ops()

            test_comparison_ops()

            test_sequence_ops(FixedBytes.from_bytes(b"\xab\xcd\x12\x34"))

            test_sequence_ops(
                FixedBytes[typing.Literal[4]].from_bytes(Bytes.from_hex("ABCD12345678"))
            )

            test_construction()

            test_iteration()

            test_size_of()

            test_passing_fixed_bytes()

            test_contains_fixed_bytes(
                FixedBytes.from_hex("ABCD1234"), FixedBytes.from_bytes(Bytes.from_hex("CD12"))
            )

            test_contains_bytes(FixedBytes.from_hex("ABCD1234"), Bytes.from_hex("CD12"))

            test_contains_literal_bytes(FixedBytes.from_hex("ABCD1234"))
            result = FixedBytes[typing.Literal[5]](b"hello")
            log(result)

        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def set_state_data(self, for_account: Account, value: FixedBytes[typing.Literal[4]]) -> None:
        self.local[for_account] = value

    @subroutine
    def get_state_data_or_assert(self, for_account: Account) -> FixedBytes[typing.Literal[4]]:
        result, exists = self.local.maybe(for_account)
        assert exists, "no data for account"
        return result

    @subroutine
    def test_augmented_or_assignment_with_bytes(
        self, val: FixedBytes[typing.Literal[1]], other: Bytes
    ) -> None:
        val1 = val
        val1 |= other
        log(val1)

    @subroutine
    def test_augmented_and_assignment_with_bytes(
        self, val: FixedBytes[typing.Literal[1]], other: Bytes
    ) -> None:
        val1 = val
        val1 &= other
        log(val1)

    @subroutine
    def test_augmented_xor_assignment_with_bytes(
        self, val: FixedBytes[typing.Literal[1]], other: Bytes
    ) -> None:
        val1 = val
        val1 ^= other
        log(val1)

    @subroutine
    def validate_fixed_bytes_3(self, val: FixedBytes[typing.Literal[3]]) -> None:
        val.validate()


@subroutine
def test_binary_ops(
    left: FixedBytes[typing.Literal[1]], right: FixedBytes[typing.Literal[1]]
) -> None:
    """Test binary operations: |, &, ^, +"""

    # Bitwise OR
    result = left | right
    assert result == FixedBytes[typing.Literal[1]].from_hex("FF")

    # Reverse bitwise OR
    result = right | left
    assert result == FixedBytes[typing.Literal[1]].from_hex("FF")

    # Bitwise XOR
    result = left ^ right
    assert result == FixedBytes[typing.Literal[1]].from_hex("F0")

    # Reverse bitwise XOR
    result = right ^ left
    assert result == FixedBytes[typing.Literal[1]].from_hex("F0")

    # Bitwise AND
    result = left & right
    assert result == FixedBytes[typing.Literal[1]].from_hex("0F")

    # Reverse bitwise AND
    result = right & left
    assert result == FixedBytes[typing.Literal[1]].from_hex("0F")

    # Concatenation (returns Bytes)
    concat_result = left + right
    assert concat_result == Bytes.from_hex("FF0F")

    # Reverse concatenation
    concat_result = right + left
    assert concat_result == Bytes.from_hex("0FFF")


@subroutine
def test_binary_ops_with_fixed_bytes_of_different_size(
    left: FixedBytes[typing.Literal[1]], right: FixedBytes[typing.Literal[2]]
) -> None:
    """Test binary operations: |, &, ^, +"""

    result = left | right
    assert result == Bytes.from_hex("0FFF")

    # Reverse bitwise OR
    result = right | left
    assert result == Bytes.from_hex("0FFF")

    # Bitwise XOR
    result = left ^ right
    assert result == Bytes.from_hex("0FF0")

    # Reverse bitwise XOR
    result = right ^ left
    assert result == Bytes.from_hex("0FF0")

    # Bitwise AND
    result = left & right
    assert result == Bytes.from_hex("000F")

    # Reverse bitwise AND
    result = right & left
    assert result == Bytes.from_hex("000F")

    # Concatenation (returns Bytes)
    concat_result = left + right
    assert concat_result == Bytes.from_hex("FF0F0F")

    # Reverse concatenation
    concat_result = right + left
    assert concat_result == Bytes.from_hex("0F0FFF")


@subroutine
def test_binary_ops_with_bytes_of_different_size(
    left: FixedBytes[typing.Literal[1]], right: Bytes
) -> None:
    """Test binary operations: |, &, ^, +"""

    # Bitwise OR
    result = left | right
    assert result == Bytes.from_hex("0FFF")

    # Reverse bitwise OR
    result = right | left
    assert result == Bytes.from_hex("0FFF")

    # Bitwise XOR
    result = left ^ right
    assert result == Bytes.from_hex("0FF0")

    # Reverse bitwise XOR
    result = right ^ left
    assert result == Bytes.from_hex("0FF0")

    # Bitwise AND
    result = left & right
    assert result == Bytes.from_hex("000F")

    # Reverse bitwise AND
    result = right & left
    assert result == Bytes.from_hex("000F")

    # Concatenation (returns Bytes)
    concat_result = left + right
    assert concat_result == Bytes.from_hex("FF0F0F")

    # Reverse concatenation
    concat_result = right + left
    assert concat_result == Bytes.from_hex("0F0FFF")


@subroutine
def test_binary_ops_with_literal_bytes(left: FixedBytes[typing.Literal[1]]) -> None:
    """Test binary operations: |, &, ^, +"""

    # Bitwise OR
    result = left | b"\x0f\x0f"
    assert result == Bytes.from_hex("0FFF")

    # Reverse bitwise OR
    result = b"\x0f\x0f" | left
    assert result == Bytes.from_hex("0FFF")

    # Bitwise XOR
    result = left ^ b"\x0f\x0f"
    assert result == Bytes.from_hex("0FF0")

    # Reverse bitwise XOR
    result = b"\x0f\x0f" ^ left
    assert result == Bytes.from_hex("0FF0")

    # Bitwise AND
    result = left & b"\x0f\x0f"
    assert result == Bytes.from_hex("000F")

    # Reverse bitwise AND
    result = b"\x0f\x0f" & left
    assert result == Bytes.from_hex("000F")

    # Concatenation (returns Bytes)
    concat_result = left + b"\x0f\x0f"
    assert concat_result == Bytes.from_hex("FF0F0F")

    # Reverse concatenation
    concat_result = b"\x0f\x0f" + left
    assert concat_result == Bytes.from_hex("0F0FFF")


@subroutine
def test_augmented_assignment_with_invalid_lengths(
    val: FixedBytes[typing.Literal[3]], other: FixedBytes[typing.Literal[3]]
) -> None:
    val1 = val
    val1 |= other
    assert val1 == Bytes.from_hex("F0F0FFFF")

    # Test &=
    val2 = val
    val2 &= other
    assert val2 == Bytes.from_hex("00000000")

    # Test ^=
    val3 = val
    val3 ^= other
    assert val3 == Bytes.from_hex("F0F0FFFF")


@subroutine
def test_augmented_assignment(
    val: FixedBytes[typing.Literal[1]], other: FixedBytes[typing.Literal[1]]
) -> None:
    """Test augmented assignment operations: |=, &=, ^=, +="""
    # Test |=
    val1 = val
    val1 |= other
    assert val1 == Bytes.from_hex("FF")

    # Test &=
    val2 = val
    val2 &= other
    assert val2 == Bytes.from_hex("00")

    # Test ^=
    val3 = val
    val3 ^= other
    assert val3 == Bytes.from_hex("FF")

    bytes_value = val + b"test"
    bytes_value += other
    assert bytes_value.length == 6


@subroutine
def test_augmented_assignment_with_bytes(val: FixedBytes[typing.Literal[1]], other: Bytes) -> None:
    """Test augmented assignment operations: |=, &=, ^=, +="""
    # Test |=
    val1 = val
    val1 |= other
    assert val1 == Bytes.from_hex("FF")

    # Test &=
    val2 = val
    val2 &= other
    assert val2 == Bytes.from_hex("00")

    # Test ^=
    val3 = val
    val3 ^= other
    assert val3 == Bytes.from_hex("FF")


@subroutine
def test_augmented_assignment_with_literal_bytes(val: FixedBytes[typing.Literal[1]]) -> None:
    """Test augmented assignment operations: |=, &=, ^=, +="""
    # Test |=
    val1 = val
    val1 |= b"\x0f"
    assert val1 == Bytes.from_hex("FF")

    # Test &=
    val2 = val
    val2 &= b"\x0f"
    assert val2 == Bytes.from_hex("00")

    # Test ^=
    val3 = val
    val3 ^= b"\x0f"
    assert val3 == Bytes.from_hex("FF")


@subroutine
def test_unary_ops() -> None:
    """Test unary operations: ~, bool"""

    # Bitwise invert
    val = FixedBytes[typing.Literal[1]].from_hex("0F")
    inverted = ~val
    assert inverted == FixedBytes[typing.Literal[1]].from_hex("F0")


@subroutine
def test_comparison_ops() -> None:
    """Test comparison operations: ==, !="""
    val1 = FixedBytes[typing.Literal[2]].from_hex("ABCD")
    val2 = FixedBytes[typing.Literal[2]].from_hex("ABCD")
    val3 = FixedBytes[typing.Literal[2]].from_hex("1234")

    # Equality
    assert val1 == val2
    assert val1 == Bytes.from_hex("ABCD")
    assert val1 == b"\xab\xcd"

    assert val2 == val1
    assert Bytes.from_hex("ABCD") == val1
    assert b"\xab\xcd" == val1  # noqa: SIM300

    # Inequality
    assert val1 != val3
    assert val1 != Bytes.from_hex("1234")
    assert val1 != b"\x12\x34"

    assert val3 != val1
    assert Bytes.from_hex("1234") != val1
    assert b"\x12\x34" != val1  # noqa: SIM300

    # invalid length
    val4 = FixedBytes[typing.Literal[3]].from_bytes(b"\xab\xcd\x12\x34\x56")
    assert val4 == b"\xab\xcd\x12\x34\x56"
    assert val4.length == 3

    val5 = FixedBytes[typing.Literal[3]](b"\xab\xcd\x12")
    assert val4 != val5

    val6 = FixedBytes[typing.Literal[2]].from_bytes(b"\xab\xcd\x12")
    val7 = FixedBytes[typing.Literal[2]].from_bytes(b"\xab\xcd\x12")
    assert val6 == val7


@subroutine(inline=False)
def test_sequence_ops(val: FixedBytes[typing.Literal[4]]) -> None:
    """Test sequence operations: indexing, slicing, iteration, contains, length"""

    # Length property
    assert val.length == UInt64(4)

    # Indexing (returns Bytes)
    first_byte = val[0]
    assert first_byte == Bytes.from_hex("AB")

    last_byte = val[3]
    assert last_byte == Bytes.from_hex("34")
    assert last_byte == val[-1]

    # Slicing (returns Bytes)
    slice_result = val[1:3]
    assert slice_result == Bytes.from_hex("CD12")

    slice_result = val[:2]
    assert slice_result == Bytes.from_hex("ABCD")

    slice_result = val[2:]
    assert slice_result == Bytes.from_hex("1234")

    slice_result = val[:-1]
    assert slice_result == Bytes.from_hex("ABCD12")

    slice_result = val[-2:]
    assert slice_result == Bytes.from_hex("1234")

    slice_result = val[-3:-1]
    assert slice_result == Bytes.from_hex("CD12")

    # Iteration
    count = UInt64(0)
    for _byte in val:
        count += 1
    assert count == 4

    # Reverse iteration
    count = UInt64(0)
    for _byte in reversed(val):
        count += 1
    assert count == 4


@subroutine
def test_construction() -> None:
    """Test construction and conversion methods"""
    # from_hex
    hex_val = FixedBytes[typing.Literal[2]].from_hex("ABCD")
    assert hex_val == b"\xab\xcd"

    # from_base64
    base64_val = FixedBytes[typing.Literal[2]].from_base64("q80=")  # "ABCD" in base64
    assert base64_val == b"\xab\xcd"

    # from_base32
    base32_val = FixedBytes[typing.Literal[2]].from_base32("VPGQ====")  # "ABCD" in base32
    assert base32_val == b"\xab\xcd"

    # Direct initialization
    direct_val = FixedBytes[typing.Literal[2]](b"\xab\xcd")
    assert direct_val == Bytes(b"\xab\xcd")

    # .bytes property (from BytesBacked)
    bytes_val = hex_val.bytes
    assert bytes_val == Bytes.from_hex("ABCD")

    # from_bytes class method (from BytesBacked)
    from_bytes_val = FixedBytes[typing.Literal[2]].from_bytes(Bytes.from_hex("ABCD"))
    assert from_bytes_val == b"\xab\xcd"

    from_txn_sender = FixedBytes[typing.Literal[32]](Txn.sender.bytes)
    assert from_txn_sender.length == 32

    empty_1 = FixedBytes[typing.Literal[4]]()
    assert empty_1 == b"\x00\x00\x00\x00"

    empty_2 = FixedBytes[typing.Literal[0]]()
    assert empty_2 == b""

    abc = FixedBytes[typing.Literal[3]](b"123" if Txn.application_id == 123 else b"abc")
    assert abc.bytes.length == 3


FB1 = FixedBytes[typing.Literal[1]]


@subroutine
def test_iteration() -> None:
    # from_hex
    val: FixedBytes[typing.Literal[3]] = FixedBytes.from_hex("ABCDEF")
    result = Bytes()

    for item in val:
        result += item
    assert result == val

    for idx, byte in uenumerate(val):
        assert byte == val[idx]
        assert FB1(byte) == val[idx]

        assert byte in val
        assert FB1(byte) in val

    exploded = tuple[Bytes, Bytes, Bytes](val)  # type: ignore[arg-type]
    assert exploded[0] == Bytes.from_hex("AB")
    assert exploded[-1] == Bytes.from_hex("EF")


@subroutine
def test_size_of() -> None:
    hex_val = FixedBytes[typing.Literal[2]].from_hex("ABCD")
    assert size_of(hex_val) == 2
    assert hex_val.length == 2

    from_txn_sender = FixedBytes[typing.Literal[32]](Txn.sender.bytes)
    assert size_of(from_txn_sender) == 32
    assert from_txn_sender.length == 32

    from_bytes_empty = FixedBytes[typing.Literal[16]].from_bytes(Bytes())
    assert size_of(from_bytes_empty) == 16

    from_bytes_less = FixedBytes[typing.Literal[16]].from_bytes(Bytes(b"ABCD"))
    assert size_of(from_bytes_less) == 16

    from_bytes_more = FixedBytes[typing.Literal[2]].from_bytes(Bytes(b"ABCD"))
    assert size_of(from_bytes_more) == 2

    empty = FixedBytes[typing.Literal[4]]()
    assert size_of(empty) == 4
    assert empty.length == 4

    arr = zero_bytes(FixedArray[FixedBytes[typing.Literal[4]], typing.Literal[8]])
    assert size_of(arr) == 32  # 4 bytes * 8 elements = 32 bytes

    for v in arr:
        assert v == FixedBytes[typing.Literal[4]]()


@subroutine
def test_passing_fixed_bytes() -> None:
    assert bytes_to_bool(FixedBytes(Bytes(b"yay")))
    assert not bytes_to_bool(FixedBytes(b"nay"))

    assert bool_to_bytes(True) == FixedBytes(b"yay")
    assert bool_to_bytes(False) == FixedBytes(Bytes(b"nay"))


@subroutine
def bool_to_bytes(x: bool) -> FixedBytes[typing.Literal[3]]:
    return FixedBytes[typing.Literal[3]](b"yay" if x else b"nay")


@subroutine
def bytes_to_bool(x: FixedBytes[typing.Literal[3]]) -> bool:
    return x == FixedBytes[typing.Literal[3]](b"yay")


@subroutine
def test_contains_fixed_bytes(
    x: FixedBytes[typing.Literal[4]], y: FixedBytes[typing.Literal[2]]
) -> None:
    assert x in x  # noqa: PLR0124
    assert y in x
    assert x not in y

    assert (x not in x) == False  # noqa: E712, PLR0124
    assert (y not in x) == False  # noqa: E712
    assert (x in y) == False  # noqa: E712


@subroutine
def test_contains_bytes(x: FixedBytes[typing.Literal[4]], y: Bytes) -> None:
    assert y in x
    assert x not in y

    assert (y not in x) == False  # noqa: E712
    assert (x in y) == False  # noqa: E712


@subroutine
def test_contains_literal_bytes(x: FixedBytes[typing.Literal[4]]) -> None:
    assert b"\xcd\x12" in x

    assert (b"\xcd\x12" not in x) == False  # noqa: E712
