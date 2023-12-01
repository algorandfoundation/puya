from algopy import Contract, UInt64, itob, log, uenumerate, urange

LOOP_ITERATIONS = 2  # max op code budget is exceeded with more


class Nested(Contract):
    def approval_program(self) -> UInt64:
        n = UInt64(LOOP_ITERATIONS)
        x = UInt64(0)

        for a in urange(n):
            for b in urange(n):
                for c in urange(n):
                    for d in urange(n):
                        for e in urange(n):
                            for f in urange(n):
                                x += a + b + c + d + e + f
            # Iterator variable should be mutable, but mutating it
            # should not affect the next iteration
            a += n

        log(itob(x))

        y = UInt64(0)
        for index, item in uenumerate(urange(UInt64(10))):
            y += item * index

        log(itob(y))
        return x

    def clear_state_program(self) -> UInt64:
        return UInt64(1)
