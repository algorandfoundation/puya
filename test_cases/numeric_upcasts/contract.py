# ruff: noqa
from algopy import *


class BooleanBinaryOps(BaseContract):
    def approval_program(self) -> bool:
        boolean = False
        uint64 = UInt64(3)
        biguint = BigUInt(5)

        # assert boolean * boolean == 0           # Unsupported
        assert boolean * uint64 == UInt64(0)
        assert boolean * biguint == BigUInt(0)
        # assert boolean * False == 0             # Unsupported
        # assert boolean * 2 == 0                 # Unsupported
        assert boolean * UInt64(3) == UInt64(0)
        assert boolean * BigUInt(5) == BigUInt(0)

        # assert False * boolean == 0             # Unsupported
        assert False * uint64 == UInt64(0)
        assert False * biguint == BigUInt(0)
        assert False * False == 0
        assert False * 2 == 0
        assert False * UInt64(3) == UInt64(0)
        assert False * BigUInt(5) == BigUInt(0)

        # assert 2 * boolean == 0                 # Unsupported
        assert 2 * uint64 == UInt64(6)
        assert 2 * biguint == BigUInt(10)
        assert 2 * False == 0
        assert 2 * 2 == 4
        assert 2 * UInt64(3) == UInt64(6)
        assert 2 * BigUInt(5) == BigUInt(10)

        assert uint64 * boolean == UInt64(0)
        assert uint64 * uint64 == UInt64(9)
        assert uint64 * biguint == BigUInt(15)
        assert uint64 * False == UInt64(0)
        assert uint64 * 2 == UInt64(6)
        assert uint64 * UInt64(3) == UInt64(9)
        assert uint64 * BigUInt(5) == BigUInt(15)

        assert UInt64(3) * boolean == UInt64(0)
        assert UInt64(3) * uint64 == UInt64(9)
        assert UInt64(3) * biguint == BigUInt(15)
        assert UInt64(3) * False == UInt64(0)
        assert UInt64(3) * 2 == UInt64(6)
        assert UInt64(3) * UInt64(3) == UInt64(9)
        assert UInt64(3) * BigUInt(5) == BigUInt(15)

        assert biguint * boolean == UInt64(0)
        assert biguint * uint64 == UInt64(15)
        assert biguint * biguint == BigUInt(25)
        assert biguint * False == BigUInt(0)
        assert biguint * 2 == BigUInt(10)
        assert biguint * UInt64(3) == BigUInt(15)
        assert biguint * BigUInt(5) == BigUInt(25)

        assert BigUInt(5) * boolean == BigUInt(0)
        assert BigUInt(5) * uint64 == BigUInt(15)
        assert BigUInt(5) * biguint == BigUInt(25)
        assert BigUInt(5) * False == BigUInt(0)
        assert BigUInt(5) * 2 == BigUInt(10)
        assert BigUInt(5) * UInt64(3) == BigUInt(15)
        assert BigUInt(5) * BigUInt(5) == BigUInt(25)

        return True

    def clear_state_program(self) -> bool:
        return True
