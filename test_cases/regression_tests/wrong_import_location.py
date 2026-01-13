# fmt: off
from algopy import ARC4Contract, UInt64, public

from test_cases.regression_tests.wrong_import_location__sub import get_return_value

# The lines below are intentionally blank!














class WrongImportLocation(ARC4Contract):
    @public
    def verify(self) -> UInt64:
        return get_return_value()
