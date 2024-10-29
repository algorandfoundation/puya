from algopy import arc4, subroutine


class MutableParams2(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_array_rebinding(self) -> None:
        a = arc4.DynamicBytes(0)
        self.maybe_modify_array(a, assign_local=True)
        assert a == arc4.DynamicBytes(0, 1)

        a = arc4.DynamicBytes(1)
        self.maybe_modify_array(a, assign_local=False)
        assert a == arc4.DynamicBytes(1, 42, 4)

    @subroutine
    def maybe_modify_array(self, a: arc4.DynamicBytes, *, assign_local: bool) -> None:  # v0
        if assign_local:
            a.append(arc4.Byte(1))  # v1: modify out
            a = arc4.DynamicBytes(1, 2, 3)  # v2: BOUNDARY
            a.append(arc4.Byte(4))  # v3: local only
            a = arc4.DynamicBytes(1, 2, 4)  # v4: local only
        else:
            a.append(arc4.Byte(42))  # v5: modify out

        a.append(arc4.Byte(4))  # v6: modify out IF not b ELSE local only
