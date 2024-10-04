from algopy import (
    Account,
    ARC4Contract,
    BigUInt,
    Global,
    OnCompleteAction,
    String,
    arc4,
    compile_contract,
    compile_logicsig,
    itxn,
)

from test_cases.compile.apps import (
    Hello,
    HelloOtherConstants,
    HelloPrfx,
    HelloTmpl,
    LargeProgram,
    always_approve_sig,
)


class HelloFactory(ARC4Contract):

    @arc4.abimethod()
    def test_logicsig(self) -> arc4.Address:
        return arc4.Address(compile_logicsig(always_approve_sig).account)

    @arc4.abimethod()
    def test_compile_contract(self) -> None:
        # create app
        compiled = compile_contract(Hello)
        hello_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create(string)void"), arc4.String("hello")),
                approval_program=compiled.approval_program,
                clear_state_program=compiled.clear_state_program,
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
    def test_compile_contract_tmpl(self) -> None:
        # create app
        greeting = String("hey")
        compiled = compile_contract(HelloTmpl, template_vars={"GREETING": greeting})
        hello_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create()void"),),
                approval_program=compiled.approval_program,
                clear_state_program=compiled.clear_state_program,
                global_num_uint=compiled.global_uints,
                global_num_bytes=compiled.global_bytes,
                local_num_uint=compiled.local_uints,
                local_num_bytes=compiled.local_bytes,
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
    def test_compile_contract_prfx(self) -> None:
        # create app
        compiled = compile_contract(
            HelloPrfx, template_vars={"GREETING": String("hi")}, template_vars_prefix="PRFX_"
        )
        hello_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create()void"),),
                approval_program=compiled.approval_program,
                clear_state_program=compiled.clear_state_program,
                global_num_bytes=compiled.global_bytes,
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
    def test_compile_contract_large(self) -> None:
        # create app
        compiled = compile_contract(LargeProgram)
        hello_app = (
            itxn.ApplicationCall(
                approval_program=compiled.approval_program,
                clear_state_program=compiled.clear_state_program,
                extra_program_pages=compiled.extra_program_pages,
                global_num_bytes=compiled.global_bytes,
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
    def test_arc4_create(self) -> None:
        # create app
        hello_app = arc4.arc4_create(Hello.create, "hello").created_app

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
    def test_arc4_create_tmpl(self) -> None:
        # create app
        compiled = compile_contract(HelloTmpl, template_vars={"GREETING": String("tmpl2")})
        hello_app = arc4.arc4_create(
            HelloTmpl.create,
            compiled=compiled,
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
    def test_arc4_create_prfx(self) -> None:
        # create app
        compiled = compile_contract(
            HelloPrfx, template_vars_prefix="PRFX_", template_vars={"GREETING": String("prfx2")}
        )
        hello_app = arc4.arc4_create(
            HelloPrfx.create,
            compiled=compiled,
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
    def test_arc4_create_large(self) -> None:
        # create app
        app = arc4.arc4_create(LargeProgram).created_app

        # call the new app
        result, _txn = arc4.abi_call(LargeProgram.get_big_bytes_length, app_id=app)
        assert result == 4096

        # delete the app
        arc4.abi_call(
            LargeProgram.delete,
            app_id=app,
        )

    @arc4.abimethod()
    def test_arc4_update(self) -> None:
        # create app
        app = arc4.arc4_create(
            HelloTmpl,
            compiled=compile_contract(
                HelloTmpl,
                template_vars={"GREETING": String("hi")},
                extra_program_pages=1,
                global_uints=2,
                global_bytes=2,
                local_bytes=2,
                local_uints=2,
            ),
        ).created_app

        # call the new app
        result, _txn = arc4.abi_call(HelloTmpl.greet, "there", app_id=app)
        assert result == "hi there"

        # update the app
        arc4.arc4_update(Hello, app_id=app)

        # call the updated app
        result, _txn = arc4.abi_call(Hello.greet, "there", app_id=app)
        assert result == "hi there"

        # delete the app
        arc4.abi_call(
            Hello.delete,
            app_id=app,
            # on_complete is inferred from Hello.delete ARC4 definition
        )

    @arc4.abimethod()
    def test_other_constants(self) -> None:
        app = arc4.arc4_create(
            HelloOtherConstants,
            compiled=compile_contract(
                HelloOtherConstants,
                template_vars={
                    "NUM": BigUInt(5),
                    "GREETING": String("hello"),
                    "ACCOUNT": Account(
                        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
                    ),
                    "METHOD": arc4.arc4_signature("something()void"),
                },
            ),
        ).created_app

        result, _txn = arc4.abi_call(HelloOtherConstants.greet, "Johnny", app_id=app)

        assert result == (
            b"hello Johnny5" + Global.zero_address.bytes + arc4.arc4_signature("something()void")
        )

        # delete the app
        arc4.abi_call(HelloOtherConstants.delete, app_id=app)

    @arc4.abimethod()
    def test_abi_call_create_params(self) -> None:
        compiled = compile_contract(Hello)
        app = arc4.abi_call(
            Hello.create,
            String("hey"),
            approval_program=compiled.approval_program,
            clear_state_program=compiled.clear_state_program,
            global_num_uint=compiled.global_uints,
            global_num_bytes=compiled.global_bytes,
            local_num_uint=compiled.local_uints,
            local_num_bytes=compiled.local_bytes,
            extra_program_pages=compiled.extra_program_pages,
        ).created_app

        result, _txn = arc4.abi_call(Hello.greet, "there", app_id=app)

        assert result == "hey there"

        # delete the app
        arc4.abi_call(Hello.delete, app_id=app)
