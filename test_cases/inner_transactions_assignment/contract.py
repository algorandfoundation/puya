from algopy import (
    ARC4Contract,
    Bytes,
    Txn,
    arc4,
    itxn,
    subroutine,
)


class Contract(ARC4Contract):

    @arc4.abimethod
    def test_itxn_slice(self) -> None:
        acfg = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            note="acfg",
            total=1,
        )
        pay1 = itxn.Payment(receiver=Txn.sender, amount=0, note="pay1")
        pay2 = pay1.copy()
        pay2.set(note="pay2")
        pay3 = pay2.copy()
        pay3.set(note="pay3")
        sliced_txns = itxn.submit_txns(pay1, acfg, pay2, pay3)[1:-1]
        assert sliced_txns[0].note == b"acfg"
        assert sliced_txns[1].note == b"pay2"

    @arc4.abimethod
    def test_itxn_nested(self) -> None:
        acfg = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            note="acfg",
            total=1,
        )
        pay1 = itxn.Payment(receiver=Txn.sender, amount=0, note="pay1")
        pay2 = pay1.copy()
        pay2.set(note="pay2")
        pay3 = pay2.copy()
        pay3.set(note="pay3")
        nested_tuple = (
            echo(Bytes(b"hi")),
            itxn.submit_txns(pay1, acfg, pay2, pay3)[1:-1],
            echo(Bytes(b"there")),
        )
        assert nested_tuple[0] == b"hi"
        assert nested_tuple[1][0].note == b"acfg"
        assert nested_tuple[1][1].note == b"pay2"
        assert nested_tuple[2] == b"there"
        nested_tuple_copy = nested_tuple

        acfg.set(note="acfg2")
        pay2.set(note="pay4")
        pay3.set(note="pay5")

        if echo(Bytes(b"maybe")) == b"maybe":
            nested_tuple = (
                echo(Bytes(b"hi2")),
                itxn.submit_txns(pay1, acfg, pay3)[1:],
                echo(Bytes(b"there2")),
            )
        assert nested_tuple[0] == b"hi2"
        assert nested_tuple[1][0].note == b"acfg2"
        assert nested_tuple[1][1].note == b"pay5"
        assert nested_tuple[2] == b"there2"

        mish_mash = nested_tuple_copy[1][0], nested_tuple_copy[1][1], nested_tuple[1]

        assert mish_mash[0].note == b"acfg"
        assert mish_mash[1].note == b"pay2"
        assert mish_mash[2][0].note == b"acfg2"
        assert mish_mash[2][1].note == b"pay5"


@subroutine
def echo(value: Bytes) -> Bytes:
    return value
