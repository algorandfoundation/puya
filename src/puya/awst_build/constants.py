import enum

from puya.models import OnCompletionAction

ALGOPY_PREFIX = "algopy."
ARC4_PREFIX = f"{ALGOPY_PREFIX}arc4."
ARC4_CONTRACT_BASE = f"{ARC4_PREFIX}ARC4Contract"
# special case for arc4 where algopy alias is present in algopy namespace
ARC4_CONTRACT_BASE_ALIAS = f"{ALGOPY_PREFIX}ARC4Contract"
ARC4_SIGNATURE = f"{ARC4_PREFIX}arc4_signature"
ARC4_SIGNATURE_ALIAS = ARC4_SIGNATURE
CONTRACT_BASE = f"{ALGOPY_PREFIX}_contract.Contract"
CONTRACT_BASE_ALIAS = f"{ALGOPY_PREFIX}Contract"
STRUCT_META = f"{ALGOPY_PREFIX}_struct._StructMeta"
STRUCT_BASE = f"{ALGOPY_PREFIX}_struct.Struct"
STRUCT_BASE_ALIAS = f"{ALGOPY_PREFIX}Struct"
CLS_ACCOUNT = f"{ALGOPY_PREFIX}_reference.Account"
CLS_ACCOUNT_ALIAS = f"{ALGOPY_PREFIX}Account"
CLS_ASSET = f"{ALGOPY_PREFIX}_reference.Asset"
CLS_ASSET_ALIAS = f"{ALGOPY_PREFIX}Asset"
CLS_APPLICATION = f"{ALGOPY_PREFIX}_reference.Application"
CLS_APPLICATION_ALIAS = f"{ALGOPY_PREFIX}Application"
CLS_UINT64 = f"{ALGOPY_PREFIX}_primitives.UInt64"
CLS_UINT64_ALIAS = f"{ALGOPY_PREFIX}UInt64"
CLS_BYTES = f"{ALGOPY_PREFIX}_primitives.Bytes"
CLS_BYTES_ALIAS = f"{ALGOPY_PREFIX}Bytes"
CLS_BYTES_BACKED = f"{ALGOPY_PREFIX}_primitives.BytesBacked"
CLS_STRING = f"{ALGOPY_PREFIX}_primitives.String"
CLS_STRING_ALIAS = f"{ALGOPY_PREFIX}String"
CLS_BIGUINT = f"{ALGOPY_PREFIX}_primitives.BigUInt"
CLS_BIGUINT_ALIAS = f"{ALGOPY_PREFIX}BigUInt"
CLS_TRANSACTION_BASE = f"{ALGOPY_PREFIX}gtxn.TransactionBase"
CLS_LOCAL_STATE = f"{ALGOPY_PREFIX}_state.LocalState"
CLS_LOCAL_STATE_ALIAS = f"{ALGOPY_PREFIX}LocalState"
CLS_GLOBAL_STATE = f"{ALGOPY_PREFIX}_state.GlobalState"
CLS_GLOBAL_STATE_ALIAS = f"{ALGOPY_PREFIX}GlobalState"
CLS_BOX_PROXY = f"{ALGOPY_PREFIX}_box.Box"
CLS_BOX_PROXY_ALIAS = f"{ALGOPY_PREFIX}Box"
CLS_BOX_REF_PROXY = f"{ALGOPY_PREFIX}_box.BoxRef"
CLS_BOX_REF_PROXY_ALIAS = f"{ALGOPY_PREFIX}BoxRef"
CLS_BOX_MAP_PROXY = f"{ALGOPY_PREFIX}_box.BoxMap"
CLS_BOX_MAP_PROXY_ALIAS = f"{ALGOPY_PREFIX}BoxMap"
SUBROUTINE_HINT = f"{ALGOPY_PREFIX}_hints.subroutine"
LOGICSIG_DECORATOR = f"{ALGOPY_PREFIX}_logic_sig.logicsig"
LOGICSIG_DECORATOR_ALIAS = f"{ALGOPY_PREFIX}.logicsig"
SUBROUTINE_HINT_ALIAS = f"{ALGOPY_PREFIX}subroutine"
ABIMETHOD_DECORATOR = f"{ALGOPY_PREFIX}arc4.abimethod"
ABIMETHOD_DECORATOR_ALIAS = ABIMETHOD_DECORATOR
BAREMETHOD_DECORATOR = f"{ALGOPY_PREFIX}arc4.baremethod"
BAREMETHOD_DECORATOR_ALIAS = BAREMETHOD_DECORATOR
CLS_ARRAY = f"{ALGOPY_PREFIX}_array.Array"
CLS_ARRAY_ALIAS = f"{ALGOPY_PREFIX}Array"
APPROVAL_METHOD = "approval_program"
CLEAR_STATE_METHOD = "clear_state_program"
ALGOPY_OP_PREFIX = f"{ALGOPY_PREFIX}op."
URANGE = f"{ALGOPY_PREFIX}_unsigned_builtins.urange"
UENUMERATE = f"{ALGOPY_PREFIX}_unsigned_builtins.uenumerate"
ENSURE_BUDGET = f"{ALGOPY_PREFIX}_util.ensure_budget"
LOG = f"{ALGOPY_PREFIX}_util.log"
EMIT = f"{ARC4_PREFIX}emit"
OP_UP_FEE_SOURCE = f"{ALGOPY_PREFIX}_util.OpUpFeeSource"
SUBMIT_TXNS = f"{ALGOPY_PREFIX}itxn.submit_txns"
CLS_ARC4_STRING = "algopy.arc4.String"
CLS_ARC4_ADDRESS = "algopy.arc4.Address"
CLS_ARC4_BOOL = "algopy.arc4.Bool"
CLS_ARC4_BYTE = "algopy.arc4.Byte"
CLS_ARC4_UINTN = "algopy.arc4.UIntN"
CLS_ARC4_BIG_UINTN = "algopy.arc4.BigUIntN"
CLS_ARC4_UFIXEDNXM = "algopy.arc4.UFixedNxM"
CLS_ARC4_BIG_UFIXEDNXM = "algopy.arc4.BigUFixedNxM"
CLS_ARC4_DYNAMIC_ARRAY = "algopy.arc4.DynamicArray"
CLS_ARC4_STATIC_ARRAY = "algopy.arc4.StaticArray"
CLS_ARC4_DYNAMIC_BYTES = "algopy.arc4.DynamicBytes"
CLS_ARC4_TUPLE = "algopy.arc4.Tuple"
CLS_ARC4_STRUCT = "algopy.arc4.Struct"
CLS_ARC4_STRUCT_META = "algopy.arc4._StructMeta"
CLS_ARC4_ABI_CALL = "algopy.arc4.abi_call"
CLS_ARC4_CLIENT = "algopy.arc4.ARC4Client"
CLS_TEMPLATE_VAR_METHOD = f"{ALGOPY_PREFIX}_template_variables.TemplateVar"

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
        self.gtxn = f"{ALGOPY_PREFIX}gtxn.{name}Transaction"
        self.itxn_fields = itxn_fields or f"{ALGOPY_PREFIX}itxn.{name}"
        self.itxn_result = itxn_result or f"{ALGOPY_PREFIX}itxn.{name}InnerTransaction"


TRANSACTION_TYPE_TO_CLS = {
    TransactionType.pay: _TransactionTypeNames("Payment"),
    TransactionType.keyreg: _TransactionTypeNames("KeyRegistration"),
    TransactionType.acfg: _TransactionTypeNames("AssetConfig"),
    TransactionType.axfer: _TransactionTypeNames("AssetTransfer"),
    TransactionType.afrz: _TransactionTypeNames("AssetFreeze"),
    TransactionType.appl: _TransactionTypeNames("ApplicationCall"),
    None: _TransactionTypeNames(
        "", f"{ALGOPY_PREFIX}itxn.InnerTransaction", f"{ALGOPY_PREFIX}itxn.InnerTransactionResult"
    ),
}

ENUM_CLS_ON_COMPLETE_ACTION = f"{ALGOPY_PREFIX}_constants.OnCompleteAction"
ENUM_CLS_TRANSACTION_TYPE = f"{ALGOPY_PREFIX}_constants.TransactionType"
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
