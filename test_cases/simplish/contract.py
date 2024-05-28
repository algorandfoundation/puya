from algopy import (
    Bytes,
    OnCompleteAction,
    UInt64,
    log,
    subroutine,
)
from algopy.op import (
    AppGlobal,
    AssetHoldingGet,
    Base64,
    Global,
    Txn,
    base64_decode,
    btoi,
    divmodw,
    gload_bytes,
    setbit_bytes,
    setbit_uint64,
)

from test_cases.simplish.base_class import CallCounter

SCALE = 100000
# SCALED_PI = int(3.14159 * SCALE)  # hmmmm
SCALED_PI = 314159


class Simplish(CallCounter):
    def approval_program(self) -> bool:
        if Txn.application_id == 0:
            return True
        oca = Txn.on_completion
        sender = Txn.sender
        if oca in (
            OnCompleteAction.UpdateApplication,
            OnCompleteAction.DeleteApplication,
        ):
            if oca == OnCompleteAction.DeleteApplication:
                log(Bytes(b"I was used ") + itoa(self.counter) + b" time(s) before I died")
            return Global.creator_address == sender

        if oca == OnCompleteAction.OptIn:
            if Txn.num_app_args > 0:
                self.set_sender_nickname(Txn.application_args(0))
            return True
        if oca != OnCompleteAction.NoOp:
            return False

        if (num_app_args := Txn.num_app_args) > 0:
            method_name = Txn.application_args(0)
            msg, result = self.call(method_name, num_app_args)
        elif Txn.num_assets == 1:
            asset_balance, asset_exists = AssetHoldingGet.asset_balance(sender, 0)
            if not asset_exists:
                msg = Bytes(b"You do not have any of the asset")
            else:
                msg = Bytes(b"You have asset balance: ") + itoa(asset_balance)
            result = True
        else:
            msg = Bytes(b"not enough app args or foreign assets")
            result = False
        log(msg)
        self.increment_counter()
        return result

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def call(self, method_name: Bytes, num_app_args: UInt64) -> tuple[Bytes, bool]:
        assert num_app_args == 2, "insufficient arguments"
        radius = btoi(Txn.application_args(1))

        status = True
        if method_name == b"circle_area":
            area = circle_area(radius)
            result = itoa(area)
        elif method_name == b"circle_circumference":
            circumference = circle_circumference(radius)
            result = itoa(circumference)
        elif method_name == b"circle_report":
            area, circumference = circle_area(radius), circle_circumference(radius)
            result = (
                Bytes(b"Approximate area and circumference of circle with radius ")
                + itoa(radius)
                + b" = "
                + itoa(area)
                + b", "
                + itoa(circumference)
            )
        else:
            status = False
            result = Bytes(b"unknown method name")
        return result, status

    @subroutine
    def increment_counter(self) -> None:
        log("Incrementing counter!")
        super().increment_counter()


@subroutine
def circle_circumference(radius: UInt64) -> UInt64:
    # PI * 2r
    two_pi = UInt64(2) * SCALED_PI
    return radius * two_pi // SCALE


@subroutine
def circle_area(radius: UInt64) -> UInt64:
    # PI * r ^ 2
    result = radius**2 * SCALED_PI // SCALE
    return result


@subroutine
def itoa(i: UInt64) -> Bytes:
    """Itoa converts an integer to the ascii byte string it represents"""
    digits = Bytes(b"0123456789")
    radix = digits.length
    if i < radix:
        return digits[i]
    return itoa(i // radix) + digits[i % radix]


@subroutine
def test_intrinsics() -> UInt64:
    _ii = gload_bytes(1, 1)
    _si = gload_bytes(UInt64(2), 2)
    _ss = gload_bytes(UInt64(3), UInt64(3))
    _is = gload_bytes(4, UInt64(4))
    _foo_uint: UInt64 = setbit_uint64(UInt64(32), 0, 3)
    _foo_int = setbit_uint64(32, 0, 3)
    _foo_bytes: Bytes = setbit_bytes(Bytes(b"32"), 0, 3)
    test = AppGlobal.get_bytes(b"foo")
    AppGlobal.put(b"b", b"yeah")
    AppGlobal.delete(b"foo")
    _expect_bytes: Bytes = test
    _abcd = divmodw(1, 2, 3, 4)
    _hello_str = base64_decode(Base64.StdEncoding, Bytes(b"SGVsbG8="))
    return UInt64(0)
