import typing
import typing as t

from puyapy import BigUInt, Bytes, Contract, UInt64
from puyapy.arc4 import (
    BigUFixedNxM,
    BigUIntN,
    UFixedNxM,
    UInt8,
    UInt16,
    UInt32,
    UInt64 as ARC4UInt64,
    UIntN,
)

Decimal: t.TypeAlias = UFixedNxM[t.Literal[64], t.Literal[10]]

ARC4BigUInt: t.TypeAlias = BigUIntN[t.Literal[128]]


sixty_four_byte_num = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # noqa: E501


class Arc4NumericTypesContract(Contract):
    def approval_program(self) -> bool:
        uint8 = UInt64(255)

        int8_encoded = UInt8(uint8)

        int8_decoded = int8_encoded.decode()

        assert uint8 == int8_decoded

        test_bytes = Bytes.from_hex("7FFFFFFFFFFFFFFF00")
        assert UInt8.from_bytes(test_bytes[:1]).decode() == 2**8 - 1 - 2**7
        assert (
            UIntN[typing.Literal[24]].from_bytes(test_bytes[:3]).decode() == 2**24 - 1 - 2**23
        )
        assert UInt16.from_bytes(test_bytes[:2]).decode() == 2**16 - 1 - 2**15
        assert UInt32.from_bytes(test_bytes[:4]).decode() == 2**32 - 1 - 2**31
        assert ARC4UInt64.from_bytes(test_bytes[:8]).decode() == 2**64 - 1 - 2**63

        decimals = Decimal("145.6853943940")

        assert decimals.bytes.length == (64 // 8)
        assert decimals.decode() == 145_6853943940

        decimals_from_truncated_str = Decimal("145.0")

        assert decimals_from_truncated_str.bytes.length == (64 // 8)
        assert decimals_from_truncated_str.decode() == 145_0000000000

        one_decimal = Decimal("1.0")

        assert one_decimal.bytes.length == (64 // 8)
        assert one_decimal.decode() == 1_0000000000

        zero_decimal = Decimal("0.0")

        assert zero_decimal.bytes.length == (64 // 8)
        assert zero_decimal.decode() == 0

        small_decimal = Decimal("0.00000001")

        assert small_decimal.bytes.length == (64 // 8)
        assert small_decimal.decode() == 100

        smaller_decimal = Decimal("1E-9")

        assert smaller_decimal.bytes.length == (64 // 8)
        assert smaller_decimal.decode() == 10

        smallest_decimal = Decimal("0.0000000001")

        assert smallest_decimal.bytes.length == (64 // 8)
        assert smallest_decimal.decode() == 1

        sixty_four_decimal = Decimal("1844674407.3709551615")

        assert sixty_four_decimal.bytes.length == (64 // 8)
        assert sixty_four_decimal.decode() == 1844674407_3709551615

        really_big_int = BigUIntN[t.Literal[512]](sixty_four_byte_num)

        assert really_big_int.bytes.length == 64
        assert really_big_int == BigUIntN[t.Literal[512]](really_big_int.decode())

        really_big_decimal = BigUFixedNxM[t.Literal[512], t.Literal[2]].encode(
            BigUInt(sixty_four_byte_num)
        )

        biguint = BigUInt(1)
        arc4_biguint_const = ARC4BigUInt(1)
        arc4_biguint_dynamic = ARC4BigUInt(biguint + 1)

        assert biguint == arc4_biguint_const.decode()

        assert arc4_biguint_dynamic.bytes.length == (128 // 8)

        assert really_big_decimal.bytes.length == 64

        return True

    def clear_state_program(self) -> bool:
        return True
