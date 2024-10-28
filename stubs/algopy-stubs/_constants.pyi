import typing
from algopy import UInt64

@typing.final
class OnCompleteAction(UInt64):
    """On Completion actions available in an application call transaction"""

    NoOp: OnCompleteAction = ...
    """NoOP indicates that no additional action is performed when the transaction completes"""

    OptIn: OnCompleteAction = ...
    """OptIn indicates that an application transaction will allocate some
    LocalState for the application in the sender's account"""

    CloseOut: OnCompleteAction = ...
    """CloseOut indicates that an application transaction will deallocate
    some LocalState for the application from the user's account"""

    ClearState: OnCompleteAction = ...
    """ClearState is similar to CloseOut, but may never fail. This
    allows users to reclaim their minimum balance from an application
    they no longer wish to opt in to."""

    UpdateApplication: OnCompleteAction = ...
    """UpdateApplication indicates that an application transaction will
    update the ApprovalProgram and ClearStateProgram for the application"""

    DeleteApplication: OnCompleteAction = ...
    """DeleteApplication indicates that an application transaction will
    delete the AppParams for the application from the creator's balance
    record"""

@typing.final
class TransactionType(UInt64):
    """The different transaction types available in a transaction"""

    Payment: TransactionType = ...
    """A Payment transaction"""
    KeyRegistration: TransactionType = ...
    """A Key Registration transaction"""
    AssetConfig: TransactionType = ...
    """An Asset Config transaction"""
    AssetTransfer: TransactionType = ...
    """An Asset Transfer transaction"""
    AssetFreeze: TransactionType = ...
    """An Asset Freeze transaction"""
    ApplicationCall: TransactionType = ...
    """An Application Call transaction"""
