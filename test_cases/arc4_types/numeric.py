import typing
import typing as t

from algopy import BigUInt, Bytes, Contract, OnCompleteAction, Txn, UInt64, op
from algopy.arc4 import (
    BigUFixedNxM,
    BigUIntN,
    Byte,
    Tuple,
    UFixedNxM,
    UInt8,
    UInt16,
    UInt32,
    UInt64 as ARC4UInt64,
    UInt512,
    UIntN,
)

Decimal: t.TypeAlias = UFixedNxM[t.Literal[64], t.Literal[10]]

ARC4BigUInt: t.TypeAlias = BigUIntN[t.Literal[128]]


sixty_four_byte_num = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # noqa: E501


class Arc4NumericTypesContract(Contract):
    def approval_program(self) -> bool:
        uint8 = UInt64(255)

        int8_encoded = UInt8(uint8)

        int8_decoded = int8_encoded.native

        assert uint8 == int8_decoded

        test_bytes = Bytes.from_hex("7FFFFFFFFFFFFFFF00")
        assert UInt8.from_bytes(test_bytes[:1]).native == 2**8 - 1 - 2**7
        assert UIntN[typing.Literal[24]].from_bytes(test_bytes[:3]).native == 2**24 - 1 - 2**23
        assert UInt16.from_bytes(test_bytes[:2]).native == 2**16 - 1 - 2**15
        assert UInt32.from_bytes(test_bytes[:4]).native == 2**32 - 1 - 2**31
        assert ARC4UInt64.from_bytes(test_bytes[:8]).native == 2**64 - 1 - 2**63
        assert UInt8(1 if Txn.num_app_args else 2) == 2
        assert UInt512(1 if Txn.num_app_args else 2) == 2

        decimals = Decimal("145.6853943940")

        assert decimals.bytes == op.itob(145_6853943940)

        decimals_from_truncated_str = Decimal("145.0")

        assert decimals_from_truncated_str.bytes == op.itob(145_0000000000)

        thousand = Decimal("1e3")

        assert thousand.bytes.length == 8
        assert thousand.bytes == op.itob(1000_0000000000)

        one_decimal = Decimal("1.0")

        assert one_decimal.bytes == op.itob(1_0000000000)

        zero_decimal = Decimal("0.0")

        assert zero_decimal.bytes == op.itob(0)

        small_decimal = Decimal("0.00000001")

        assert small_decimal.bytes == op.itob(100)

        smaller_decimal = Decimal("1E-9")

        assert smaller_decimal.bytes == op.itob(10)

        smallest_decimal = Decimal("0.0000000001")

        assert smallest_decimal.bytes == op.itob(1)

        sixty_four_decimal = Decimal("1844674407.3709551615")

        assert sixty_four_decimal.bytes == op.itob(1844674407_3709551615)

        really_big_int = BigUIntN[t.Literal[512]](sixty_four_byte_num)

        assert really_big_int == BigUIntN[t.Literal[512]].from_bytes(really_big_int.bytes)

        really_big_decimal = BigUFixedNxM[t.Literal[512], t.Literal[2]].from_bytes(
            BigUInt(sixty_four_byte_num).bytes
        )

        assert Decimal("1844674407.3709551615" if Txn.num_app_args else "0.0") == Decimal()

        biguint = BigUInt(1)
        arc4_biguint_const = ARC4BigUInt(1)
        arc4_biguint_dynamic = ARC4BigUInt(biguint + 1)

        assert biguint == arc4_biguint_const.native

        assert arc4_biguint_dynamic.bytes.length == (128 // 8)

        assert really_big_decimal.bytes.length == 64

        # check UInt64 sub-types are converted properly
        tup = Tuple((ARC4UInt64(OnCompleteAction.ClearState),))
        assert tup[0].native == OnCompleteAction.ClearState

        return True

    def clear_state_program(self) -> bool:
        assert BigUInt.from_bytes(Decimal().bytes) == 0
        assert BigUInt.from_bytes(BigUFixedNxM[t.Literal[512], t.Literal[5]]().bytes) == 0
        assert Byte() == 0
        assert ARC4UInt64() == 0
        assert UInt512() == 0

        return True
