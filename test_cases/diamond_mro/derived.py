from algopy import arc4, log

from test_cases.diamond_mro.base1 import Base1
from test_cases.diamond_mro.base2 import Base2


class Derived(Base1, Base2):
    def __init__(self) -> None:
        log("derived.__init__")
        super().__init__()

    @arc4.abimethod
    def method(self) -> None:
        log("derived.method")
        super().method()
