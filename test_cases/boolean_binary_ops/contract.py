from algopy import Bytes, Contract, log, subroutine


class BooleanBinaryOps(Contract):
    def approval_program(self) -> bool:
        test_boolean_binary_ops(true=True, false=False)
        test_boolean_shortcircuit_binary_ops()
        return True

    def clear_state_program(self) -> bool:
        assert bool() == False  # noqa: E712, UP018
        return True


@subroutine
def test_boolean_binary_ops(*, true: bool, false: bool) -> None:
    assert not (true and false)
    assert not (false and true)
    assert true and true
    assert not (false and false)

    assert true or false
    assert false or true
    assert true or true
    assert not (false or false)


@subroutine
def bool_to_bytes(x: bool) -> Bytes:
    return Bytes(b"true") if x else Bytes(b"false")  # TODO: allow Bytes() outside ternary instead


@subroutine
def test_boolean_shortcircuit_binary_ops() -> None:
    for lhs in (True, False):
        for rhs in (True, False):
            and_msg = b"_" + bool_to_bytes(lhs) + b"_and_" + bool_to_bytes(rhs)
            and_result = log_and_return(lhs, b"lhs" + and_msg) and log_and_return(
                rhs, b"rhs" + and_msg
            )
            assert and_result == (lhs and rhs)
            or_msg = b"_" + bool_to_bytes(lhs) + b"_or_" + bool_to_bytes(rhs)
            or_result = log_and_return(lhs, b"lhs" + or_msg) or log_and_return(
                rhs, b"rhs" + or_msg
            )
            assert or_result == (lhs or rhs)


@subroutine
def log_and_return(x: bool, msg: Bytes) -> bool:
    log(msg)
    return x
