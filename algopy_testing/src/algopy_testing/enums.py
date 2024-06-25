from enum import Enum, IntEnum, StrEnum


class OnCompleteAction(Enum):
    NoOp = 0
    OptIn = 1
    CloseOut = 2
    ClearState = 3
    UpdateApplication = 4
    DeleteApplication = 5


class TransactionType(IntEnum):
    Payment = 0
    KeyRegistration = 1
    AssetConfig = 2
    AssetTransfer = 3
    AssetFreeze = 4
    ApplicationCall = 5


class ECDSA(Enum):
    Secp256k1 = 0
    Secp256r1 = 1


class VrfVerify(Enum):
    VrfAlgorand = 0


class Base64(Enum):
    URLEncoding = 0
    StdEncoding = 1


class EC(StrEnum):
    """Available values for the `EC` enum"""

    BN254g1 = "BN254g1"
    BN254g2 = "BN254g2"
    BLS12_381g1 = "BLS12_381g1"
    BLS12_381g2 = "BLS12_381g2"
