import algopy


class Counter(algopy.Contract):
    def __init__(self) -> None:
        self.counter = algopy.UInt64(0)

    def approval_program(self) -> bool:
        match algopy.Txn.on_completion:
            case algopy.OnCompleteAction.NoOp:
                self.increment_counter()
                return True
            case _:
                # reject all OnCompletionAction's other than NoOp
                return False

    def clear_state_program(self) -> bool:
        return True

    @algopy.subroutine
    def increment_counter(self) -> None:
        self.counter += 1
