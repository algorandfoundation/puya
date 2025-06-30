from algopy import ARC4Contract


class Parent(ARC4Contract):
    def __init__(self) -> None:
        super().__init__()
        self.is_initialised = False


class Orphan(ARC4Contract):
    def __init__(self) -> None:
        super().__init__()


class Child(Orphan, Parent):
    def __init__(self) -> None:
        super().__init__()
