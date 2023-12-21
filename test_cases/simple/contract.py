import puyapy as algo

from test_cases.simple import pkg_a, subs


class MyContract(algo.Contract):
    """My contract"""

    def approval_program(self) -> algo.UInt64:
        a = algo.UInt64(1) + 2
        b = algo.UInt64(4) * 5
        if (1 + 2) * (4 - 3) == a:
            if b < 2:
                b = 3 + algo.UInt64(2)
                return a + b
            else:
                b = 2 * a
                if ((3 * 4) + 2) * b:
                    return algo.UInt64(2)
                else:
                    return algo.UInt64(3)
        else:
            return pkg_a.MyUInt64(4)

    def clear_state_program(self) -> algo.UInt64:
        assert pkg_a.Txn.num_app_args() == 0
        return subs.zero() * pkg_a.pkg_1.subs.one()
