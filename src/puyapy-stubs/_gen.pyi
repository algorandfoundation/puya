import enum
from typing import Never

from puyapy import Account, BigUInt, Bytes, UInt64

class Base64(enum.StrEnum):
    URLEncoding = enum.auto()
    StdEncoding = enum.auto()

class Ecdsa(enum.StrEnum):
    Secp256k1 = enum.auto()
    Secp256r1 = enum.auto()

class VrfVerify(enum.StrEnum):
    VrfAlgorand = enum.auto()

def addw(a: UInt64 | int, b: UInt64 | int, /) -> tuple[UInt64, UInt64]:
    """
    A plus B as a 128-bit result. X is the carry-bit, Y is the low-order 64 bits.

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X, Y]
    TEAL: addw

    """

def app_opted_in(a: Account | UInt64 | int, b: UInt64 | int, /) -> bool:
    """
    1 if account A is opted in to application B, else 0
    params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset). Return: 1 if opted in and 0 otherwise.

    Groups: State Access

    Stack: [..., A, B] -> [..., X]
    TEAL: app_opted_in

    """

def arg(a: UInt64 | int, /) -> Bytes:
    """
    Ath LogicSig argument

    Groups: Loading Values

    Stack: [..., A] -> [..., X]
    TEAL: args

    """

def balance(a: Account | UInt64 | int, /) -> UInt64:
    """
    balance for account A, in microalgos. The balance is observed after the effects of previous transactions in the group, and after the fee for the current transaction is deducted. Changes caused by inner transactions are observable immediately following `itxn_submit`
    params: Txn.Accounts offset (or, since v4, an _available_ account address). Return: value.

    Groups: State Access

    Stack: [..., A] -> [..., X]
    TEAL: balance

    """

def base64_decode(e: Base64, a: Bytes | bytes, /) -> Bytes:
    """
    decode A which was base64-encoded using _encoding_ E. Fail if A is not base64 encoded with encoding E
    *Warning*: Usage should be restricted to very rare use cases. In almost all cases, smart contracts should directly handle non-encoded byte-strings.	This opcode should only be used in cases where base64 is the only available option, e.g. interoperability with a third-party that only signs base64 strings.

     Decodes A using the base64 encoding E. Specify the encoding with an immediate arg either as URL and Filename Safe (`URLEncoding`) or Standard (`StdEncoding`). See [RFC 4648 sections 4 and 5](https://rfc-editor.org/rfc/rfc4648.html#section-4). It is assumed that the encoding ends with the exact number of `=` padding characters as required by the RFC. When padding occurs, any unused pad bits in the encoding must be set to zero or the decoding will fail. The special cases of `\n` and `\r` are allowed but completely ignored. An error will result when attempting to decode a string with a character that is not in the encoding alphabet or not one of `=`, `\r`, or `\n`.

    Groups: Byte Array Manipulation

    Stack: [..., A] -> [..., X]
    TEAL: base64_decode E

    :param Base64 e: encoding index
    """

def bitlen(a: Bytes | bytes | UInt64 | int, /) -> UInt64:
    """
    The highest set bit in A. If A is a byte-array, it is interpreted as a big-endian unsigned integer. bitlen of 0 is 0, bitlen of 8 is 4
    bitlen interprets arrays as big-endian integers, unlike setbit/getbit

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: bitlen

    """

def bsqrt(a: BigUInt, /) -> BigUInt:
    """
    The largest integer I such that I^2 <= A. A and I are interpreted as big-endian unsigned integers

    Groups: Byte Array Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: bsqrt

    """

def btoi(a: Bytes | bytes, /) -> UInt64:
    """
    converts big-endian byte array A to uint64. Fails if len(A) > 8. Padded by leading 0s if len(A) < 8.
    `btoi` fails if the input is longer than 8 bytes.

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: btoi

    """

def bzero(a: UInt64 | int, /) -> Bytes:
    """
    zero filled byte-array of length A

    Groups: Loading Values

    Stack: [..., A] -> [..., X]
    TEAL: bzero

    """

