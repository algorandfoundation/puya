from algopy import arc4, log

from test_cases.diamond_mro.gp import GP


class Base1(GP):
    def __init__(self) -> None:
        log("base1.__init__")
        super().__init__()

    @arc4.abimethod
    def method(self) -> None:
        log("base1.method")
        super().method()
