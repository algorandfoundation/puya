from algopy import (
    Bytes,
    Contract,
    OnCompleteAction,
    itxn,
    op,
    subroutine,
)

LOG_1ST_ARG_AND_APPROVE = (
    b"\x09"  # pragma version 9
    b"\x36\x1A\x00"  # txna ApplicationArgs 0
    b"\xB0"  # log
    b"\x81\x01"  # pushint 1
)
ALWAYS_APPROVE = (
    b"\x09"  # pragma version 9
    b"\x81\x01"  # pushint 1
)


class MyContract(Contract):
    def __init__(self) -> None:
        self.name = Bytes(b"")

    def approval_program(self) -> bool:
        if op.Txn.num_app_args:
            match op.Txn.application_args(0):
                case Bytes(b"test1"):
                    self.test1()
                case Bytes(b"test2"):
                    self.test2()
                case Bytes(b"test3"):
                    self.test3()
                case Bytes(b"test4"):
                    self.test4()
        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def test1(self) -> None:
        self.name = Bytes(b"AST1")
        asset_params = itxn.AssetConfig(
            total=1000,
            asset_name=self.name,
            unit_name=b"unit",
            decimals=3,
            manager=op.Global.current_application_address,
            reserve=op.Global.current_application_address,
            fee=0,
        )
        self.name = Bytes(b"AST2")
        asset1_txn = asset_params.submit()

        asset_params.set(
            asset_name=self.name,
        )

        asset2_txn = asset_params.submit()

        assert asset1_txn.asset_name == b"AST1", "asset1_txn is correct"
        assert asset2_txn.asset_name == b"AST2", "asset2_txn is correct"

        assert asset1_txn.created_asset.name == b"AST1", "created asset 1 is correct"
        assert asset2_txn.created_asset.name == b"AST2", "created asset 2 is correct"

        app_create_params = itxn.ApplicationCall(
            approval_program=b"\x09\x81\x01",
            clear_state_program=Bytes.from_hex("098101"),
            fee=0,
        )

        asset_params.set(
            asset_name=Bytes(b"AST3"),
        )

        app_create_txn, asset3_txn = itxn.submit_txns(app_create_params, asset_params)

        assert app_create_txn.created_app, "created app"
        assert asset3_txn.asset_name == b"AST3", "asset3_txn is correct"

        app_create_params.set(note=b"3rd")
        asset_params.set(note=b"3rd")
        # unassigned result
        itxn.submit_txns(app_create_params, asset_params)

    @subroutine
    def test2(self) -> None:
        if op.Txn.num_app_args:
            args = Bytes(b"1"), Bytes(b"2")
            create_app_params = itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                app_args=args,
                fee=0,
            )
        else:
            create_app_params = itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                app_args=(Bytes(b"3"), Bytes(b"4"), Bytes(b"5")),
                note=b"different param set",
                fee=0,
            )
        create_app_txn = create_app_params.submit()
        assert create_app_txn.app_args(0) == b"1", "correct args used 1"
        assert create_app_txn.app_args(1) == b"2", "correct args used 2"

        if op.Txn.num_app_args > 1:
            create_app_txn2 = itxn.ApplicationCall(
                approval_program=ALWAYS_APPROVE,
                clear_state_program=ALWAYS_APPROVE,
                on_completion=OnCompleteAction.DeleteApplication,
                app_args=(Bytes(b"42"),),
                fee=0,
            ).submit()
            assert create_app_txn2.app_args(0) == b"42", "correct args used 2"
        assert (
            create_app_txn.app_args(0) == b"1"
        ), "this will error on access if create_app_txn2 was submitted"

    @subroutine
    def test3(self) -> None:
        app_p_1 = itxn.ApplicationCall(
            approval_program=LOG_1ST_ARG_AND_APPROVE,
            clear_state_program=ALWAYS_APPROVE,
            on_completion=OnCompleteAction.DeleteApplication,
            app_args=(Bytes(b"1"),),
            fee=0,
        )

        app_p_2 = app_p_1.copy().copy()
        app_p_2.set(app_args=(Bytes(b"2"),))

        app_p_3 = app_p_1.copy()
        app_p_3.set(app_args=(Bytes(b"3"),))

        app_p_4 = app_p_1.copy()
        app_p_4.set(app_args=(Bytes(b"4"),))

        app_p_5 = app_p_1.copy()
        app_p_5.set(app_args=(Bytes(b"5"),))

        app_p_6 = app_p_1.copy()
        app_p_6.set(app_args=(Bytes(b"6"),))

        app_p_7 = app_p_1.copy()
        app_p_7.set(app_args=(Bytes(b"7"),))

        app_p_8 = app_p_1.copy()
        app_p_8.set(app_args=(Bytes(b"8"),))

        app_p_9 = app_p_1.copy()
        app_p_9.set(app_args=(Bytes(b"9"),))

        app_p_10 = app_p_1.copy()
        app_p_10.set(app_args=(Bytes(b"10"),))

        app_p_11 = app_p_1.copy()
        app_p_11.set(app_args=(Bytes(b"11"),))

        app_p_12 = app_p_1.copy()
        app_p_12.set(app_args=(Bytes(b"12"),))

        app_p_13 = app_p_1.copy()
        app_p_13.set(app_args=(Bytes(b"13"),))

        app_p_14 = app_p_1.copy()
        app_p_14.set(app_args=(Bytes(b"14"),))

        app_p_15 = app_p_1.copy()
        app_p_15.set(app_args=(Bytes(b"15"),))

        app_p_16 = app_p_1.copy()
        app_p_16.set(app_args=(Bytes(b"16"),))
        (
            app1,
            app2,
            app3,
            app4,
            app5,
            app6,
            app7,
            app8,
            app9,
            app10,
            app11,
            app12,
            app13,
            app14,
            app15,
            app16,
        ) = itxn.submit_txns(
            app_p_1,
            app_p_2,
            app_p_3,
            app_p_4,
            app_p_5,
            app_p_6,
            app_p_7,
            app_p_8,
            app_p_9,
            app_p_10,
            app_p_11,
            app_p_12,
            app_p_13,
            app_p_14,
            app_p_15,
            app_p_16,
        )

        assert app1.logs(0) == b"1"
        assert app2.logs(0) == b"2"
        assert app3.logs(0) == b"3"
        assert app4.logs(0) == b"4"
        assert app5.logs(0) == b"5"
        assert app6.logs(0) == b"6"
        assert app7.logs(0) == b"7"
        assert app8.logs(0) == b"8"
        assert app9.logs(0) == b"9"
        assert app10.logs(0) == b"10"
        assert app11.logs(0) == b"11"
        assert app12.logs(0) == b"12"
        assert app13.logs(0) == b"13"
        assert app14.logs(0) == b"14"
        assert app15.logs(0) == b"15"
        assert app16.logs(0) == b"16"

    @subroutine
    def test4(self) -> None:
        lots_of_bytes = op.bzero(2044)
        approval_1 = Bytes(ALWAYS_APPROVE)
        approval_2 = (
            Bytes(
                b"\x80"  # pushbytes
                b"\xFC\x0F"  # varuint 2044
            )
            + lots_of_bytes
            + Bytes(b"\x48")  # pop
        )
        app_p_1 = itxn.ApplicationCall(
            approval_program=(approval_1, approval_2, approval_2, approval_2),
            clear_state_program=ALWAYS_APPROVE,
            on_completion=OnCompleteAction.DeleteApplication,
            app_args=(Bytes(b"1"),),
            extra_program_pages=3,
            fee=0,
        )
        app_1 = app_p_1.submit()
        assert app_1.extra_program_pages == 3, "extra_pages == 3"
        assert app_1.num_approval_program_pages == 2, "approval_pages == 2"
        assert (
            app_1.approval_program_pages(0) == approval_1 + approval_2 + approval_2[:-3]
        ), "expected approval page 0"
        assert (
            app_1.approval_program_pages(1) == approval_2[-3:] + approval_2
        ), "expected approval page 1"
        assert app_1.num_clear_state_program_pages == 1, "clear_state_pages == 1"
        assert app_1.clear_state_program_pages(0) == ALWAYS_APPROVE, "expected clear_state_pages"


@subroutine
def echo(v: Bytes) -> Bytes:
    return v
