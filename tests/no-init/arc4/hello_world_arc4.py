from algopy import ARC4Contract, String, arc4  # noqa: INP001


class HelloWorldARC4Contract(ARC4Contract):
    @arc4.abimethod
    def hello(self, name: String) -> String:
        return "Hello, " + name
