import enum

from puya.models import OnCompletionAction

PUYAPY_PREFIX = "puyapy."
ARC4_PREFIX = f"{PUYAPY_PREFIX}arc4."
ARC4_CONTRACT_BASE = f"{ARC4_PREFIX}ARC4Contract"
# special case for arc4 where puyapy alias is present in puyapy namespace
ARC4_CONTRACT_BASE_ALIAS = f"{PUYAPY_PREFIX}ARC4Contract"
ARC4_SIGNATURE = f"{ARC4_PREFIX}arc4_signature"
ARC4_SIGNATURE_ALIAS = ARC4_SIGNATURE
CONTRACT_BASE = f"{PUYAPY_PREFIX}_contract.Contract"
CONTRACT_BASE_ALIAS = f"{PUYAPY_PREFIX}Contract"
STRUCT_BASE = f"{PUYAPY_PREFIX}_struct.Struct"
STRUCT_BASE_ALIAS = f"{PUYAPY_PREFIX}Struct"
CLS_ACCOUNT = f"{PUYAPY_PREFIX}_reference.Account"
CLS_ACCOUNT_ALIAS = f"{PUYAPY_PREFIX}Account"
CLS_ASSET = f"{PUYAPY_PREFIX}_reference.Asset"
CLS_ASSET_ALIAS = f"{PUYAPY_PREFIX}Asset"
CLS_APPLICATION = f"{PUYAPY_PREFIX}_reference.Application"
CLS_APPLICATION_ALIAS = f"{PUYAPY_PREFIX}Application"
CLS_UINT64 = f"{PUYAPY_PREFIX}_primitives.UInt64"
CLS_UINT64_ALIAS = f"{PUYAPY_PREFIX}UInt64"
CLS_BYTES = f"{PUYAPY_PREFIX}_primitives.Bytes"
CLS_BYTES_ALIAS = f"{PUYAPY_PREFIX}Bytes"
CLS_BIGUINT = f"{PUYAPY_PREFIX}_primitives.BigUInt"
CLS_BIGUINT_ALIAS = f"{PUYAPY_PREFIX}BigUInt"
CLS_TRANSACTION_BASE = f"{PUYAPY_PREFIX}gtxn.TransactionBase"
CLS_LOCAL_STATE = f"{PUYAPY_PREFIX}_state.LocalState"
CLS_LOCAL_STATE_ALIAS = f"{PUYAPY_PREFIX}.LocalState"
CLS_GLOBAL_STATE = f"{PUYAPY_PREFIX}_state.GlobalState"
CLS_GLOBAL_STATE_ALIAS = f"{PUYAPY_PREFIX}.GlobalState"
SUBROUTINE_HINT = f"{PUYAPY_PREFIX}_hints.subroutine"
SUBROUTINE_HINT_ALIAS = f"{PUYAPY_PREFIX}subroutine"
ABIMETHOD_DECORATOR = f"{PUYAPY_PREFIX}arc4.abimethod"
ABIMETHOD_DECORATOR_ALIAS = ABIMETHOD_DECORATOR
BAREMETHOD_DECORATOR = f"{PUYAPY_PREFIX}arc4.baremethod"
BAREMETHOD_DECORATOR_ALIAS = BAREMETHOD_DECORATOR
CLS_ARRAY = f"{PUYAPY_PREFIX}_array.Array"
CLS_ARRAY_ALIAS = f"{PUYAPY_PREFIX}Array"
APPROVAL_METHOD = "approval_program"
CLEAR_STATE_METHOD = "clear_state_program"
PUYAPY_OP_PREFIX = f"{PUYAPY_PREFIX}op."
URANGE = f"{PUYAPY_PREFIX}_unsigned_builtins.urange"
UENUMERATE = f"{PUYAPY_PREFIX}_unsigned_builtins.uenumerate"
ENSURE_BUDGET = f"{PUYAPY_PREFIX}_util.ensure_budget"
LOG = f"{PUYAPY_PREFIX}_util.log"
OP_UP_FEE_SOURCE = f"{PUYAPY_PREFIX}_util.OpUpFeeSource"
SUBMIT_TXNS = f"{PUYAPY_PREFIX}itxn.submit_txns"
CLS_ARC4_STRING = "puyapy.arc4.String"
CLS_ARC4_ADDRESS = "puyapy.arc4.Address"
CLS_ARC4_BOOL = "puyapy.arc4.Bool"
CLS_ARC4_BYTE = "puyapy.arc4.Byte"
CLS_ARC4_UINTN = "puyapy.arc4.UIntN"
CLS_ARC4_BIG_UINTN = "puyapy.arc4.BigUIntN"
CLS_ARC4_UFIXEDNXM = "puyapy.arc4.UFixedNxM"
CLS_ARC4_BIG_UFIXEDNXM = "puyapy.arc4.BigUFixedNxM"
CLS_ARC4_DYNAMIC_ARRAY = "puyapy.arc4.DynamicArray"
CLS_ARC4_STATIC_ARRAY = "puyapy.arc4.StaticArray"
CLS_ARC4_TUPLE = "puyapy.arc4.Tuple"
CLS_ARC4_STRUCT = "puyapy.arc4.Struct"

CONTRACT_STUB_TYPES = [
    CONTRACT_BASE,
    ARC4_CONTRACT_BASE,
]


ALLOWED_FUNCTION_DECORATORS = [
    SUBROUTINE_HINT,
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


class _TransactionTypeNames:
    def __init__(self, name: str, itxn_fields: str | None = None, itxn_result: str | None = None):
        self.gtxn = f"{PUYAPY_PREFIX}gtxn.{name}Transaction"
        self.itxn_fields = itxn_fields or f"{PUYAPY_PREFIX}itxn.{name}"
        self.itxn_result = itxn_result or f"{PUYAPY_PREFIX}itxn.{name}InnerTransaction"


TRANSACTION_TYPE_TO_CLS = {
    TransactionType.pay: _TransactionTypeNames("Payment"),
    TransactionType.keyreg: _TransactionTypeNames("KeyRegistration"),
    TransactionType.acfg: _TransactionTypeNames("AssetConfig"),
    TransactionType.axfer: _TransactionTypeNames("AssetTransfer"),
    TransactionType.afrz: _TransactionTypeNames("AssetFreeze"),
    TransactionType.appl: _TransactionTypeNames("ApplicationCall"),
    None: _TransactionTypeNames(
        "", f"{PUYAPY_PREFIX}itxn.InnerTransaction", f"{PUYAPY_PREFIX}itxn.InnerTransactionResult"
    ),
}

ENUM_CLS_ON_COMPLETE_ACTION = f"{PUYAPY_PREFIX}_constants.OnCompleteAction"
ENUM_CLS_TRANSACTION_TYPE = f"{PUYAPY_PREFIX}_constants.TransactionType"
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
