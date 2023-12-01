ALGOPY_PREFIX = "algopy."
ARC4_CONTRACT_BASE = f"{ALGOPY_PREFIX}arc4.ARC4Contract"
ARC4_CONTRACT_BASE_ALIAS = f"{ALGOPY_PREFIX}ARC4Contract"
CONTRACT_BASE = f"{ALGOPY_PREFIX}_contract.Contract"
CONTRACT_BASE_ALIAS = f"{ALGOPY_PREFIX}Contract"
STRUCT_BASE = f"{ALGOPY_PREFIX}_struct.Struct"
STRUCT_BASE_ALIAS = f"{ALGOPY_PREFIX}Struct"
CLS_ASSET = f"{ALGOPY_PREFIX}_primitives.Asset"
CLS_ASSET_ALIAS = f"{ALGOPY_PREFIX}Asset"
CLS_UINT64 = f"{ALGOPY_PREFIX}_primitives.UInt64"
CLS_UINT64_ALIAS = f"{ALGOPY_PREFIX}UInt64"
CLS_BYTES = f"{ALGOPY_PREFIX}_primitives.Bytes"
CLS_BYTES_ALIAS = f"{ALGOPY_PREFIX}Bytes"
CLS_BIGUINT = f"{ALGOPY_PREFIX}_primitives.BigUInt"
CLS_BIGUINT_ALIAS = f"{ALGOPY_PREFIX}BigUInt"
CLS_ADDRESS = f"{ALGOPY_PREFIX}_primitives.Address"
CLS_ADDRESS_ALIAS = f"{ALGOPY_PREFIX}Address"
SUBROUTINE_HINT = f"{ALGOPY_PREFIX}_hints.subroutine"
SUBROUTINE_HINT_ALIAS = f"{ALGOPY_PREFIX}subroutine"
ABIMETHOD_DECORATOR = f"{ALGOPY_PREFIX}arc4.abimethod"
ABIMETHOD_DECORATOR_ALIAS = ABIMETHOD_DECORATOR
CLS_ARRAY = f"{ALGOPY_PREFIX}_array.Array"
CLS_ARRAY_ALIAS = f"{ALGOPY_PREFIX}Array"
APPROVAL_METHOD = "approval_program"
CLEAR_STATE_METHOD = "clear_state_program"
ALGOPY_GEN_PREFIX = f"{ALGOPY_PREFIX}_gen."
LOCAL_PROXY_CLS = f"{ALGOPY_PREFIX}_storage.Local"
URANGE = f"{ALGOPY_PREFIX}_unsigned_builtins.urange"
UENUMERATE = f"{ALGOPY_PREFIX}_unsigned_builtins.uenumerate"
ENSURE_BUDGET = f"{ALGOPY_PREFIX}_util.ensure_budget"
OP_UP_FEE_SOURCE = f"{ALGOPY_PREFIX}_util.OpUpFeeSource"


CLS_ABI_STRING = "algopy.arc4.String"
CLS_ABI_UINTN = "algopy.arc4.UIntN"
CLS_ABI_DYNAMIC_ARRAY = "algopy.arc4.DynamicArray"
CLS_ABI_STATIC_ARRAY = "algopy.arc4.StaticArray"

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
]

ENUM_CLS_ON_COMPLETE_ACTION = f"{ALGOPY_PREFIX}_constants.OnCompleteAction"
ENUM_CLS_TRANSACTION_TYPE = f"{ALGOPY_PREFIX}_constants.TransactionType"
NAMED_INT_CONST_ENUM_DATA = {
    ENUM_CLS_ON_COMPLETE_ACTION: {
        "NoOp": (0, "NoOp"),
        "OptIn": (1, "OptIn"),
        "CloseOut": (2, "CloseOut"),
        "ClearState": (3, "ClearState"),
        "UpdateApplication": (4, "UpdateApplication"),
        "DeleteApplication": (5, "DeleteApplication"),
    },
    ENUM_CLS_TRANSACTION_TYPE: {
        "Payment": (1, "pay"),
        "KeyRegistration": (2, "keyreg"),
        "AssetConfig": (3, "acfg"),
        "AssetTransfer": (4, "axfer"),
        "AssetFreeze": (5, "afrz"),
        "ApplicationCall": (6, "appl"),
    },
}
