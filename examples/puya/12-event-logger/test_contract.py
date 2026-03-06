import pytest
from algopy import UInt64, arc4
from algopy_testing import algopy_testing_context
from contract import EventLogger


class TestEventLogger:
    def test_emit_arc4_struct(self) -> None:
        with algopy_testing_context():
            contract = EventLogger()
            contract.emit_arc4_struct(arc4.UInt64(10), arc4.UInt64(20))

    @pytest.mark.xfail(reason="algorand-python-testing arc4.emit rejects native algopy.Struct")
    def test_emit_native_struct(self) -> None:
        with algopy_testing_context():
            contract = EventLogger()
            contract.emit_native_struct(UInt64(10), UInt64(20))

    def test_emit_by_name(self) -> None:
        with algopy_testing_context():
            contract = EventLogger()
            contract.emit_by_name(UInt64(10), UInt64(20))

    def test_emit_by_signature(self) -> None:
        with algopy_testing_context():
            contract = EventLogger()
            contract.emit_by_signature(UInt64(10), UInt64(20))

    @pytest.mark.xfail(reason="arc4.emit with string signature crashes on Tuple")
    def test_emit_multiple(self) -> None:
        with algopy_testing_context():
            contract = EventLogger()
            contract.emit_multiple(UInt64(42))
