ZERO_ADDRESS = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
ENCODED_ADDRESS_LENGTH = 58
PUBLIC_KEY_HASH_LENGTH = 32
ADDRESS_CHECKSUM_LENGTH = 4
MAX_BIGUINT_BITS = 512
MAX_BIGUINT_BYTES = MAX_BIGUINT_BITS // 8
MAX_BYTES_LENGTH = 4096
MAX_SCRATCH_SLOT_NUMBER = 255


# Which language versions does this version of puya support targeting
# This will typically just be the current mainnet version and potentially the vNext if it doesn't
# contain breaking changes
SUPPORTED_TEAL_LANGUAGE_VERSIONS = [10]
# Which language version is currently deployed to mainnet
MAINNET_TEAL_LANGUAGE_VERSION = 10
