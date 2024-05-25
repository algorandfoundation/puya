from enum import Enum


class OnCompleteAction(Enum):
    """On Completion actions available in an application call transaction"""

    NoOp = 0
    """NoOp indicates that no additional action is performed when the transaction completes"""

    OptIn = 1
    """OptIn indicates that an application transaction will allocate some
    LocalState for the application in the sender's account"""

    CloseOut = 2
    """CloseOut indicates that an application transaction will deallocate
    some LocalState for the application from the user's account"""

    ClearState = 3
    """ClearState is similar to CloseOut, but may never fail. This
    allows users to reclaim their minimum balance from an application
    they no longer wish to opt in to."""

    UpdateApplication = 4
    """UpdateApplication indicates that an application transaction will
    update the ApprovalProgram and ClearStateProgram for the application"""

    DeleteApplication = 5
    """DeleteApplication indicates that an application transaction will
    delete the AppParams for the application from the creator's balance
    record"""


class TransactionType(Enum):
    """The different transaction types available in a transaction"""

    Payment = 0
    """A Payment transaction"""

    KeyRegistration = 1
    """A Key Registration transaction"""

    AssetConfig = 2
    """An Asset Config transaction"""

    AssetTransfer = 3
    """An Asset Transfer transaction"""

    AssetFreeze = 4
    """An Asset Freeze transaction"""

    ApplicationCall = 5
    """An Application Call transaction"""
