import typing

from algopy import Bytes, log, subroutine, uenumerate

from test_cases.iteration.base import IterationTestBase


class IndexableIterationTest(IterationTestBase):
    @typing.override
    @subroutine
    def test_forwards(self) -> None:
        for i in Bytes(b"abc"):
            log(i)

    @typing.override
    @subroutine
    def test_reversed(self) -> None:
        for i in reversed(Bytes(b"abc")):
            log(i)

    @typing.override
    @subroutine
    def test_forwards_with_forwards_index(self) -> None:
        for idx, i in uenumerate(Bytes(b"abc")):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_forwards_with_reverse_index(self) -> None:
        for idx, i in reversed(uenumerate(reversed(Bytes(b"abc")))):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_reverse_with_forwards_index(self) -> None:
        for idx, i in uenumerate(reversed(Bytes(b"abc"))):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_reverse_with_reverse_index(self) -> None:
        for idx, i in reversed(uenumerate(Bytes(b"abc"))):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_empty(self) -> None:
        for i in Bytes():
            log(i)
        for i in reversed(Bytes()):
            log(i)
        for idx, i in uenumerate(Bytes()):
            self._log_with_index(idx, i)
        for idx, i in reversed(uenumerate(reversed(Bytes()))):
            self._log_with_index(idx, i)
        for idx, i in uenumerate(reversed(Bytes())):
            self._log_with_index(idx, i)
        for idx, i in reversed(uenumerate(Bytes())):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_break(self) -> None:
        for b in Bytes(b"abc"):
            log(b)
            break
