import typing as t

from puyapy import Contract, arc4
from puyapy.op import Txn


class MyStruct(arc4.Struct):
    x: arc4.UInt512


class Arc4BoolEvalContract(Contract):
    def approval_program(self) -> bool:
        assert not arc4.Bool(False)
        assert arc4.Bool(True)

        assert not arc4.String("")
        assert arc4.String(".")

        assert not arc4.Address()
        assert arc4.Address(Txn.sender)

        assert not arc4.UInt8(0)
        assert arc4.UInt8(1)

        assert not arc4.UInt16(0)
        assert arc4.UInt16(1)

        assert not arc4.UInt32(0)
        assert arc4.UInt32(1)

        assert not arc4.UInt64(0)
        assert arc4.UInt64(1)

        assert not arc4.UInt128(0)
        assert arc4.UInt128(1)

        assert not arc4.UInt256(0)
        assert arc4.UInt256(1)

        assert not arc4.UInt512(0)
        assert arc4.UInt512(1)

        assert not arc4.UIntN[t.Literal[24]](0)
        assert arc4.UIntN[t.Literal[24]](1)

        assert not arc4.BigUIntN[t.Literal[504]](0)
        assert arc4.BigUIntN[t.Literal[504]](1)

        assert not arc4.UFixedNxM[t.Literal[48], t.Literal[10]]("0.0")
        assert arc4.UFixedNxM[t.Literal[48], t.Literal[10]]("1.0")

        assert not arc4.BigUFixedNxM[t.Literal[496], t.Literal[10]]("0.0")
        assert arc4.BigUFixedNxM[t.Literal[496], t.Literal[10]]("0.01")

        assert not arc4.StaticArray[arc4.UInt16, t.Literal[0]]()
        assert arc4.StaticArray(arc4.UInt16(0))

        assert not arc4.StaticArray[arc4.Bool, t.Literal[0]]()
        assert arc4.StaticArray(arc4.Bool(False))

        dynamic_arr = arc4.DynamicArray[arc4.UInt64]()
        assert not dynamic_arr
        dynamic_arr.append(arc4.UInt64(0))
        assert dynamic_arr

        assert MyStruct(x=arc4.UInt512(0))

        assert arc4.Tuple((arc4.Bool(False),))

        assert arc4.Bool() == arc4.Bool(False)

        return True

    def clear_state_program(self) -> bool:
        return True
