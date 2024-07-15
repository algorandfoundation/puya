import typing

from algopy import Bytes, log, subroutine, uenumerate

from test_cases.iteration.base import IterationTestBase


class TupleIterationTest(IterationTestBase):
    @typing.override
    @subroutine
    def test_forwards(self) -> None:
        for i in (Bytes(b"a"), Bytes(b"b"), Bytes(b"c")):
            log(i)

    @typing.override
    @subroutine
    def test_reversed(self) -> None:
        for i in reversed((Bytes(b"a"), Bytes(b"b"), Bytes(b"c"))):
            log(i)

    @typing.override
    @subroutine
    def test_forwards_with_forwards_index(self) -> None:
        for idx, i in uenumerate((Bytes(b"a"), Bytes(b"b"), Bytes(b"c"))):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_forwards_with_reverse_index(self) -> None:
        for idx, i in reversed(uenumerate(reversed((Bytes(b"a"), Bytes(b"b"), Bytes(b"c"))))):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_reverse_with_forwards_index(self) -> None:
        for idx, i in uenumerate(reversed((Bytes(b"a"), Bytes(b"b"), Bytes(b"c")))):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_reverse_with_reverse_index(self) -> None:
        for idx, i in reversed(uenumerate((Bytes(b"a"), Bytes(b"b"), Bytes(b"c")))):
            self._log_with_index(idx, i)

    @typing.override
    @subroutine
    def test_empty(self) -> None:
        """empty tuples not supported (yet)"""
        # i: Bytes
        # for i in ():
        #     log(i)
        # for i in reversed(()):
        #     log(i)
        # for idx, i in uenumerate(()):
        #     log(idx)
        #     log(i)
        # for idx, i in reversed(uenumerate(reversed(()))):
        #     log(idx)
        #     log(i)
        # for idx, i in uenumerate(reversed(())):
        #     log(idx)
        #     log(i)
        # for idx, i in reversed(uenumerate(())):
        #     log(idx)
        #     log(i)

    @typing.override
    @subroutine
    def test_break(self) -> None:
        for x in (Bytes(b"a"), Bytes(b"b"), Bytes(b"c")):
            log(x)
            break
