import abc

from algopy import ARC4Contract, arc4, log


class GP(ARC4Contract, abc.ABC):
    def __init__(self) -> None:
        log("gp.__init__")
        super().__init__()

    @arc4.abimethod(create="require")
    def create(self) -> None:
        pass

    @arc4.abimethod
    def method(self) -> None:
        log("gp.method")
