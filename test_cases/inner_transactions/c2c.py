from puyapy import Application, ARC4Contract, Bytes, UInt64, arc4, itxn, log

from test_cases.inner_transactions.programs import HELLO_WORLD_APPROVAL_HEX, HELLO_WORLD_CLEAR


class Greeter(ARC4Contract):
    def __init__(self) -> None:
        self.hello_app = Application(0)

    @arc4.abimethod()
    def bootstrap(self) -> UInt64:
        assert not self.hello_app, "already bootstrapped"
        self.hello_app = (
            itxn.ApplicationCall(
                approval_program=Bytes.from_hex(HELLO_WORLD_APPROVAL_HEX),
                clear_state_program=HELLO_WORLD_CLEAR,
                fee=0,
            )
            .submit()
            .created_app
        )
        return self.hello_app.id

    @arc4.abimethod()
    def log_greetings(self, name: arc4.String) -> None:
        hello_call = itxn.ApplicationCall(
            app_id=self.hello_app,
            app_args=(arc4.arc4_signature("hello(string)string"), name),
        ).submit()
        greeting = arc4.String.from_log(hello_call.last_log)
        log(b"HelloWorld returned: ", greeting.decode())
