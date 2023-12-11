from puyapy import *  # noqa: F403 # note: star import here to explicitly test that


class MyContract(Contract):
    """My contract"""

    def approval_program(self) -> UInt64:
        a = UInt64(1)
        sum_of_evens = UInt64(0)
        product_of_odds = UInt64(0)
        while a < 100:
            if a % 5 == 0:
                continue
            if not a % 21:
                break
            if a % 2 == 0:
                sum_of_evens += a
            else:
                if product_of_odds == 0:
                    product_of_odds = a
                else:
                    product_of_odds *= a
            a += 1
        return product_of_odds - sum_of_evens

    def clear_state_program(self) -> UInt64:
        sum_of_squares = UInt64(0)
        for i in urange(1, 100):
            square_root = sqrt(i)
            if square_root * square_root == i:
                sum_of_squares += i
            if sum_of_squares > 200:
                break
        return sum_of_squares