def concat(a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
    """
    join A and B
    `concat` fails if the result would be greater than 4096 bytes.

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X]
    TEAL: concat

    """

def divmodw(
    a: UInt64 | int, b: UInt64 | int, c: UInt64 | int, d: UInt64 | int, /
) -> tuple[UInt64, UInt64, UInt64, UInt64]:
    """
    W,X = (A,B / C,D); Y,Z = (A,B modulo C,D)
    The notation J,K indicates that two uint64 values J and K are interpreted as a uint128 value, with J as the high uint64 and K the low.

    Groups: Arithmetic

    Stack: [..., A, B, C, D] -> [..., W, X, Y, Z]
    TEAL: divmodw

    """

def divw(a: UInt64 | int, b: UInt64 | int, c: UInt64 | int, /) -> UInt64:
    """
    A,B / C. Fail if C == 0 or if result overflows.
    The notation A,B indicates that A and B are interpreted as a uint128 value, with A as the high uint64 and B the low.

    Groups: Arithmetic

    Stack: [..., A, B, C] -> [..., X]
    TEAL: divw

    """

def ecdsa_pk_decompress(v: Ecdsa, a: Bytes | bytes, /) -> tuple[Bytes, Bytes]:
    """
    decompress pubkey A into components X, Y
    The 33 byte public key in a compressed form to be decompressed into X and Y (top) components. All values are big-endian encoded.

    Groups: Arithmetic

    Stack: [..., A] -> [..., X, Y]
    TEAL: ecdsa_pk_decompress V

    :param Ecdsa v: curve index
    """

def ecdsa_pk_recover(
    v: Ecdsa, a: Bytes | bytes, b: UInt64 | int, c: Bytes | bytes, d: Bytes | bytes, /
) -> tuple[Bytes, Bytes]:
    """
    for (data A, recovery id B, signature C, D) recover a public key
    S (top) and R elements of a signature, recovery id and data (bottom) are expected on the stack and used to deriver a public key. All values are big-endian encoded. The signed data must be 32 bytes long.

    Groups: Arithmetic

    Stack: [..., A, B, C, D] -> [..., X, Y]
    TEAL: ecdsa_pk_recover V

    :param Ecdsa v: curve index
    """

def ecdsa_verify(
    v: Ecdsa,
    a: Bytes | bytes,
    b: Bytes | bytes,
    c: Bytes | bytes,
    d: Bytes | bytes,
    e: Bytes | bytes,
    /,
) -> bool:
    """
    for (data A, signature B, C and pubkey D, E) verify the signature of the data against the pubkey => {0 or 1}
    The 32 byte Y-component of a public key is the last element on the stack, preceded by X-component of a pubkey, preceded by S and R components of a signature, preceded by the data that is fifth element on the stack. All values are big-endian encoded. The signed data must be 32 bytes long, and signatures in lower-S form are only accepted.

    Groups: Arithmetic

    Stack: [..., A, B, C, D, E] -> [..., X]
    TEAL: ecdsa_verify V

    :param Ecdsa v: curve index
    """

def ed25519verify(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    """
    for (data A, signature B, pubkey C) verify the signature of ("ProgData" || program_hash || data) against the pubkey => {0 or 1}
    The 32 byte public key is the last element on the stack, preceded by the 64 byte signature at the second-to-last element on the stack, preceded by the data which was signed at the third-to-last element on the stack.

    Groups: Arithmetic

    Stack: [..., A, B, C] -> [..., X]
    TEAL: ed25519verify

    """

def ed25519verify_bare(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    """
    for (data A, signature B, pubkey C) verify the signature of the data against the pubkey => {0 or 1}

    Groups: Arithmetic

    Stack: [..., A, B, C] -> [..., X]
    TEAL: ed25519verify_bare

    """

def err() -> Never:
    """
    Fail immediately.

    Groups: Flow Control

    Stack: [...] -> [...]
    TEAL: err

    """

def exit(a: UInt64 | int, /) -> Never:
    """
    use A as success value; end

    Groups: Flow Control

    Stack: [..., A] -> [...]
    TEAL: return

    """

def exp(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    A raised to the Bth power. Fail if A == B == 0 and on overflow

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X]
    TEAL: exp

    """

def expw(a: UInt64 | int, b: UInt64 | int, /) -> tuple[UInt64, UInt64]:
    """
    A raised to the Bth power as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low. Fail if A == B == 0 or if the results exceeds 2^128-1

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X, Y]
    TEAL: expw

    """

def extract(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    A range of bytes from A starting at B up to but not including B+C. If B+C is larger than the array length, the program fails
    `extract3` can be called using `extract` with no immediates.

    Groups: Byte Array Manipulation

    Stack: [..., A, B, C] -> [..., X]
    TEAL: extract3

    """

def extract_uint16(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    A uint16 formed from a range of big-endian bytes from A starting at B up to but not including B+2. If B+2 is larger than the array length, the program fails

    Groups: Byte Array Manipulation

    Stack: [..., A, B] -> [..., X]
    TEAL: extract_uint16

    """

def extract_uint32(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    A uint32 formed from a range of big-endian bytes from A starting at B up to but not including B+4. If B+4 is larger than the array length, the program fails

    Groups: Byte Array Manipulation

    Stack: [..., A, B] -> [..., X]
    TEAL: extract_uint32

    """

def extract_uint64(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    A uint64 formed from a range of big-endian bytes from A starting at B up to but not including B+8. If B+8 is larger than the array length, the program fails

    Groups: Byte Array Manipulation

    Stack: [..., A, B] -> [..., X]
    TEAL: extract_uint64

    """

def gaid(a: UInt64 | int, /) -> UInt64:
    """
    ID of the asset or application created in the Ath transaction of the current group
    `gaids` fails unless the requested transaction created an asset or application and A < GroupIndex.

    Groups: Loading Values

    Stack: [..., A] -> [..., X]
    TEAL: gaids

    """

def getbit(a: Bytes | bytes | UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    Bth bit of (byte-array or integer) A. If B is greater than or equal to the bit length of the value (8*byte length), the program fails
    see explanation of bit ordering in setbit

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X]
    TEAL: getbit

    """

def getbyte(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    Bth byte of A, as an integer. If B is greater than or equal to the array length, the program fails

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X]
    TEAL: getbyte

    """

def gload_bytes(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
    """
    Bth scratch space value of the Ath transaction in the current group

    Groups: Loading Values

    Stack: [..., A, B] -> [..., X]
    TEAL: gloadss

    """

def gload_uint64(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    Bth scratch space value of the Ath transaction in the current group

    Groups: Loading Values

    Stack: [..., A, B] -> [..., X]
    TEAL: gloadss

    """

def itob(a: UInt64 | int, /) -> Bytes:
    """
    converts uint64 A to big-endian byte array, always of length 8

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: itob

    """

def keccak256(a: Bytes | bytes, /) -> Account:
    """
    Keccak256 hash of value A, yields [32]byte

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: keccak256

    """

def log(a: Bytes | bytes, /) -> None:
    """
    write A to log state of the current application
    `log` fails if called more than MaxLogCalls times in a program, or if the sum of logged bytes exceeds 1024 bytes.

    Groups: State Access

    Stack: [..., A] -> [...]
    TEAL: log

    """

def min_balance(a: Account | UInt64 | int, /) -> UInt64:
    """
    minimum required balance for account A, in microalgos. Required balance is affected by ASA, App, and Box usage. When creating or opting into an app, the minimum balance grows before the app code runs, therefore the increase is visible there. When deleting or closing out, the minimum balance decreases after the app executes. Changes caused by inner transactions or box usage are observable immediately following the opcode effecting the change.
    params: Txn.Accounts offset (or, since v4, an _available_ account address). Return: value.

    Groups: State Access

    Stack: [..., A] -> [..., X]
    TEAL: min_balance

    """

def mulw(a: UInt64 | int, b: UInt64 | int, /) -> tuple[UInt64, UInt64]:
    """
    A times B as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X, Y]
    TEAL: mulw

    """

def replace(a: Bytes | bytes, b: UInt64 | int, c: Bytes | bytes, /) -> Bytes:
    """
    Copy of A with the bytes starting at B replaced by the bytes of C. Fails if B+len(C) exceeds len(A)
    `replace3` can be called using `replace` with no immediates.

    Groups: Byte Array Manipulation

    Stack: [..., A, B, C] -> [..., X]
    TEAL: replace3

    """

def setbit_bytes(a: Bytes | bytes | UInt64 | int, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8*byte length), the program fails
    When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.

    Groups: Arithmetic

    Stack: [..., A, B, C] -> [..., X]
    TEAL: setbit

    """

def setbit_uint64(a: Bytes | bytes | UInt64 | int, b: UInt64 | int, c: UInt64 | int, /) -> UInt64:
    """
    Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8*byte length), the program fails
    When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.

    Groups: Arithmetic

    Stack: [..., A, B, C] -> [..., X]
    TEAL: setbit

    """

def setbyte(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    Copy of A with the Bth byte set to small integer (between 0..255) C. If B is greater than or equal to the array length, the program fails

    Groups: Arithmetic

    Stack: [..., A, B, C] -> [..., X]
    TEAL: setbyte

    """

def sha256(a: Bytes | bytes, /) -> Account:
    """
    SHA256 hash of value A, yields [32]byte

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: sha256

    """

def sha3_256(a: Bytes | bytes, /) -> Bytes:
    """
    SHA3_256 hash of value A, yields [32]byte

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: sha3_256

    """

def sha512_256(a: Bytes | bytes, /) -> Account:
    """
    SHA512_256 hash of value A, yields [32]byte

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: sha512_256

    """

def shl(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    A times 2^B, modulo 2^64

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X]
    TEAL: shl

    """

def shr(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    A divided by 2^B

    Groups: Arithmetic

    Stack: [..., A, B] -> [..., X]
    TEAL: shr

    """

def sqrt(a: UInt64 | int, /) -> UInt64:
    """
    The largest integer I such that I^2 <= A

    Groups: Arithmetic

    Stack: [..., A] -> [..., X]
    TEAL: sqrt

    """

def substring(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    A range of bytes from A starting at B up to but not including C. If C < B, or either is larger than the array length, the program fails

    Groups: Byte Array Manipulation

    Stack: [..., A, B, C] -> [..., X]
    TEAL: substring3

    """

def vrf_verify(
    s: VrfVerify, a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /
) -> tuple[Bytes, bool]:
    """
    Verify the proof B of message A against pubkey C. Returns vrf output and verification flag.
    `VrfAlgorand` is the VRF used in Algorand. It is ECVRF-ED25519-SHA512-Elligator2, specified in the IETF internet draft [draft-irtf-cfrg-vrf-03](https://datatracker.ietf.org/doc/draft-irtf-cfrg-vrf/03/).

    Groups: Arithmetic

    Stack: [..., A, B, C] -> [..., X, Y]
    TEAL: vrf_verify S

    :param VrfVerify s:  parameters index
    """

class AcctParamsGet:
    @staticmethod
    def acct_balance(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: Account balance in microalgos
        """
    @staticmethod
    def acct_min_balance(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: Minimum required balance for account, in microalgos
        """
    @staticmethod
    def acct_auth_addr(a: Account | UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[Account, bool]: Address the account is rekeyed to.
        """
    @staticmethod
    def acct_total_num_uint(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The total number of uint64 values allocated by this account in Global and Local States.
        """
    @staticmethod
    def acct_total_num_byte_slice(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The total number of byte array values allocated by this account in Global and Local States.
        """
    @staticmethod
    def acct_total_extra_app_pages(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The number of extra app code pages used by this account.
        """
    @staticmethod
    def acct_total_apps_created(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The number of existing apps created by this account.
        """
    @staticmethod
    def acct_total_apps_opted_in(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The number of apps this account is opted into.
        """
    @staticmethod
    def acct_total_assets_created(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The number of existing ASAs created by this account.
        """
    @staticmethod
    def acct_total_assets(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The numbers of ASAs held by this account (including ASAs this account created).
        """
    @staticmethod
    def acct_total_boxes(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The number of existing boxes created by this account's app.
        """
    @staticmethod
    def acct_total_box_bytes(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A. Y is 1 if A owns positive algos, else 0

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: acct_params_get F

        :returns tuple[UInt64, bool]: The total number of bytes used by this account's app's box keys and values.
        """

class AppGlobals:
    @staticmethod
    def get_bytes(a: Bytes | bytes, /) -> Bytes:
        """
        global state of the key A in the current application
        params: state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A] -> [..., X]
        TEAL: app_global_get

        """
    @staticmethod
    def get_uint64(a: Bytes | bytes, /) -> UInt64:
        """
        global state of the key A in the current application
        params: state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A] -> [..., X]
        TEAL: app_global_get

        """
    @staticmethod
    def get_ex_bytes(a: UInt64 | int, b: Bytes | bytes, /) -> tuple[Bytes, bool]:
        """
        X is the global state of application A, key B. Y is 1 if key existed, else 0
        params: Txn.ForeignApps offset (or, since v4, an _available_ application id), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A, B] -> [..., X, Y]
        TEAL: app_global_get_ex

        """
    @staticmethod
    def get_ex_uint64(a: UInt64 | int, b: Bytes | bytes, /) -> tuple[UInt64, bool]:
        """
        X is the global state of application A, key B. Y is 1 if key existed, else 0
        params: Txn.ForeignApps offset (or, since v4, an _available_ application id), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A, B] -> [..., X, Y]
        TEAL: app_global_get_ex

        """
    @staticmethod
    def delete(a: Bytes | bytes, /) -> None:
        """
        delete key A from the global state of the current application
        params: state key.

        Deleting a key which is already absent has no effect on the application global state. (In particular, it does _not_ cause the program to fail.)

        Groups: State Access

        Stack: [..., A] -> [...]
        TEAL: app_global_del

        """
    @staticmethod
    def put(a: Bytes | bytes, b: Bytes | bytes | UInt64 | int, /) -> None:
        """
        write B to key A in the global state of the current application

        Groups: State Access

        Stack: [..., A, B] -> [...]
        TEAL: app_global_put

        """

class AppLocals:
    @staticmethod
    def get_bytes(a: Account | UInt64 | int, b: Bytes | bytes, /) -> Bytes:
        """
        local state of the key B in the current application in account A
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A, B] -> [..., X]
        TEAL: app_local_get

        """
    @staticmethod
    def get_uint64(a: Account | UInt64 | int, b: Bytes | bytes, /) -> UInt64:
        """
        local state of the key B in the current application in account A
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A, B] -> [..., X]
        TEAL: app_local_get

        """
    @staticmethod
    def get_ex_bytes(
        a: Account | UInt64 | int, b: UInt64 | int, c: Bytes | bytes, /
    ) -> tuple[Bytes, bool]:
        """
        X is the local state of application B, key C in account A. Y is 1 if key existed, else 0
        params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A, B, C] -> [..., X, Y]
        TEAL: app_local_get_ex

        """
    @staticmethod
    def get_ex_uint64(
        a: Account | UInt64 | int, b: UInt64 | int, c: Bytes | bytes, /
    ) -> tuple[UInt64, bool]:
        """
        X is the local state of application B, key C in account A. Y is 1 if key existed, else 0
        params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Groups: State Access

        Stack: [..., A, B, C] -> [..., X, Y]
        TEAL: app_local_get_ex

        """
    @staticmethod
    def delete(a: Account | UInt64 | int, b: Bytes | bytes, /) -> None:
        """
        delete key B from account A's local state of the current application
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key.

        Deleting a key which is already absent has no effect on the application local state. (In particular, it does _not_ cause the program to fail.)

        Groups: State Access

        Stack: [..., A, B] -> [...]
        TEAL: app_local_del

        """
    @staticmethod
    def put(
        a: Account | UInt64 | int, b: Bytes | bytes, c: Bytes | bytes | UInt64 | int, /
    ) -> None:
        """
        write C to key B in account A's local state of the current application
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key, value.

        Groups: State Access

        Stack: [..., A, B, C] -> [...]
        TEAL: app_local_put

        """

class AppParamsGet:
    @staticmethod
    def app_approval_program(a: UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[Bytes, bool]: Bytecode of Approval Program
        """
    @staticmethod
    def app_clear_state_program(a: UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[Bytes, bool]: Bytecode of Clear State Program
        """
    @staticmethod
    def app_global_num_uint(a: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[UInt64, bool]: Number of uint64 values allowed in Global State
        """
    @staticmethod
    def app_global_num_byte_slice(a: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[UInt64, bool]: Number of byte array values allowed in Global State
        """
    @staticmethod
    def app_local_num_uint(a: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[UInt64, bool]: Number of uint64 values allowed in Local State
        """
    @staticmethod
    def app_local_num_byte_slice(a: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[UInt64, bool]: Number of byte array values allowed in Local State
        """
    @staticmethod
    def app_extra_program_pages(a: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[UInt64, bool]: Number of Extra Program Pages of code space
        """
    @staticmethod
    def app_creator(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[Account, bool]: Creator address
        """
    @staticmethod
    def app_address(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from app A. Y is 1 if A exists, else 0
        params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: app_params_get F

        :returns tuple[Account, bool]: Address for which this application has authority
        """

class AssetHoldingGet:
    @staticmethod
    def asset_balance(a: Account | UInt64 | int, b: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from account A's holding of asset B. Y is 1 if A is opted into B, else 0
        params: Txn.Accounts offset (or, since v4, an _available_ address), asset id (or, since v4, a Txn.ForeignAssets offset). Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A, B] -> [..., X, Y]
        TEAL: asset_holding_get F

        :returns tuple[UInt64, bool]: Amount of the asset unit held by this account
        """
    @staticmethod
    def asset_frozen(a: Account | UInt64 | int, b: UInt64 | int, /) -> tuple[bool, bool]:
        """
        X is field F from account A's holding of asset B. Y is 1 if A is opted into B, else 0
        params: Txn.Accounts offset (or, since v4, an _available_ address), asset id (or, since v4, a Txn.ForeignAssets offset). Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A, B] -> [..., X, Y]
        TEAL: asset_holding_get F

        :returns tuple[bool, bool]: Is the asset frozen or not
        """

class AssetParamsGet:
    @staticmethod
    def asset_total(a: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[UInt64, bool]: Total number of units of this asset
        """
    @staticmethod
    def asset_decimals(a: UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[UInt64, bool]: See AssetParams.Decimals
        """
    @staticmethod
    def asset_default_frozen(a: UInt64 | int, /) -> tuple[bool, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[bool, bool]: Frozen by default or not
        """
    @staticmethod
    def asset_unit_name(a: UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Bytes, bool]: Asset unit name
        """
    @staticmethod
    def asset_name(a: UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Bytes, bool]: Asset name
        """
    @staticmethod
    def asset_url(a: UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Bytes, bool]: URL with additional info about the asset
        """
    @staticmethod
    def asset_metadata_hash(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Account, bool]: Arbitrary commitment
        """
    @staticmethod
    def asset_manager(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Account, bool]: Manager address
        """
    @staticmethod
    def asset_reserve(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Account, bool]: Reserve address
        """
    @staticmethod
    def asset_freeze(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Account, bool]: Freeze address
        """
    @staticmethod
    def asset_clawback(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Account, bool]: Clawback address
        """
    @staticmethod
    def asset_creator(a: UInt64 | int, /) -> tuple[Account, bool]:
        """
        X is field F from asset A. Y is 1 if A exists, else 0
        params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.

        Groups: State Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: asset_params_get F

        :returns tuple[Account, bool]: Creator address
        """

class Block:
    @staticmethod
    def blk_seed(a: UInt64 | int, /) -> Bytes:
        """
        field F of block A. Fail unless A falls between txn.LastValid-1002 and txn.FirstValid (exclusive)

        Groups: State Access

        Stack: [..., A] -> [..., X]
        TEAL: block F

        """
    @staticmethod
    def blk_timestamp(a: UInt64 | int, /) -> UInt64:
        """
        field F of block A. Fail unless A falls between txn.LastValid-1002 and txn.FirstValid (exclusive)

        Groups: State Access

        Stack: [..., A] -> [..., X]
        TEAL: block F

        """

class Box:
    @staticmethod
    def create(a: Bytes | bytes, b: UInt64 | int, /) -> bool:
        """
        create a box named A, of length B. Fail if A is empty or B exceeds 32,768. Returns 0 if A already existed, else 1
        Newly created boxes are filled with 0 bytes. `box_create` will fail if the referenced box already exists with a different size. Otherwise, existing boxes are unchanged by `box_create`.

        Groups: Box Access

        Stack: [..., A, B] -> [..., X]
        TEAL: box_create

        """
    @staticmethod
    def delete(a: Bytes | bytes, /) -> bool:
        """
        delete box named A if it exists. Return 1 if A existed, 0 otherwise

        Groups: Box Access

        Stack: [..., A] -> [..., X]
        TEAL: box_del

        """
    @staticmethod
    def extract(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
        """
        read C bytes from box A, starting at offset B. Fail if A does not exist, or the byte range is outside A's size.

        Groups: Box Access

        Stack: [..., A, B, C] -> [..., X]
        TEAL: box_extract

        """
    @staticmethod
    def get(a: Bytes | bytes, /) -> tuple[Bytes, bool]:
        """
        X is the contents of box A if A exists, else ''. Y is 1 if A exists, else 0.
        For boxes that exceed 4,096 bytes, consider `box_create`, `box_extract`, and `box_replace`

        Groups: Box Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: box_get

        """
    @staticmethod
    def length(a: Bytes | bytes, /) -> tuple[UInt64, bool]:
        """
        X is the length of box A if A exists, else 0. Y is 1 if A exists, else 0.

        Groups: Box Access

        Stack: [..., A] -> [..., X, Y]
        TEAL: box_len

        """
    @staticmethod
    def put(a: Bytes | bytes, b: Bytes | bytes, /) -> None:
        """
        replaces the contents of box A with byte-array B. Fails if A exists and len(B) != len(box A). Creates A if it does not exist
        For boxes that exceed 4,096 bytes, consider `box_create`, `box_extract`, and `box_replace`

        Groups: Box Access

        Stack: [..., A, B] -> [...]
        TEAL: box_put

        """
    @staticmethod
    def replace(a: Bytes | bytes, b: UInt64 | int, c: Bytes | bytes, /) -> None:
        """
        write byte-array C into box A, starting at offset B. Fail if A does not exist, or the byte range is outside A's size.

        Groups: Box Access

        Stack: [..., A, B, C] -> [...]
        TEAL: box_replace

        """

class CreateInnerTransaction:
    @staticmethod
    def begin() -> None:
        """
        begin preparation of a new inner transaction in a new transaction group
        `itxn_begin` initializes Sender to the application address; Fee to the minimum allowable, taking into account MinTxnFee and credit from overpaying in earlier transactions; FirstValid/LastValid to the values in the invoking transaction, and all other fields to zero or empty values.

        Groups: Inner Transactions

        Stack: [...] -> [...]
        TEAL: itxn_begin

        """
    @staticmethod
    def next() -> None:
        """
        begin preparation of a new inner transaction in the same transaction group
        `itxn_next` initializes the transaction exactly as `itxn_begin` does

        Groups: Inner Transactions

        Stack: [...] -> [...]
        TEAL: itxn_next

        """
    @staticmethod
    def submit() -> None:
        """
        execute the current inner transaction group. Fail if executing this group would exceed the inner transaction limit, or if any transaction in the group fails.
        `itxn_submit` resets the current transaction so that it can not be resubmitted. A new `itxn_begin` is required to prepare another inner transaction.

        Groups: Inner Transactions

        Stack: [...] -> [...]
        TEAL: itxn_submit

        """
    @staticmethod
    def set_sender(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_fee(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: microalgos
        """
    @staticmethod
    def set_note(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: Any data up to 1024 bytes
        """
    @staticmethod
    def set_receiver(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_amount(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: microalgos
        """
    @staticmethod
    def set_close_remainder_to(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_vote_pk(a: Bytes | bytes | Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes | Account a: 32 byte address
        """
    @staticmethod
    def set_selection_pk(a: Bytes | bytes | Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes | Account a: 32 byte address
        """
    @staticmethod
    def set_vote_first(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: The first round that the participation key is valid.
        """
    @staticmethod
    def set_vote_last(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: The last round that the participation key is valid.
        """
    @staticmethod
    def set_vote_key_dilution(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Dilution for the 2-level participation key
        """
    @staticmethod
    def set_type(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: Transaction type as bytes
        """
    @staticmethod
    def set_type_enum(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Transaction type as integer
        """
    @staticmethod
    def set_xfer_asset(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Asset ID
        """
    @staticmethod
    def set_asset_amount(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: value in Asset's units
        """
    @staticmethod
    def set_asset_sender(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address. Source of assets if Sender is the Asset's Clawback address.
        """
    @staticmethod
    def set_asset_receiver(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_asset_close_to(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_application_id(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: ApplicationID from ApplicationCall transaction
        """
    @staticmethod
    def set_on_completion(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: ApplicationCall transaction on completion action
        """
    @staticmethod
    def set_application_args(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: Arguments passed to the application in the ApplicationCall transaction
        """
    @staticmethod
    def set_accounts(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: Accounts listed in the ApplicationCall transaction
        """
    @staticmethod
    def set_approval_program(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: Approval program
        """
    @staticmethod
    def set_clear_state_program(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: Clear state program
        """
    @staticmethod
    def set_rekey_to(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte Sender's new AuthAddr
        """
    @staticmethod
    def set_config_asset(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Asset ID in asset config transaction
        """
    @staticmethod
    def set_config_asset_total(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Total number of units of this asset created
        """
    @staticmethod
    def set_config_asset_decimals(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Number of digits to display after the decimal place when displaying the asset
        """
    @staticmethod
    def set_config_asset_default_frozen(a: bool | UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param bool | UInt64 | int a: Whether the asset's slots are frozen by default or not, 0 or 1
        """
    @staticmethod
    def set_config_asset_unit_name(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: Unit name of the asset
        """
    @staticmethod
    def set_config_asset_name(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: The asset name
        """
    @staticmethod
    def set_config_asset_url(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: URL
        """
    @staticmethod
    def set_config_asset_metadata_hash(a: Bytes | bytes | Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes | Account a: 32 byte commitment to unspecified asset metadata
        """
    @staticmethod
    def set_config_asset_manager(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_config_asset_reserve(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_config_asset_freeze(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_config_asset_clawback(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address
        """
    @staticmethod
    def set_freeze_asset(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Asset ID being frozen or un-frozen
        """
    @staticmethod
    def set_freeze_asset_account(a: Account, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Account a: 32 byte address of the account whose asset slot is being frozen or un-frozen
        """
    @staticmethod
    def set_freeze_asset_frozen(a: bool | UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param bool | UInt64 | int a: The new frozen value, 0 or 1
        """
    @staticmethod
    def set_assets(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Foreign Assets listed in the ApplicationCall transaction
        """
    @staticmethod
    def set_applications(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Foreign Apps listed in the ApplicationCall transaction
        """
    @staticmethod
    def set_global_num_uint(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Number of global state integers in ApplicationCall
        """
    @staticmethod
    def set_global_num_byte_slice(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Number of global state byteslices in ApplicationCall
        """
    @staticmethod
    def set_local_num_uint(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Number of local state integers in ApplicationCall
        """
    @staticmethod
    def set_local_num_byte_slice(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Number of local state byteslices in ApplicationCall
        """
    @staticmethod
    def set_extra_program_pages(a: UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param UInt64 | int a: Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.
        """
    @staticmethod
    def set_nonparticipation(a: bool | UInt64 | int, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param bool | UInt64 | int a: Marks an account nonparticipating for rewards
        """
    @staticmethod
    def set_state_proof_pk(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: 64 byte state proof public key
        """
    @staticmethod
    def set_approval_program_pages(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: Approval Program as an array of pages
        """
    @staticmethod
    def set_clear_state_program_pages(a: Bytes | bytes, /) -> None:
        """
        set field F of the current inner transaction to A
        `itxn_field` fails if A is of the wrong type for F, including a byte array of the wrong size for use as an address when F is an address field. `itxn_field` also fails if A is an account, asset, or app that is not _available_, or an attempt is made extend an array field beyond the limit imposed by consensus parameters. (Addresses set into asset params of acfg transactions need not be _available_.)

        Groups: Inner Transactions

        Stack: [..., A] -> [...]
        TEAL: itxn_field F

        :param Bytes | bytes a: ClearState Program as an array of pages
        """

class Global:
    @staticmethod
    def min_txn_fee() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: microalgos
        """
    @staticmethod
    def min_balance() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: microalgos
        """
    @staticmethod
    def max_txn_life() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: rounds
        """
    @staticmethod
    def zero_address() -> Account:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns Account: 32 byte address of all zero bytes
        """
    @staticmethod
    def group_size() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: Number of transactions in this atomic transaction group. At least 1
        """
    @staticmethod
    def logic_sig_version() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: Maximum supported version
        """
    @staticmethod
    def round() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: Current round number. Application mode only.
        """
    @staticmethod
    def latest_timestamp() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: Last confirmed block UNIX timestamp. Fails if negative. Application mode only.
        """
    @staticmethod
    def current_application_id() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: ID of current application executing. Application mode only.
        """
    @staticmethod
    def creator_address() -> Account:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns Account: Address of the creator of the current application. Application mode only.
        """
    @staticmethod
    def current_application_address() -> Account:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns Account: Address that the current application controls. Application mode only.
        """
    @staticmethod
    def group_id() -> Account:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns Account: ID of the transaction group. 32 zero bytes if the transaction is not part of a group.
        """
    @staticmethod
    def opcode_budget() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: The remaining cost that can be spent by opcodes in this program.
        """
    @staticmethod
    def caller_application_id() -> UInt64:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns UInt64: The application ID of the application that called this application. 0 if this application is at the top-level. Application mode only.
        """
    @staticmethod
    def caller_application_address() -> Account:
        """
        global field F

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: global F

        :returns Account: The application address of the application that called this application. ZeroAddress if this application is at the top-level. Application mode only.
        """

class InnerTransaction:
    @staticmethod
    def sender() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def fee() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: microalgos
        """
    @staticmethod
    def first_valid() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: round number
        """
    @staticmethod
    def first_valid_time() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: UNIX timestamp of block before txn.FirstValid. Fails if negative
        """
    @staticmethod
    def last_valid() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: round number
        """
    @staticmethod
    def note() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: Any data up to 1024 bytes
        """
    @staticmethod
    def lease() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte lease value
        """
    @staticmethod
    def receiver() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def amount() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: microalgos
        """
    @staticmethod
    def close_remainder_to() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_pk() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def selection_pk() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_first() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: The first round that the participation key is valid.
        """
    @staticmethod
    def vote_last() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: The last round that the participation key is valid.
        """
    @staticmethod
    def vote_key_dilution() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Dilution for the 2-level participation key
        """
    @staticmethod
    def type() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: Transaction type as bytes
        """
    @staticmethod
    def type_enum() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Transaction type as integer
        """
    @staticmethod
    def xfer_asset() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Asset ID
        """
    @staticmethod
    def asset_amount() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: value in Asset's units
        """
    @staticmethod
    def asset_sender() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address. Source of assets if Sender is the Asset's Clawback address.
        """
    @staticmethod
    def asset_receiver() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def asset_close_to() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def group_index() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1
        """
    @staticmethod
    def tx_id() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: The computed ID for this transaction. 32 bytes.
        """
    @staticmethod
    def application_id() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: ApplicationID from ApplicationCall transaction
        """
    @staticmethod
    def on_completion() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: ApplicationCall transaction on completion action
        """
    @staticmethod
    def application_args(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: itxnas F

        :returns Bytes: Arguments passed to the application in the ApplicationCall transaction
        """
    @staticmethod
    def num_app_args() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of ApplicationArgs
        """
    @staticmethod
    def accounts(a: UInt64 | int, /) -> Account:
        """
        Ath value of the array field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: itxnas F

        :returns Account: Accounts listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_accounts() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of Accounts
        """
    @staticmethod
    def approval_program() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: Approval program
        """
    @staticmethod
    def clear_state_program() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: Clear state program
        """
    @staticmethod
    def rekey_to() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte Sender's new AuthAddr
        """
    @staticmethod
    def config_asset() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Asset ID in asset config transaction
        """
    @staticmethod
    def config_asset_total() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Total number of units of this asset created
        """
    @staticmethod
    def config_asset_decimals() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of digits to display after the decimal place when displaying the asset
        """
    @staticmethod
    def config_asset_default_frozen() -> bool:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns bool: Whether the asset's slots are frozen by default or not, 0 or 1
        """
    @staticmethod
    def config_asset_unit_name() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: Unit name of the asset
        """
    @staticmethod
    def config_asset_name() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: The asset name
        """
    @staticmethod
    def config_asset_url() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: URL
        """
    @staticmethod
    def config_asset_metadata_hash() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte commitment to unspecified asset metadata
        """
    @staticmethod
    def config_asset_manager() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_reserve() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_freeze() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_clawback() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def freeze_asset() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Asset ID being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_account() -> Account:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Account: 32 byte address of the account whose asset slot is being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_frozen() -> bool:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns bool: The new frozen value, 0 or 1
        """
    @staticmethod
    def assets(a: UInt64 | int, /) -> UInt64:
        """
        Ath value of the array field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: itxnas F

        :returns UInt64: Foreign Assets listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_assets() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of Assets
        """
    @staticmethod
    def applications(a: UInt64 | int, /) -> UInt64:
        """
        Ath value of the array field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: itxnas F

        :returns UInt64: Foreign Apps listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_applications() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of Applications
        """
    @staticmethod
    def global_num_uint() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of global state integers in ApplicationCall
        """
    @staticmethod
    def global_num_byte_slice() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of global state byteslices in ApplicationCall
        """
    @staticmethod
    def local_num_uint() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of local state integers in ApplicationCall
        """
    @staticmethod
    def local_num_byte_slice() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of local state byteslices in ApplicationCall
        """
    @staticmethod
    def extra_program_pages() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.
        """
    @staticmethod
    def nonparticipation() -> bool:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns bool: Marks an account nonparticipating for rewards
        """
    @staticmethod
    def logs(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: itxnas F

        :returns Bytes: Log messages emitted by an application call (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def num_logs() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of Logs (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_asset_id() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_application_id() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def last_log() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: The last message emitted. Empty bytes if none were emitted. Application mode only
        """
    @staticmethod
    def state_proof_pk() -> Bytes:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns Bytes: 64 byte state proof public key
        """
    @staticmethod
    def approval_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: itxnas F

        :returns Bytes: Approval Program as an array of pages
        """
    @staticmethod
    def num_approval_program_pages() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of Approval Program pages
        """
    @staticmethod
    def clear_state_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: itxnas F

        :returns Bytes: ClearState Program as an array of pages
        """
    @staticmethod
    def num_clear_state_program_pages() -> UInt64:
        """
        field F of the last inner transaction

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: itxn F

        :returns UInt64: Number of ClearState Program pages
        """

class InnerTransactionGroup:
    @staticmethod
    def sender(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def fee(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: microalgos
        """
    @staticmethod
    def first_valid(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: round number
        """
    @staticmethod
    def first_valid_time(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: UNIX timestamp of block before txn.FirstValid. Fails if negative
        """
    @staticmethod
    def last_valid(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: round number
        """
    @staticmethod
    def note(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: Any data up to 1024 bytes
        """
    @staticmethod
    def lease(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte lease value
        """
    @staticmethod
    def receiver(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def amount(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: microalgos
        """
    @staticmethod
    def close_remainder_to(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_pk(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def selection_pk(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_first(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: The first round that the participation key is valid.
        """
    @staticmethod
    def vote_last(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: The last round that the participation key is valid.
        """
    @staticmethod
    def vote_key_dilution(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Dilution for the 2-level participation key
        """
    @staticmethod
    def type(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: Transaction type as bytes
        """
    @staticmethod
    def type_enum(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Transaction type as integer
        """
    @staticmethod
    def xfer_asset(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Asset ID
        """
    @staticmethod
    def asset_amount(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: value in Asset's units
        """
    @staticmethod
    def asset_sender(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address. Source of assets if Sender is the Asset's Clawback address.
        """
    @staticmethod
    def asset_receiver(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def asset_close_to(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def group_index(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1
        """
    @staticmethod
    def tx_id(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: The computed ID for this transaction. 32 bytes.
        """
    @staticmethod
    def application_id(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: ApplicationID from ApplicationCall transaction
        """
    @staticmethod
    def on_completion(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: ApplicationCall transaction on completion action
        """
    @staticmethod
    def application_args(t: int, a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F from the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: gitxnas T F

        :param int t: transaction group index
        :returns Bytes: Arguments passed to the application in the ApplicationCall transaction
        """
    @staticmethod
    def num_app_args(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of ApplicationArgs
        """
    @staticmethod
    def accounts(t: int, a: UInt64 | int, /) -> Account:
        """
        Ath value of the array field F from the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: gitxnas T F

        :param int t: transaction group index
        :returns Account: Accounts listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_accounts(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of Accounts
        """
    @staticmethod
    def approval_program(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: Approval program
        """
    @staticmethod
    def clear_state_program(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: Clear state program
        """
    @staticmethod
    def rekey_to(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte Sender's new AuthAddr
        """
    @staticmethod
    def config_asset(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Asset ID in asset config transaction
        """
    @staticmethod
    def config_asset_total(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Total number of units of this asset created
        """
    @staticmethod
    def config_asset_decimals(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of digits to display after the decimal place when displaying the asset
        """
    @staticmethod
    def config_asset_default_frozen(t: int, /) -> bool:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns bool: Whether the asset's slots are frozen by default or not, 0 or 1
        """
    @staticmethod
    def config_asset_unit_name(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: Unit name of the asset
        """
    @staticmethod
    def config_asset_name(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: The asset name
        """
    @staticmethod
    def config_asset_url(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: URL
        """
    @staticmethod
    def config_asset_metadata_hash(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte commitment to unspecified asset metadata
        """
    @staticmethod
    def config_asset_manager(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_reserve(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_freeze(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_clawback(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address
        """
    @staticmethod
    def freeze_asset(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Asset ID being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_account(t: int, /) -> Account:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Account: 32 byte address of the account whose asset slot is being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_frozen(t: int, /) -> bool:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns bool: The new frozen value, 0 or 1
        """
    @staticmethod
    def assets(t: int, a: UInt64 | int, /) -> UInt64:
        """
        Ath value of the array field F from the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: gitxnas T F

        :param int t: transaction group index
        :returns UInt64: Foreign Assets listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_assets(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of Assets
        """
    @staticmethod
    def applications(t: int, a: UInt64 | int, /) -> UInt64:
        """
        Ath value of the array field F from the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: gitxnas T F

        :param int t: transaction group index
        :returns UInt64: Foreign Apps listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_applications(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of Applications
        """
    @staticmethod
    def global_num_uint(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of global state integers in ApplicationCall
        """
    @staticmethod
    def global_num_byte_slice(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of global state byteslices in ApplicationCall
        """
    @staticmethod
    def local_num_uint(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of local state integers in ApplicationCall
        """
    @staticmethod
    def local_num_byte_slice(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of local state byteslices in ApplicationCall
        """
    @staticmethod
    def extra_program_pages(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.
        """
    @staticmethod
    def nonparticipation(t: int, /) -> bool:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns bool: Marks an account nonparticipating for rewards
        """
    @staticmethod
    def logs(t: int, a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F from the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: gitxnas T F

        :param int t: transaction group index
        :returns Bytes: Log messages emitted by an application call (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def num_logs(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of Logs (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_asset_id(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_application_id(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def last_log(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: The last message emitted. Empty bytes if none were emitted. Application mode only
        """
    @staticmethod
    def state_proof_pk(t: int, /) -> Bytes:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns Bytes: 64 byte state proof public key
        """
    @staticmethod
    def approval_program_pages(t: int, a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F from the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: gitxnas T F

        :param int t: transaction group index
        :returns Bytes: Approval Program as an array of pages
        """
    @staticmethod
    def num_approval_program_pages(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of Approval Program pages
        """
    @staticmethod
    def clear_state_program_pages(t: int, a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F from the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [..., A] -> [..., X]
        TEAL: gitxnas T F

        :param int t: transaction group index
        :returns Bytes: ClearState Program as an array of pages
        """
    @staticmethod
    def num_clear_state_program_pages(t: int, /) -> UInt64:
        """
        field F of the Tth transaction in the last inner group submitted

        Groups: Inner Transactions

        Stack: [...] -> [..., X]
        TEAL: gitxn T F

        :param int t: transaction group index
        :returns UInt64: Number of ClearState Program pages
        """

class JsonRef:
    @staticmethod
    def json_string(a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
        """
        key B's value, of type R, from a [valid](jsonspec.md) utf-8 encoded json object A
        *Warning*: Usage should be restricted to very rare use cases, as JSON decoding is expensive and quite limited. In addition, JSON objects are large and not optimized for size.

        Almost all smart contracts should use simpler and smaller methods (such as the [ABI](https://arc.algorand.foundation/ARCs/arc-0004). This opcode should only be used in cases where JSON is only available option, e.g. when a third-party only signs JSON.

        Groups: Byte Array Manipulation

        Stack: [..., A, B] -> [..., X]
        TEAL: json_ref R

        """
    @staticmethod
    def json_uint64(a: Bytes | bytes, b: Bytes | bytes, /) -> UInt64:
        """
        key B's value, of type R, from a [valid](jsonspec.md) utf-8 encoded json object A
        *Warning*: Usage should be restricted to very rare use cases, as JSON decoding is expensive and quite limited. In addition, JSON objects are large and not optimized for size.

        Almost all smart contracts should use simpler and smaller methods (such as the [ABI](https://arc.algorand.foundation/ARCs/arc-0004). This opcode should only be used in cases where JSON is only available option, e.g. when a third-party only signs JSON.

        Groups: Byte Array Manipulation

        Stack: [..., A, B] -> [..., X]
        TEAL: json_ref R

        """
    @staticmethod
    def json_object(a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
        """
        key B's value, of type R, from a [valid](jsonspec.md) utf-8 encoded json object A
        *Warning*: Usage should be restricted to very rare use cases, as JSON decoding is expensive and quite limited. In addition, JSON objects are large and not optimized for size.

        Almost all smart contracts should use simpler and smaller methods (such as the [ABI](https://arc.algorand.foundation/ARCs/arc-0004). This opcode should only be used in cases where JSON is only available option, e.g. when a third-party only signs JSON.

        Groups: Byte Array Manipulation

        Stack: [..., A, B] -> [..., X]
        TEAL: json_ref R

        """

class Transaction:
    @staticmethod
    def sender() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def fee() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: microalgos
        """
    @staticmethod
    def first_valid() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: round number
        """
    @staticmethod
    def first_valid_time() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: UNIX timestamp of block before txn.FirstValid. Fails if negative
        """
    @staticmethod
    def last_valid() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: round number
        """
    @staticmethod
    def note() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: Any data up to 1024 bytes
        """
    @staticmethod
    def lease() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte lease value
        """
    @staticmethod
    def receiver() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def amount() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: microalgos
        """
    @staticmethod
    def close_remainder_to() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_pk() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def selection_pk() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_first() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: The first round that the participation key is valid.
        """
    @staticmethod
    def vote_last() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: The last round that the participation key is valid.
        """
    @staticmethod
    def vote_key_dilution() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Dilution for the 2-level participation key
        """
    @staticmethod
    def type() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: Transaction type as bytes
        """
    @staticmethod
    def type_enum() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Transaction type as integer
        """
    @staticmethod
    def xfer_asset() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Asset ID
        """
    @staticmethod
    def asset_amount() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: value in Asset's units
        """
    @staticmethod
    def asset_sender() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address. Source of assets if Sender is the Asset's Clawback address.
        """
    @staticmethod
    def asset_receiver() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def asset_close_to() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def group_index() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1
        """
    @staticmethod
    def tx_id() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: The computed ID for this transaction. 32 bytes.
        """
    @staticmethod
    def application_id() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: ApplicationID from ApplicationCall transaction
        """
    @staticmethod
    def on_completion() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: ApplicationCall transaction on completion action
        """
    @staticmethod
    def application_args(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the current transaction

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: txnas F

        :returns Bytes: Arguments passed to the application in the ApplicationCall transaction
        """
    @staticmethod
    def num_app_args() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of ApplicationArgs
        """
    @staticmethod
    def accounts(a: UInt64 | int, /) -> Account:
        """
        Ath value of the array field F of the current transaction

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: txnas F

        :returns Account: Accounts listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_accounts() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of Accounts
        """
    @staticmethod
    def approval_program() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: Approval program
        """
    @staticmethod
    def clear_state_program() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: Clear state program
        """
    @staticmethod
    def rekey_to() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte Sender's new AuthAddr
        """
    @staticmethod
    def config_asset() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Asset ID in asset config transaction
        """
    @staticmethod
    def config_asset_total() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Total number of units of this asset created
        """
    @staticmethod
    def config_asset_decimals() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of digits to display after the decimal place when displaying the asset
        """
    @staticmethod
    def config_asset_default_frozen() -> bool:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns bool: Whether the asset's slots are frozen by default or not, 0 or 1
        """
    @staticmethod
    def config_asset_unit_name() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: Unit name of the asset
        """
    @staticmethod
    def config_asset_name() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: The asset name
        """
    @staticmethod
    def config_asset_url() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: URL
        """
    @staticmethod
    def config_asset_metadata_hash() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte commitment to unspecified asset metadata
        """
    @staticmethod
    def config_asset_manager() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_reserve() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_freeze() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_clawback() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address
        """
    @staticmethod
    def freeze_asset() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Asset ID being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_account() -> Account:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Account: 32 byte address of the account whose asset slot is being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_frozen() -> bool:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns bool: The new frozen value, 0 or 1
        """
    @staticmethod
    def assets(a: UInt64 | int, /) -> UInt64:
        """
        Ath value of the array field F of the current transaction

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: txnas F

        :returns UInt64: Foreign Assets listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_assets() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of Assets
        """
    @staticmethod
    def applications(a: UInt64 | int, /) -> UInt64:
        """
        Ath value of the array field F of the current transaction

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: txnas F

        :returns UInt64: Foreign Apps listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_applications() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of Applications
        """
    @staticmethod
    def global_num_uint() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of global state integers in ApplicationCall
        """
    @staticmethod
    def global_num_byte_slice() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of global state byteslices in ApplicationCall
        """
    @staticmethod
    def local_num_uint() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of local state integers in ApplicationCall
        """
    @staticmethod
    def local_num_byte_slice() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of local state byteslices in ApplicationCall
        """
    @staticmethod
    def extra_program_pages() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.
        """
    @staticmethod
    def nonparticipation() -> bool:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns bool: Marks an account nonparticipating for rewards
        """
    @staticmethod
    def logs(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the current transaction

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: txnas F

        :returns Bytes: Log messages emitted by an application call (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def num_logs() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of Logs (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_asset_id() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_application_id() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def last_log() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: The last message emitted. Empty bytes if none were emitted. Application mode only
        """
    @staticmethod
    def state_proof_pk() -> Bytes:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns Bytes: 64 byte state proof public key
        """
    @staticmethod
    def approval_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the current transaction

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: txnas F

        :returns Bytes: Approval Program as an array of pages
        """
    @staticmethod
    def num_approval_program_pages() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of Approval Program pages
        """
    @staticmethod
    def clear_state_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        Ath value of the array field F of the current transaction

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: txnas F

        :returns Bytes: ClearState Program as an array of pages
        """
    @staticmethod
    def num_clear_state_program_pages() -> UInt64:
        """
        field F of current transaction

        Groups: Loading Values

        Stack: [...] -> [..., X]
        TEAL: txn F

        :returns UInt64: Number of ClearState Program pages
        """

class TransactionGroup:
    @staticmethod
    def sender(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def fee(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: microalgos
        """
    @staticmethod
    def first_valid(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: round number
        """
    @staticmethod
    def first_valid_time(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: UNIX timestamp of block before txn.FirstValid. Fails if negative
        """
    @staticmethod
    def last_valid(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: round number
        """
    @staticmethod
    def note(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: Any data up to 1024 bytes
        """
    @staticmethod
    def lease(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte lease value
        """
    @staticmethod
    def receiver(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def amount(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: microalgos
        """
    @staticmethod
    def close_remainder_to(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_pk(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def selection_pk(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def vote_first(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: The first round that the participation key is valid.
        """
    @staticmethod
    def vote_last(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: The last round that the participation key is valid.
        """
    @staticmethod
    def vote_key_dilution(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Dilution for the 2-level participation key
        """
    @staticmethod
    def type(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: Transaction type as bytes
        """
    @staticmethod
    def type_enum(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Transaction type as integer
        """
    @staticmethod
    def xfer_asset(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Asset ID
        """
    @staticmethod
    def asset_amount(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: value in Asset's units
        """
    @staticmethod
    def asset_sender(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address. Source of assets if Sender is the Asset's Clawback address.
        """
    @staticmethod
    def asset_receiver(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def asset_close_to(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def group_index(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1
        """
    @staticmethod
    def tx_id(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: The computed ID for this transaction. 32 bytes.
        """
    @staticmethod
    def application_id(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: ApplicationID from ApplicationCall transaction
        """
    @staticmethod
    def on_completion(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: ApplicationCall transaction on completion action
        """
    @staticmethod
    def application_args(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        Bth value of the array field F from the Ath transaction in the current group

        Groups: Loading Values

        Stack: [..., A, B] -> [..., X]
        TEAL: gtxnsas F

        :returns Bytes: Arguments passed to the application in the ApplicationCall transaction
        """
    @staticmethod
    def num_app_args(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of ApplicationArgs
        """
    @staticmethod
    def accounts(a: UInt64 | int, b: UInt64 | int, /) -> Account:
        """
        Bth value of the array field F from the Ath transaction in the current group

        Groups: Loading Values

        Stack: [..., A, B] -> [..., X]
        TEAL: gtxnsas F

        :returns Account: Accounts listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_accounts(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of Accounts
        """
    @staticmethod
    def approval_program(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: Approval program
        """
    @staticmethod
    def clear_state_program(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: Clear state program
        """
    @staticmethod
    def rekey_to(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte Sender's new AuthAddr
        """
    @staticmethod
    def config_asset(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Asset ID in asset config transaction
        """
    @staticmethod
    def config_asset_total(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Total number of units of this asset created
        """
    @staticmethod
    def config_asset_decimals(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of digits to display after the decimal place when displaying the asset
        """
    @staticmethod
    def config_asset_default_frozen(a: UInt64 | int, /) -> bool:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns bool: Whether the asset's slots are frozen by default or not, 0 or 1
        """
    @staticmethod
    def config_asset_unit_name(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: Unit name of the asset
        """
    @staticmethod
    def config_asset_name(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: The asset name
        """
    @staticmethod
    def config_asset_url(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: URL
        """
    @staticmethod
    def config_asset_metadata_hash(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte commitment to unspecified asset metadata
        """
    @staticmethod
    def config_asset_manager(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_reserve(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_freeze(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def config_asset_clawback(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address
        """
    @staticmethod
    def freeze_asset(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Asset ID being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_account(a: UInt64 | int, /) -> Account:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Account: 32 byte address of the account whose asset slot is being frozen or un-frozen
        """
    @staticmethod
    def freeze_asset_frozen(a: UInt64 | int, /) -> bool:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns bool: The new frozen value, 0 or 1
        """
    @staticmethod
    def assets(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
        """
        Bth value of the array field F from the Ath transaction in the current group

        Groups: Loading Values

        Stack: [..., A, B] -> [..., X]
        TEAL: gtxnsas F

        :returns UInt64: Foreign Assets listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_assets(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of Assets
        """
    @staticmethod
    def applications(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
        """
        Bth value of the array field F from the Ath transaction in the current group

        Groups: Loading Values

        Stack: [..., A, B] -> [..., X]
        TEAL: gtxnsas F

        :returns UInt64: Foreign Apps listed in the ApplicationCall transaction
        """
    @staticmethod
    def num_applications(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of Applications
        """
    @staticmethod
    def global_num_uint(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of global state integers in ApplicationCall
        """
    @staticmethod
    def global_num_byte_slice(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of global state byteslices in ApplicationCall
        """
    @staticmethod
    def local_num_uint(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of local state integers in ApplicationCall
        """
    @staticmethod
    def local_num_byte_slice(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of local state byteslices in ApplicationCall
        """
    @staticmethod
    def extra_program_pages(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.
        """
    @staticmethod
    def nonparticipation(a: UInt64 | int, /) -> bool:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns bool: Marks an account nonparticipating for rewards
        """
    @staticmethod
    def logs(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        Bth value of the array field F from the Ath transaction in the current group

        Groups: Loading Values

        Stack: [..., A, B] -> [..., X]
        TEAL: gtxnsas F

        :returns Bytes: Log messages emitted by an application call (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def num_logs(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of Logs (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_asset_id(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def created_application_id(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only
        """
    @staticmethod
    def last_log(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: The last message emitted. Empty bytes if none were emitted. Application mode only
        """
    @staticmethod
    def state_proof_pk(a: UInt64 | int, /) -> Bytes:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns Bytes: 64 byte state proof public key
        """
    @staticmethod
    def approval_program_pages(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        Bth value of the array field F from the Ath transaction in the current group

        Groups: Loading Values

        Stack: [..., A, B] -> [..., X]
        TEAL: gtxnsas F

        :returns Bytes: Approval Program as an array of pages
        """
    @staticmethod
    def num_approval_program_pages(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of Approval Program pages
        """
    @staticmethod
    def clear_state_program_pages(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        Bth value of the array field F from the Ath transaction in the current group

        Groups: Loading Values

        Stack: [..., A, B] -> [..., X]
        TEAL: gtxnsas F

        :returns Bytes: ClearState Program as an array of pages
        """
    @staticmethod
    def num_clear_state_program_pages(a: UInt64 | int, /) -> UInt64:
        """
        field F of the Ath transaction in the current group
        for notes on transaction fields available, see `txn`. If top of stack is _i_, `gtxns field` is equivalent to `gtxn _i_ field`. gtxns exists so that _i_ can be calculated, often based on the index of the current transaction.

        Groups: Loading Values

        Stack: [..., A] -> [..., X]
        TEAL: gtxns F

        :returns UInt64: Number of ClearState Program pages
        """
