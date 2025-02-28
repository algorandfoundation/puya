from algopy import ARC4Contract, arc4, log, subroutine


class MyStruct(arc4.Struct):
    foo: arc4.UInt64


class Jira142(ARC4Contract):
    @subroutine
    def some_subroutine(self, char: MyStruct) -> None:
        pass

    @arc4.abimethod
    def battle(self) -> None:
        my_struct = MyStruct(foo=arc4.UInt64(200))

        if my_struct.foo > arc4.UInt64(100):
            self.some_subroutine(my_struct)

        log(my_struct.copy())
