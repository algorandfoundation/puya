from algopy import BaseContract, Bytes, Txn, log, op, subroutine, urange


class OpPrefixConcat(BaseContract):
    def approval_program(self) -> bool:
        a = Txn.num_app_args
        b = Txn.application_args(0)
        c = op.itob(a) + b
        log(c)
        return True

    def clear_state_program(self) -> bool:
        return True


class ConstPrefixConcat(BaseContract):
    def approval_program(self) -> bool:
        prefix = Bytes(b"log:")
        value = op.itob(Txn.num_app_args)
        log(prefix + value)
        return True

    def clear_state_program(self) -> bool:
        return True


class LocalVarConcat(BaseContract):
    def approval_program(self) -> bool:
        x = Txn.application_args(0)
        a = Txn.application_args(1)
        b = Txn.application_args(2)
        log(x + (a + b))
        return True

    def clear_state_program(self) -> bool:
        return True


class VarConcatRight(BaseContract):
    def approval_program(self) -> bool:
        x = Txn.application_args(0)
        a = Txn.application_args(1)
        b = Txn.application_args(2)
        log((a + b) + x)
        return True

    def clear_state_program(self) -> bool:
        return True


class FrameSlotMutationConcat(BaseContract):
    def approval_program(self) -> bool:
        log(_chain(Txn.application_args(0), Txn.application_args(1)))
        return True

    def clear_state_program(self) -> bool:
        return True


class FrameMutateInLoopConcat(BaseContract):
    def approval_program(self) -> bool:
        result = Bytes(b"")
        sep = Bytes(b",")
        for i in urange(Txn.num_app_args):
            result = result + sep + Txn.application_args(i)
        log(result)
        return True

    def clear_state_program(self) -> bool:
        return True


class DeepShuffleConcat(BaseContract):
    def approval_program(self) -> bool:
        a = Txn.application_args(0)
        b = Txn.application_args(1)
        c = Txn.application_args(2)
        d = Txn.application_args(3)
        prefix = Bytes(b"prefix:")
        log(prefix + (a + b) + (c + d))
        return True

    def clear_state_program(self) -> bool:
        return True


class DupedLocalConcat(BaseContract):
    def approval_program(self) -> bool:
        x = Txn.application_args(0)
        y = Txn.application_args(1)
        log(x + y + x + y)
        return True

    def clear_state_program(self) -> bool:
        return True


class IntLocalShuffleConcat(BaseContract):
    def approval_program(self) -> bool:
        n = Txn.num_app_args
        a = Txn.application_args(0)
        b = Txn.application_args(1)
        log(op.itob(n) + a + b)
        if n > 1:
            log(op.itob(n + 1) + b + a)
        return True

    def clear_state_program(self) -> bool:
        return True


class ScratchLoadShuffleConcat(BaseContract, scratch_slots=(0,)):
    def approval_program(self) -> bool:
        op.Scratch.store(0, Txn.application_args(0))
        b = op.itob(Txn.num_app_args)
        a = op.Scratch.load_bytes(0)
        log(a + b)
        return True

    def clear_state_program(self) -> bool:
        return True


class ScratchLoadBarrierConcat(BaseContract, scratch_slots=(0,)):
    def approval_program(self) -> bool:
        op.Scratch.store(0, Txn.application_args(0))
        b = op.itob(Txn.num_app_args)
        op.Scratch.store(0, Txn.application_args(1))
        a = op.Scratch.load_bytes(0)
        log(a + b)
        return True

    def clear_state_program(self) -> bool:
        return True


class SubroutineParamSwapConcat(BaseContract):
    def approval_program(self) -> bool:
        log(_swap_and_concat(Txn.application_args(0), Txn.application_args(1)))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def _chain(a: Bytes, b: Bytes) -> Bytes:
    a = a + b
    return b + a


@subroutine
def _swap_and_concat(a: Bytes, b: Bytes) -> Bytes:
    if Txn.num_app_args > 2:
        a = b
        b = Txn.application_args(2)
    return a + b + a
