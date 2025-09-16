from algopy import ARC4Contract, String, arc4

from pkg.constants import GREETING


class HelloWorldPkgContract(ARC4Contract):
    @arc4.abimethod
    def hello(self, name: String) -> String:
        return GREETING + ", " + name
