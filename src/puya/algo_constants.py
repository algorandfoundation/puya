ZERO_ADDRESS = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
ENCODED_ADDRESS_LENGTH = 58
PUBLIC_KEY_HASH_LENGTH = 32
ADDRESS_CHECKSUM_LENGTH = 4
MAX_BIGUINT_BITS = 512
MAX_UINT64 = 2**64 - 1
MAX_BIGUINT_BYTES = MAX_BIGUINT_BITS // 8
MAX_BYTES_LENGTH = 4096
MAX_SCRATCH_SLOT_NUMBER = 255
MAX_GLOBAL_STATE_KEYS = 64
MAX_LOCAL_STATE_KEYS = 16
MAX_STATE_KEY_LENGTH = 64
MIN_BOX_KEY_LENGTH = 1
MAX_BOX_KEY_LENGTH = 64
MAX_TRANSACTION_GROUP_SIZE = 16
MAX_APP_PAGE_SIZE = 2048
HASH_PREFIX_PROGRAM = b"Program"
"""Represents the prefix added to a program before hashing e.g. for a LogicSigs address"""
# Which language versions does this version of puya support targeting
# This will typically just be the current mainnet version and potentially the vNext if it doesn't
# contain breaking changes
SUPPORTED_AVM_VERSIONS = [10, 11, 12]
# Which language version is currently deployed to mainnet
MAINNET_AVM_VERSION = 10
