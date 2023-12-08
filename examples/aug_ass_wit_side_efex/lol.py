from algopy import Contract, Struct, UInt64, itob, log, subroutine


class MyData(Struct):
    x: UInt64


class Lol(Contract):
    def approval_program(self) -> bool:
        data = MyData(x=UInt64(1))
        log_and_return(data).x += 2
        assert data.x == 3
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def log_and_return(data: MyData) -> MyData:
    log(itob(data.x))
    return data
