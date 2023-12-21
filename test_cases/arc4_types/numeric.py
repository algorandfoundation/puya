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

        int8_encoded = UInt8.encode(uint8)

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

        really_big_int = BigUIntN[t.Literal[512]](sixty_four_byte_num)

        assert really_big_int.bytes.length == 64
        assert really_big_int == BigUIntN[t.Literal[512]].encode(really_big_int.decode())

        really_big_decimal = BigUFixedNxM[t.Literal[512], t.Literal[2]].encode(
            BigUInt(sixty_four_byte_num)
        )

        biguint = BigUInt(1)
        arc4_biguint_const = ARC4BigUInt(1)
        arc4_biguint_dynamic = ARC4BigUInt.encode(biguint + 1)

        assert biguint == arc4_biguint_const.decode()

        assert arc4_biguint_dynamic.bytes.length == (128 // 8)

        assert really_big_decimal.bytes.length == 64

        return True

    def clear_state_program(self) -> bool:
        return True
