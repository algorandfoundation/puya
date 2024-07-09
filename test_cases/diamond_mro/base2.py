from algopy import arc4, log

from test_cases.diamond_mro.gp import GP


class Base2(GP):
    def __init__(self) -> None:
        log("base2.__init__")
        super().__init__()

    @arc4.abimethod
    def method(self) -> None:
        log("base2.method")
        super().method()
