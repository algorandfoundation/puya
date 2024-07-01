import enum

from puya.models import OnCompletionAction

ARC4_CONTRACT_BASE = "algopy.arc4.ARC4Contract"
CONTRACT_BASE = "algopy._contract.Contract"
STRUCT_META = "algopy._struct._StructMeta"
SUBROUTINE_HINT = "algopy._hints.subroutine"
LOGICSIG_DECORATOR = "algopy._logic_sig.logicsig"
LOGICSIG_DECORATOR_ALIAS = "algopy.logicsig"
SUBROUTINE_HINT_ALIAS = "algopy.subroutine"
ABIMETHOD_DECORATOR = "algopy.arc4.abimethod"
ABIMETHOD_DECORATOR_ALIAS = ABIMETHOD_DECORATOR
BAREMETHOD_DECORATOR = "algopy.arc4.baremethod"
BAREMETHOD_DECORATOR_ALIAS = BAREMETHOD_DECORATOR
APPROVAL_METHOD = "approval_program"
CLEAR_STATE_METHOD = "clear_state_program"
ALGOPY_OP_PREFIX = "algopy.op."
URANGE = "algopy._unsigned_builtins.urange"
CLS_ARC4_STRUCT_META = "algopy.arc4._StructMeta"
CLS_ARC4_ABI_CALL = "algopy.arc4.abi_call"

CONTRACT_STUB_TYPES = [
    CONTRACT_BASE,
    ARC4_CONTRACT_BASE,
]


KNOWN_METHOD_DECORATORS = [
    SUBROUTINE_HINT,
    ABIMETHOD_DECORATOR,
    BAREMETHOD_DECORATOR,
]


# values and names are matched to AVM definitions
class TransactionType(enum.IntEnum):
    pay = 1
    keyreg = 2
    acfg = 3
    axfer = 4
    afrz = 5
    appl = 6


ENUM_CLS_ON_COMPLETE_ACTION = "algopy._constants.OnCompleteAction"
ENUM_CLS_TRANSACTION_TYPE = "algopy._constants.TransactionType"
NAMED_INT_CONST_ENUM_DATA: dict[str, dict[str, enum.IntEnum]] = {
    ENUM_CLS_ON_COMPLETE_ACTION: {
        "NoOp": OnCompletionAction.NoOp,
        "OptIn": OnCompletionAction.OptIn,
        "CloseOut": OnCompletionAction.CloseOut,
        "ClearState": OnCompletionAction.ClearState,
        "UpdateApplication": OnCompletionAction.UpdateApplication,
        "DeleteApplication": OnCompletionAction.DeleteApplication,
    },
    ENUM_CLS_TRANSACTION_TYPE: {
        "Payment": TransactionType.pay,
        "KeyRegistration": TransactionType.keyreg,
        "AssetConfig": TransactionType.acfg,
        "AssetTransfer": TransactionType.axfer,
        "AssetFreeze": TransactionType.afrz,
        "ApplicationCall": TransactionType.appl,
    },
}
