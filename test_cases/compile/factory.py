from algopy import (
    ARC4Contract,
    Bytes,
    OnCompleteAction,
    String,
    TemplateVar,
    UInt64,
    arc4,
    get_approval_program,
    get_clear_state_program,
    get_logicsig_account,
    itxn,
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

    @arc4.abimethod()
    def greet(self, name: String) -> String:
        return self.greeting + " " + name


class LargeProgram(ARC4Contract):

    @arc4.abimethod()
    def get_big_bytes_length(self) -> UInt64:
        return get_big_bytes().length

    @arc4.abimethod(create="require")
    def create(self) -> None:
        pass

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


class HelloFactory(ARC4Contract):

    @arc4.abimethod()
    def test_logicsig(self) -> arc4.Address:
        return arc4.Address(get_logicsig_account(always_approve_sig))

    @arc4.abimethod()
    def test_get_program(self) -> None:
        # create app
        hello_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create(string)void"), arc4.String("hello")),
                approval_program=get_approval_program(Hello),
                clear_state_program=get_clear_state_program(Hello),
                global_num_bytes=1,
            )
            .submit()
            .created_app
        )

        # call the new app
        txn = itxn.ApplicationCall(
            app_args=(arc4.arc4_signature("greet(string)string"), arc4.String("world")),
            app_id=hello_app,
        ).submit()
        result = arc4.String.from_log(txn.last_log)

        # delete the app
        itxn.ApplicationCall(
            app_id=hello_app,
            app_args=(arc4.arc4_signature("delete()void"),),
            on_completion=OnCompleteAction.DeleteApplication,
        ).submit()

        assert result == "hello world"

    @arc4.abimethod()
    def test_get_program_tmpl(self) -> None:
        # create app
        hello_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create()void"),),
                approval_program=get_approval_program(HelloTmpl, GREETING=b"hey"),
                clear_state_program=get_clear_state_program(HelloTmpl),
                global_num_bytes=1,
            )
            .submit()
            .created_app
        )

        # call the new app
        txn = itxn.ApplicationCall(
            app_args=(arc4.arc4_signature("greet(string)string"), arc4.String("world")),
            app_id=hello_app,
        ).submit()
        result = arc4.String.from_log(txn.last_log)

        # delete the app
        itxn.ApplicationCall(
            app_id=hello_app,
            app_args=(arc4.arc4_signature("delete()void"),),
            on_completion=OnCompleteAction.DeleteApplication,
        ).submit()

        assert result == "hey world"

    @arc4.abimethod()
    def test_get_program_prfx(self) -> None:
        # create app
        hello_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create()void"),),
                approval_program=get_approval_program(HelloPrfx, prefix="PRFX_", GREETING=b"hi"),
                clear_state_program=get_clear_state_program(HelloPrfx),
                global_num_bytes=1,
            )
            .submit()
            .created_app
        )

        # call the new app
        txn = itxn.ApplicationCall(
            app_args=(arc4.arc4_signature("greet(string)string"), arc4.String("world")),
            app_id=hello_app,
        ).submit()
        result = arc4.String.from_log(txn.last_log)

        # delete the app
        itxn.ApplicationCall(
            app_id=hello_app,
            app_args=(arc4.arc4_signature("delete()void"),),
            on_completion=OnCompleteAction.DeleteApplication,
        ).submit()

        assert result == "hi world"

    @arc4.abimethod()
    def test_get_program_large(self) -> None:
        # create app
        hello_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create()void"),),
                approval_program=get_approval_program(LargeProgram),
                clear_state_program=get_clear_state_program(LargeProgram),
                extra_program_pages=3,
                global_num_bytes=1,
            )
            .submit()
            .created_app
        )

        # call the new app
        txn = itxn.ApplicationCall(
            app_args=(arc4.arc4_signature("get_big_bytes_length()uint64"),),
            app_id=hello_app,
        ).submit()
        result = arc4.UInt64.from_log(txn.last_log)

        # delete the app
        itxn.ApplicationCall(
            app_id=hello_app,
            app_args=(arc4.arc4_signature("delete()void"),),
            on_completion=OnCompleteAction.DeleteApplication,
        ).submit()

        assert result == 4096

    @arc4.abimethod()
    def test_abi_call(self) -> None:
        # create app
        hello_app = arc4.abi_call(
            Hello.create,
            "hello",
            # approval_program, clear_state_program, global_num_*, local_num_*, and
            # extra_program_pages are automatically set based on Hello contract
        ).created_app

        # call the new app
        result, _txn = arc4.abi_call(Hello.greet, "world", app_id=hello_app)

        # delete the app
        arc4.abi_call(
            Hello.delete,
            app_id=hello_app,
            # on_complete is inferred from Hello.delete ARC4 definition
        )

        assert result == "hello world"

    @arc4.abimethod()
    def test_abi_call_tmpl(self) -> None:
        # create app
        hello_app = arc4.abi_call(
            HelloTmpl.create,
            GREETING=b"tmpl2",
        ).created_app

        # call the new app
        result, _txn = arc4.abi_call(HelloTmpl.greet, "world", app_id=hello_app)

        # delete the app
        arc4.abi_call(
            HelloTmpl.delete,
            app_id=hello_app,
            # on_complete is inferred from Hello.delete ARC4 definition
        )

        assert result == "tmpl2 world"

    @arc4.abimethod()
    def test_abi_call_prfx(self) -> None:
        # create app
        hello_app = arc4.abi_call(
            HelloPrfx.create,
            prefix="PRFX_",
            GREETING=b"prfx2",
        ).created_app

        # call the new app
        result, _txn = arc4.abi_call(HelloPrfx.greet, "world", app_id=hello_app)

        # delete the app
        arc4.abi_call(
            HelloPrfx.delete,
            app_id=hello_app,
            # on_complete is inferred from Hello.delete ARC4 definition
        )

        assert result == "prfx2 world"

    @arc4.abimethod()
    def test_abi_call_large(self) -> None:
        # create app
        app = arc4.abi_call(
            LargeProgram.create,
        ).created_app

        # call the new app
        result, _txn = arc4.abi_call(LargeProgram.get_big_bytes_length, app_id=app)
        assert result == 4096

        # delete the app
        arc4.abi_call(
            LargeProgram.delete,
            app_id=app,
        )
