import typing

from algopy import Bytes, log, subroutine, uenumerate, urange

from test_cases.iteration.base import IterationTestBase


class URangeIterationTest(IterationTestBase):
    @typing.override
    @subroutine
    def test_forwards(self) -> None:
        values = Bytes(b" a b c")
        for i in urange(1, 7, 2):
            log(values[i])
            i += 1

    @typing.override
    @subroutine
    def test_reversed(self) -> None:
        values = Bytes(b" a b c")
        for i in reversed(urange(1, 7, 2)):
            log(values[i])
            i += 1

    @typing.override
    @subroutine
    def test_forwards_with_forwards_index(self) -> None:
        values = Bytes(b" a b c")
        for idx, i in uenumerate(urange(1, 7, 2)):
            self._log_with_index(idx, values[i])
            i += 1
            idx += 1

    @typing.override
    @subroutine
    def test_forwards_with_reverse_index(self) -> None:
        values = Bytes(b" a b c")
        for idx, i in reversed(uenumerate(reversed(urange(1, 7, 2)))):
            self._log_with_index(idx, values[i])
            i += 1
            idx += 1

    @typing.override
    @subroutine
    def test_reverse_with_forwards_index(self) -> None:
        values = Bytes(b" a b c")
        for idx, i in uenumerate(reversed(urange(1, 7, 2))):
            self._log_with_index(idx, values[i])
            i += 1
            idx += 1

    @typing.override
    @subroutine
    def test_reverse_with_reverse_index(self) -> None:
        values = Bytes(b" a b c")
        for idx, i in reversed(uenumerate(urange(1, 7, 2))):
            self._log_with_index(idx, values[i])
            i += 1
            idx += 1

    @typing.override
    @subroutine
    def test_empty(self) -> None:
        for i in urange(0):
            log(i)
        for i in reversed(urange(0)):
            log(i)
        for idx, i in uenumerate(urange(0)):
            log(idx, i)
        for idx, i in reversed(uenumerate(reversed(urange(0)))):
            log(idx, i)
        for idx, i in uenumerate(reversed(urange(0))):
            log(idx, i)
        for idx, i in reversed(uenumerate(urange(0))):
            log(idx, i)

    @typing.override
    @subroutine
    def test_break(self) -> None:
        values = Bytes(b" a b c")
        for i in urange(1, 7, 2):
            log(values[i])
            break

    @typing.override
    @subroutine
    def test_tuple_target(self) -> None:
        values = Bytes(b"t")
        for tup in uenumerate(urange(1)):
            self._log_with_index(tup[0], values[tup[1]])
