import abc

from algopy import Bytes, Contract, UInt64, log, subroutine


class IterationTestBase(Contract, abc.ABC):
    def approval_program(self) -> bool:
        log("test_forwards")
        self.test_forwards()
        log("test_reversed")
        self.test_reversed()
        log("test_forwards_with_forwards_index")
        self.test_forwards_with_forwards_index()
        log("test_forwards_with_reverse_index")
        self.test_forwards_with_reverse_index()
        log("test_reverse_with_forwards_index")
        self.test_reverse_with_forwards_index()
        log("test_reverse_with_reverse_index")
        self.test_reverse_with_reverse_index()
        log("test_empty")
        self.test_empty()
        log("test_break")
        self.test_break()
        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def _log_with_index(self, idx: UInt64, value: Bytes) -> None:
        digits = Bytes(b"0123456789")
        log(digits[idx], value, sep="=")

    @subroutine
    @abc.abstractmethod
    def test_forwards(self) -> None: ...

    @subroutine
    @abc.abstractmethod
    def test_reversed(self) -> None: ...

    @subroutine
    @abc.abstractmethod
    def test_forwards_with_forwards_index(self) -> None: ...

    @subroutine
    @abc.abstractmethod
    def test_forwards_with_reverse_index(self) -> None: ...

    @subroutine
    @abc.abstractmethod
    def test_reverse_with_forwards_index(self) -> None: ...

    @subroutine
    @abc.abstractmethod
    def test_reverse_with_reverse_index(self) -> None: ...

    @subroutine
    @abc.abstractmethod
    def test_empty(self) -> None: ...

    @subroutine
    @abc.abstractmethod
    def test_break(self) -> None: ...
