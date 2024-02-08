import enum

from puyapy import UInt64

@enum.unique
class OnCompleteAction(UInt64, enum.ReprEnum):
    """On Completion actions available in an application call transaction"""

    NoOp = ...
    """NoOP indicates that no additional action is performed when the transaction completes"""

    OptIn = ...
    """OptIn indicates that an application transaction will allocate some
    LocalState for the application in the sender's account"""

    CloseOut = ...
    """CloseOut indicates that an application transaction will deallocate
    some LocalState for the application from the user's account"""

    ClearState = ...
    """ClearState is similar to CloseOut, but may never fail. This
    allows users to reclaim their minimum balance from an application
    they no longer wish to opt in to."""

    UpdateApplication = ...
    """UpdateApplication indicates that an application transaction will
    update the ApprovalProgram and ClearStateProgram for the application"""

    DeleteApplication = ...
    """DeleteApplication indicates that an application transaction will
    delete the AppParams for the application from the creator's balance
    record"""

@enum.unique
class TransactionType(UInt64, enum.ReprEnum):
    """The different transaction types available in a transaction"""

    Payment = ...
    """A Payment transaction"""
    KeyRegistration = ...
    """A Key Registration transaction"""
    AssetConfig = ...
    """An Asset Config transaction"""
    AssetTransfer = ...
    """An Asset Transfer transaction"""
    AssetFreeze = ...
    """An Asset Freeze transaction"""
    ApplicationCall = ...
    """An Application Call transaction"""
