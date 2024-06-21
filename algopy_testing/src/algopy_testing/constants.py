UINT8_SIZE = 8
UINT16_SIZE = 16
UINT64_SIZE = 64
UINT512_SIZE = 512
MAX_BYTES_SIZE = 4096
MAX_LOG_SIZE = 1024
MAX_UINT8 = 2**UINT8_SIZE - 1
MAX_UINT16 = 2**UINT16_SIZE - 1
MAX_UINT64 = 2**UINT64_SIZE - 1
MAX_UINT512 = 2**UINT512_SIZE - 1
MAX_UINT64_BIT_SHIFT = UINT64_SIZE - 1
UINT64_BYTES_LENGTH = UINT64_SIZE // 8
UINT512_BYTES_LENGTH = UINT512_SIZE // 8
BITS_IN_BYTE = 8
ARC4_RETURN_PREFIX = b"\x15\x1f\x7c\x75"

DEFAULT_TEST_CTX_OPCODE_BUDGET = 2_000
DEFAULT_GLOBAL_GENESIS_HASH = b"\x85Y\xb5\x14x\xfd\x89\xc1vC\xd0]\x15\xa8\xaek\x10\xabG\xbbm\x8a1\x88\x11V\xe6\xbd;\xae\x95\xd1"  # noqa: E501
