from algopy import (
    Account,
    ARC4Contract,
    BigUInt,
    Bytes,
    String,
    TemplateVar,
    UInt64,
    arc4,
    logicsig,
    subroutine,
)


@logicsig
def always_approve_sig() -> bool:
    return True


class HelloBase(ARC4Contract):

    def __init__(self) -> None:
        self.greeting = String()

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        pass

    @arc4.baremethod(allow_actions=["UpdateApplication"])
    def update(self) -> None:
        pass

    @arc4.abimethod()
    def greet(self, name: String) -> String:
        return self.greeting + " " + name


class LargeProgram(ARC4Contract):

    @arc4.abimethod()
    def get_big_bytes_length(self) -> UInt64:
        return get_big_bytes().length

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        pass


@subroutine
def get_big_bytes() -> Bytes:
    return Bytes.from_hex("00" * 4096)


class Hello(HelloBase):

    @arc4.abimethod(create="require")
    def create(self, greeting: String) -> None:
        self.greeting = greeting


class HelloTmpl(HelloBase):

    def __init__(self) -> None:
        self.greeting = TemplateVar[String]("GREETING")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        pass


class HelloPrfx(HelloBase):

    def __init__(self) -> None:
        self.greeting = TemplateVar[String]("GREETING", prefix="PRFX_")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        pass


class HelloOtherConstants(ARC4Contract):

    def __init__(self) -> None:
        self.greeting = TemplateVar[String]("GREETING")
        self.num = TemplateVar[BigUInt]("NUM")
        self.address = TemplateVar[Account]("ACCOUNT")
        self.method = TemplateVar[Bytes]("METHOD")

    @arc4.abimethod(create="require")
    def create(self) -> UInt64:
        return UInt64(1)

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        pass

    @arc4.abimethod()
    def greet(self, name: String) -> Bytes:
        num_alpha = (self.num + 48).bytes[-1]
        return (
            self.greeting.bytes + b" " + name.bytes + num_alpha + self.address.bytes + self.method
        )
