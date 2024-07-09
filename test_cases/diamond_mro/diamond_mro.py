import abc

from algopy import ARC4Contract, log, subroutine


class GP(ARC4Contract, abc.ABC):
    def __init__(self) -> None:
        log("gp.__init__")
        super().__init__()

    @subroutine
    def method(self) -> None:
        log("gp.method")


class Base1(GP):
    def __init__(self) -> None:
        log("base1.__init__")
        super().__init__()

    @subroutine
    def method(self) -> None:
        log("base1.method")
        super().method()


class Base2(GP):
    def __init__(self) -> None:
        log("base2.__init__")
        super().__init__()

    @subroutine
    def method(self) -> None:
        log("base2.method")
        super().method()


class Derived(Base1, Base2):
    def __init__(self) -> None:
        log("derived.__init__")
        super().__init__()

    @subroutine
    def method(self) -> None:
        log("derived.method")
        super().method()
