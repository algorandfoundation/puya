from puyapy import (
    Account,
    ARC4Contract,
    LocalState,
    OnCompleteAction,
    UInt64,
    op,
    subroutine,
)
from puyapy.arc4 import (
    String,
    UInt64 as arc4_UInt64,
    abimethod,
)

from test_cases.everything.constants import BANNED, EXT_ONE
from test_cases.everything.my_base import MyMiddleBase, multiplicative_identity

ZERO = ZER0 = 0  # lol
ONE = ZERO + (ZER0 * 2) + (2 - 1) // EXT_ONE


@subroutine
def get_banned() -> Account:
    addr = Account(BANNED)
    return addr


@subroutine
def add_one(x: UInt64) -> UInt64:
    new_value = x
    one = UInt64(ONE)
    new_value += one
    return new_value


class Everything(ARC4Contract, MyMiddleBase, name="MyContract"):
    def __init__(self) -> None:
        self.name = LocalState(String)

    @abimethod(create=True)
    def create(self) -> None:
        self._check_ban_list()
        self.remember_creator()
        self.counter = UInt64(ZERO)

    @abimethod(allow_actions=["NoOp", "OptIn"])
    def register(self, name: String) -> None:
        self._check_ban_list()
        if op.Txn.on_completion == OnCompleteAction.OptIn:
            sender_name, sender_name_existed = self.name.maybe(account=0)
            if not sender_name_existed:
                self.counter += multiplicative_identity()  # has full FuncDef
        self.name[0] = name

    @abimethod
    def say_hello(self) -> String:
        self._check_ban_list()
        name, exists = self.name.maybe(account=0)
        if not exists:
            return String("Howdy stranger!")
        return "Hello, " + name + "!"

    @abimethod
    def calculate(self, a: arc4_UInt64, b: arc4_UInt64) -> arc4_UInt64:
        c = super().calculate(a, b)
        return arc4_UInt64(c.decode() * b.decode())

    @abimethod(allow_actions=["CloseOut"])
    def close_out(self) -> None:
        self._remove_sender()

    def clear_state_program(self) -> bool:
        self._remove_sender()
        return True

    @subroutine
    def _check_ban_list(self) -> None:
        assert op.Txn.sender != get_banned(), "You are banned, goodbye"

    @subroutine
    def _remove_sender(self) -> None:
        self.counter -= positive_one()


@subroutine
def positive_one() -> UInt64:
    return UInt64(1)
