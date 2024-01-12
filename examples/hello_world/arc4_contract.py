from puyapy import ARC4Contract, Bytes
from puyapy.arc4 import String, abimethod


class HelloWorldContract(ARC4Contract):
    @abimethod
    def say_hello(self, name: String) -> String:
        return String.encode(Bytes(b"Hello ") + name.decode())
