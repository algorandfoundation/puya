import typing

from algopy import (
    Account,
    Application,
    Asset,
    BigUInt,
    Bytes,
    OnCompleteAction,
    TransactionType,
    UInt64,
)

class EC(str):
    """Available values for the `EC` enum"""

    BN254g1: EC = ...
    """
    G1 of the BN254 curve. Points encoded as 32 byte X following by 32 byte Y
    """
    BN254g2: EC = ...
    """
    G2 of the BN254 curve. Points encoded as 64 byte X following by 64 byte Y
    """
    BLS12_381g1: EC = ...
    """
    G1 of the BLS 12-381 curve. Points encoded as 48 byte X following by 48 byte Y
    """
    BLS12_381g2: EC = ...
    """
    G2 of the BLS 12-381 curve. Points encoded as 96 byte X following by 96 byte Y
    """

class Base64(str):
    """Available values for the `base64` enum"""

    URLEncoding: Base64 = ...
    StdEncoding: Base64 = ...

class ECDSA(str):
    """Available values for the `ECDSA` enum"""

    Secp256k1: ECDSA = ...
    """
    secp256k1 curve, used in Bitcoin
    """
    Secp256r1: ECDSA = ...
    """
    secp256r1 curve, NIST standard
    """

class MiMCConfigurations(str):
    """Available values for the `Mimc Configurations` enum"""

    BN254Mp110: MiMCConfigurations = ...
    """
    MiMC configuration for the BN254 curve with Miyaguchi-Preneel mode, 110 rounds, exponent 5, seed "seed"
    Min AVM version: 11
    """
    BLS12_381Mp111: MiMCConfigurations = ...
    """
    MiMC configuration for the BLS12-381 curve with Miyaguchi-Preneel mode, 111 rounds, exponent 5, seed "seed"
    Min AVM version: 11
    """

class VrfVerify(str):
    """Available values for the `vrf_verify` enum"""

    VrfAlgorand: VrfVerify = ...

def addw(a: UInt64 | int, b: UInt64 | int, /) -> tuple[UInt64, UInt64]:
    """
    A plus B as a 128-bit result. X is the carry-bit, Y is the low-order 64 bits.

    Native TEAL opcode: [`addw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#addw)
    """

def app_opted_in(a: Account | UInt64 | int, b: Application | UInt64 | int, /) -> bool:
    """
    1 if account A is opted in to application B, else 0
    params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset). Return: 1 if opted in and 0 otherwise.

    Native TEAL opcode: [`app_opted_in`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_opted_in)
    """

def arg(a: UInt64 | int, /) -> Bytes:
    """
    Ath LogicSig argument

    Native TEAL opcode: [`arg`](https://dev.algorand.co/reference/algorand-teal/opcodes/#arg), [`args`](https://dev.algorand.co/reference/algorand-teal/opcodes/#args)
    """

def balance(a: Account | UInt64 | int, /) -> UInt64:
    """
    balance for account A, in microalgos. The balance is observed after the effects of previous transactions in the group, and after the fee for the current transaction is deducted. Changes caused by inner transactions are observable immediately following `itxn_submit`
    params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset). Return: value.

    Native TEAL opcode: [`balance`](https://dev.algorand.co/reference/algorand-teal/opcodes/#balance)
    """

def base64_decode(e: Base64, a: Bytes | bytes, /) -> Bytes:
    """
    decode A which was base64-encoded using _encoding_ E. Fail if A is not base64 encoded with encoding E
    *Warning*: Usage should be restricted to very rare use cases. In almost all cases, smart contracts should directly handle non-encoded byte-strings.	This opcode should only be used in cases where base64 is the only available option, e.g. interoperability with a third-party that only signs base64 strings.

     Decodes A using the base64 encoding E. Specify the encoding with an immediate arg either as URL and Filename Safe (`URLEncoding`) or Standard (`StdEncoding`). See [RFC 4648 sections 4 and 5](https://rfc-editor.org/rfc/rfc4648.html#section-4). It is assumed that the encoding ends with the exact number of `=` padding characters as required by the RFC. When padding occurs, any unused pad bits in the encoding must be set to zero or the decoding will fail. The special cases of `\\n` and `\\r` are allowed but completely ignored. An error will result when attempting to decode a string with a character that is not in the encoding alphabet or not one of `=`, `\\r`, or `\\n`.
    :param Base64 e: encoding index

    Native TEAL opcode: [`base64_decode`](https://dev.algorand.co/reference/algorand-teal/opcodes/#base64_decode)
    """

def bitlen(a: Bytes | UInt64 | bytes | int, /) -> UInt64:
    """
    The highest set bit in A. If A is a byte-array, it is interpreted as a big-endian unsigned integer. bitlen of 0 is 0, bitlen of 8 is 4
    bitlen interprets arrays as big-endian integers, unlike setbit/getbit

    Native TEAL opcode: [`bitlen`](https://dev.algorand.co/reference/algorand-teal/opcodes/#bitlen)
    """

def bsqrt(a: BigUInt | int, /) -> BigUInt:
    """
    The largest integer I such that I^2 <= A. A and I are interpreted as big-endian unsigned integers

    Native TEAL opcode: [`bsqrt`](https://dev.algorand.co/reference/algorand-teal/opcodes/#bsqrt)
    """

def btoi(a: Bytes | bytes, /) -> UInt64:
    """
    converts big-endian byte array A to uint64. Fails if len(A) > 8. Padded by leading 0s if len(A) < 8.
    `btoi` fails if the input is longer than 8 bytes.

    Native TEAL opcode: [`btoi`](https://dev.algorand.co/reference/algorand-teal/opcodes/#btoi)
    """

def bzero(a: UInt64 | int, /) -> Bytes:
    """
    zero filled byte-array of length A

    Native TEAL opcode: [`bzero`](https://dev.algorand.co/reference/algorand-teal/opcodes/#bzero)
    """

def concat(a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
    """
    join A and B
    `concat` fails if the result would be greater than 4096 bytes.

    Native TEAL opcode: [`concat`](https://dev.algorand.co/reference/algorand-teal/opcodes/#concat)
    """

def divmodw(
    a: UInt64 | int, b: UInt64 | int, c: UInt64 | int, d: UInt64 | int, /
) -> tuple[UInt64, UInt64, UInt64, UInt64]:
    """
    W,X = (A,B / C,D); Y,Z = (A,B modulo C,D)
    The notation J,K indicates that two uint64 values J and K are interpreted as a uint128 value, with J as the high uint64 and K the low.

    Native TEAL opcode: [`divmodw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#divmodw)
    """

def divw(a: UInt64 | int, b: UInt64 | int, c: UInt64 | int, /) -> UInt64:
    """
    A,B / C. Fail if C == 0 or if result overflows.
    The notation A,B indicates that A and B are interpreted as a uint128 value, with A as the high uint64 and B the low.

    Native TEAL opcode: [`divw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#divw)
    """

def ecdsa_pk_decompress(v: ECDSA, a: Bytes | bytes, /) -> tuple[Bytes, Bytes]:
    """
    decompress pubkey A into components X, Y
    The 33 byte public key in a compressed form to be decompressed into X and Y (top) components. All values are big-endian encoded.
    :param ECDSA v: curve index

    Native TEAL opcode: [`ecdsa_pk_decompress`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ecdsa_pk_decompress)
    """

def ecdsa_pk_recover(
    v: ECDSA, a: Bytes | bytes, b: UInt64 | int, c: Bytes | bytes, d: Bytes | bytes, /
) -> tuple[Bytes, Bytes]:
    """
    for (data A, recovery id B, signature C, D) recover a public key
    S (top) and R elements of a signature, recovery id and data (bottom) are expected on the stack and used to deriver a public key. All values are big-endian encoded. The signed data must be 32 bytes long.
    :param ECDSA v: curve index

    Native TEAL opcode: [`ecdsa_pk_recover`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ecdsa_pk_recover)
    """

def ecdsa_verify(
    v: ECDSA,
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
    :param ECDSA v: curve index

    Native TEAL opcode: [`ecdsa_verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ecdsa_verify)
    """

def ed25519verify(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    """
    for (data A, signature B, pubkey C) verify the signature of ("ProgData" || program_hash || data) against the pubkey => {0 or 1}
    The 32 byte public key is the last element on the stack, preceded by the 64 byte signature at the second-to-last element on the stack, preceded by the data which was signed at the third-to-last element on the stack.

    Native TEAL opcode: [`ed25519verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ed25519verify)
    """

def ed25519verify_bare(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    """
    for (data A, signature B, pubkey C) verify the signature of the data against the pubkey => {0 or 1}

    Native TEAL opcode: [`ed25519verify_bare`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ed25519verify_bare)
    """

def err() -> typing.Never:
    """
    Fail immediately.
    :returns typing.Never: Halts program

    Native TEAL opcode: [`err`](https://dev.algorand.co/reference/algorand-teal/opcodes/#err)
    """

def exit(a: UInt64 | int, /) -> typing.Never:
    """
    use A as success value; end
    :returns typing.Never: Halts program

    Native TEAL opcode: [`return`](https://dev.algorand.co/reference/algorand-teal/opcodes/#return)
    """

def exp(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    A raised to the Bth power. Fail if A == B == 0 and on overflow

    Native TEAL opcode: [`exp`](https://dev.algorand.co/reference/algorand-teal/opcodes/#exp)
    """

def expw(a: UInt64 | int, b: UInt64 | int, /) -> tuple[UInt64, UInt64]:
    """
    A raised to the Bth power as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low. Fail if A == B == 0 or if the results exceeds 2^128-1

    Native TEAL opcode: [`expw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#expw)
    """

def extract(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    A range of bytes from A starting at B up to but not including B+C. If B+C is larger than the array length, the program fails
    `extract3` can be called using `extract` with no immediates.

    Native TEAL opcode: [`extract`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract), [`extract3`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract3)
    """

def extract_uint16(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    A uint16 formed from a range of big-endian bytes from A starting at B up to but not including B+2. If B+2 is larger than the array length, the program fails

    Native TEAL opcode: [`extract_uint16`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract_uint16)
    """

def extract_uint32(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    A uint32 formed from a range of big-endian bytes from A starting at B up to but not including B+4. If B+4 is larger than the array length, the program fails

    Native TEAL opcode: [`extract_uint32`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract_uint32)
    """

def extract_uint64(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    A uint64 formed from a range of big-endian bytes from A starting at B up to but not including B+8. If B+8 is larger than the array length, the program fails

    Native TEAL opcode: [`extract_uint64`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract_uint64)
    """

def falcon_verify(a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /) -> bool:
    """
    for (data A, compressed-format signature B, pubkey C) verify the signature of data against the pubkey
    Min AVM version: 12

    Native TEAL opcode: [`falcon_verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#falcon_verify)
    """

def gaid(a: UInt64 | int, /) -> UInt64:
    """
    ID of the asset or application created in the Ath transaction of the current group
    `gaids` fails unless the requested transaction created an asset or application and A < GroupIndex.

    Native TEAL opcode: [`gaid`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gaid), [`gaids`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gaids)
    """

def getbit(a: Bytes | UInt64 | bytes | int, b: UInt64 | int, /) -> UInt64:
    """
    Bth bit of (byte-array or integer) A. If B is greater than or equal to the bit length of the value (8*byte length), the program fails
    see explanation of bit ordering in setbit

    Native TEAL opcode: [`getbit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#getbit)
    """

def getbyte(a: Bytes | bytes, b: UInt64 | int, /) -> UInt64:
    """
    Bth byte of A, as an integer. If B is greater than or equal to the array length, the program fails

    Native TEAL opcode: [`getbyte`](https://dev.algorand.co/reference/algorand-teal/opcodes/#getbyte)
    """

def gload_bytes(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
    """
    Bth scratch space value of the Ath transaction in the current group

    Native TEAL opcode: [`gload`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gload), [`gloads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloads), [`gloadss`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloadss)
    """

def gload_uint64(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    Bth scratch space value of the Ath transaction in the current group

    Native TEAL opcode: [`gload`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gload), [`gloads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloads), [`gloadss`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloadss)
    """

def itob(a: UInt64 | int, /) -> Bytes:
    """
    converts uint64 A to big-endian byte array, always of length 8

    Native TEAL opcode: [`itob`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itob)
    """

def keccak256(a: Bytes | bytes, /) -> Bytes:
    """
    Keccak256 hash of value A, yields [32]byte

    Native TEAL opcode: [`keccak256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#keccak256)
    """

def mimc(c: MiMCConfigurations, a: Bytes | bytes, /) -> Bytes:
    """
    MiMC hash of scalars A, using curve and parameters specified by configuration C
    A is a list of concatenated 32 byte big-endian unsigned integer scalars.  Fail if A's length is not a multiple of 32 or any element exceeds the curve modulus.

    The MiMC hash function has known collisions since any input which is a multiple of the elliptic curve modulus will hash to the same value. MiMC is thus not a general purpose hash function, but meant to be used in zero knowledge applications to match a zk-circuit implementation.
    Min AVM version: 11
    :param MiMCConfigurations c: configuration index

    Native TEAL opcode: [`mimc`](https://dev.algorand.co/reference/algorand-teal/opcodes/#mimc)
    """

def min_balance(a: Account | UInt64 | int, /) -> UInt64:
    """
    minimum required balance for account A, in microalgos. Required balance is affected by ASA, App, and Box usage. When creating or opting into an app, the minimum balance grows before the app code runs, therefore the increase is visible there. When deleting or closing out, the minimum balance decreases after the app executes. Changes caused by inner transactions or box usage are observable immediately following the opcode effecting the change.
    params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset). Return: value.

    Native TEAL opcode: [`min_balance`](https://dev.algorand.co/reference/algorand-teal/opcodes/#min_balance)
    """

def mulw(a: UInt64 | int, b: UInt64 | int, /) -> tuple[UInt64, UInt64]:
    """
    A times B as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low

    Native TEAL opcode: [`mulw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#mulw)
    """

def online_stake() -> UInt64:
    """
    the total online stake in the agreement round
    Min AVM version: 11

    Native TEAL opcode: [`online_stake`](https://dev.algorand.co/reference/algorand-teal/opcodes/#online_stake)
    """

def replace(a: Bytes | bytes, b: UInt64 | int, c: Bytes | bytes, /) -> Bytes:
    """
    Copy of A with the bytes starting at B replaced by the bytes of C. Fails if B+len(C) exceeds len(A)
    `replace3` can be called using `replace` with no immediates.

    Native TEAL opcode: [`replace2`](https://dev.algorand.co/reference/algorand-teal/opcodes/#replace2), [`replace3`](https://dev.algorand.co/reference/algorand-teal/opcodes/#replace3)
    """

def select_bytes(a: Bytes | bytes, b: Bytes | bytes, c: bool | UInt64 | int, /) -> Bytes:
    """
    selects one of two values based on top-of-stack: B if C != 0, else A

    Native TEAL opcode: [`select`](https://dev.algorand.co/reference/algorand-teal/opcodes/#select)
    """

def select_uint64(a: UInt64 | int, b: UInt64 | int, c: bool | UInt64 | int, /) -> UInt64:
    """
    selects one of two values based on top-of-stack: B if C != 0, else A

    Native TEAL opcode: [`select`](https://dev.algorand.co/reference/algorand-teal/opcodes/#select)
    """

def setbit_bytes(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8*byte length), the program fails
    When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.

    Native TEAL opcode: [`setbit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#setbit)
    """

def setbit_uint64(a: UInt64 | int, b: UInt64 | int, c: UInt64 | int, /) -> UInt64:
    """
    Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8*byte length), the program fails
    When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.

    Native TEAL opcode: [`setbit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#setbit)
    """

def setbyte(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    Copy of A with the Bth byte set to small integer (between 0..255) C. If B is greater than or equal to the array length, the program fails

    Native TEAL opcode: [`setbyte`](https://dev.algorand.co/reference/algorand-teal/opcodes/#setbyte)
    """

def sha256(a: Bytes | bytes, /) -> Bytes:
    """
    SHA256 hash of value A, yields [32]byte

    Native TEAL opcode: [`sha256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sha256)
    """

def sha3_256(a: Bytes | bytes, /) -> Bytes:
    """
    SHA3_256 hash of value A, yields [32]byte

    Native TEAL opcode: [`sha3_256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sha3_256)
    """

def sha512_256(a: Bytes | bytes, /) -> Bytes:
    """
    SHA512_256 hash of value A, yields [32]byte

    Native TEAL opcode: [`sha512_256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sha512_256)
    """

def shl(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    A times 2^B, modulo 2^64

    Native TEAL opcode: [`shl`](https://dev.algorand.co/reference/algorand-teal/opcodes/#shl)
    """

def shr(a: UInt64 | int, b: UInt64 | int, /) -> UInt64:
    """
    A divided by 2^B

    Native TEAL opcode: [`shr`](https://dev.algorand.co/reference/algorand-teal/opcodes/#shr)
    """

def sqrt(a: UInt64 | int, /) -> UInt64:
    """
    The largest integer I such that I^2 <= A

    Native TEAL opcode: [`sqrt`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sqrt)
    """

def substring(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
    """
    A range of bytes from A starting at B up to but not including C. If C < B, or either is larger than the array length, the program fails

    Native TEAL opcode: [`substring`](https://dev.algorand.co/reference/algorand-teal/opcodes/#substring), [`substring3`](https://dev.algorand.co/reference/algorand-teal/opcodes/#substring3)
    """

def sumhash512(a: Bytes | bytes, /) -> Bytes:
    """
    sumhash512 of value A, yields [64]byte
    Min AVM version: 12

    Native TEAL opcode: [`sumhash512`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sumhash512)
    """

def vrf_verify(
    s: VrfVerify, a: Bytes | bytes, b: Bytes | bytes, c: Bytes | bytes, /
) -> tuple[Bytes, bool]:
    """
    Verify the proof B of message A against pubkey C. Returns vrf output and verification flag.
    `VrfAlgorand` is the VRF used in Algorand. It is ECVRF-ED25519-SHA512-Elligator2, specified in the IETF internet draft [draft-irtf-cfrg-vrf-03](https://datatracker.ietf.org/doc/draft-irtf-cfrg-vrf/03/).
    :param VrfVerify s:  parameters index

    Native TEAL opcode: [`vrf_verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#vrf_verify)
    """

class AcctParamsGet:
    """
    X is field F from account A. Y is 1 if A owns positive algos, else 0
    Native TEAL op: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
    """
    @staticmethod
    def acct_balance(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Account balance in microalgos

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_min_balance(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Minimum required balance for account, in microalgos

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_auth_addr(a: Account | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Address the account is rekeyed to.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_num_uint(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The total number of uint64 values allocated by this account in Global and Local States.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_num_byte_slice(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The total number of byte array values allocated by this account in Global and Local States.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_extra_app_pages(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The number of extra app code pages used by this account.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_apps_created(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The number of existing apps created by this account.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_apps_opted_in(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The number of apps this account is opted into.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_assets_created(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The number of existing ASAs created by this account.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_assets(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The numbers of ASAs held by this account (including ASAs this account created).

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_boxes(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The number of existing boxes created by this account's app.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_total_box_bytes(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        The total number of bytes used by this account's app's box keys and values.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_incentive_eligible(a: Account | UInt64 | int, /) -> tuple[bool, bool]:
        """
        Min AVM version: 11
        :returns tuple[bool, bool]: Has this account opted into block payouts

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_last_proposed(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Min AVM version: 11
        :returns tuple[UInt64, bool]: The round number of the last block this account proposed.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

    @staticmethod
    def acct_last_heartbeat(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Min AVM version: 11
        :returns tuple[UInt64, bool]: The round number of the last block this account sent a heartbeat.

        Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)
        """

class AppGlobal:
    """
    Get or modify Global app state
    Native TEAL ops: [`app_global_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_del), [`app_global_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get), [`app_global_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get_ex), [`app_global_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_put)
    """
    @staticmethod
    def get_bytes(a: Bytes | bytes, /) -> Bytes:
        """
        global state of the key A in the current application
        params: state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_global_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get)
        """

    @staticmethod
    def get_uint64(a: Bytes | bytes, /) -> UInt64:
        """
        global state of the key A in the current application
        params: state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_global_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get)
        """

    @staticmethod
    def get_ex_bytes(a: Application | UInt64 | int, b: Bytes | bytes, /) -> tuple[Bytes, bool]:
        """
        X is the global state of application A, key B. Y is 1 if key existed, else 0
        params: Txn.ForeignApps offset (or, since v4, an _available_ application id), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_global_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get_ex)
        """

    @staticmethod
    def get_ex_uint64(a: Application | UInt64 | int, b: Bytes | bytes, /) -> tuple[UInt64, bool]:
        """
        X is the global state of application A, key B. Y is 1 if key existed, else 0
        params: Txn.ForeignApps offset (or, since v4, an _available_ application id), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_global_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get_ex)
        """

    @staticmethod
    def delete(a: Bytes | bytes, /) -> None:
        """
        delete key A from the global state of the current application
        params: state key.

        Deleting a key which is already absent has no effect on the application global state. (In particular, it does _not_ cause the program to fail.)

        Native TEAL opcode: [`app_global_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_del)
        """

    @staticmethod
    def put(a: Bytes | bytes, b: Bytes | UInt64 | bytes | int, /) -> None:
        """
        write B to key A in the global state of the current application

        Native TEAL opcode: [`app_global_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_put)
        """

class AppLocal:
    """
    Get or modify Local app state
    Native TEAL ops: [`app_local_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_del), [`app_local_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get), [`app_local_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get_ex), [`app_local_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_put)
    """
    @staticmethod
    def get_bytes(a: Account | UInt64 | int, b: Bytes | bytes, /) -> Bytes:
        """
        local state of the key B in the current application in account A
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_local_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get)
        """

    @staticmethod
    def get_uint64(a: Account | UInt64 | int, b: Bytes | bytes, /) -> UInt64:
        """
        local state of the key B in the current application in account A
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key. Return: value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_local_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get)
        """

    @staticmethod
    def get_ex_bytes(
        a: Account | UInt64 | int, b: Application | UInt64 | int, c: Bytes | bytes, /
    ) -> tuple[Bytes, bool]:
        """
        X is the local state of application B, key C in account A. Y is 1 if key existed, else 0
        params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_local_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get_ex)
        """

    @staticmethod
    def get_ex_uint64(
        a: Account | UInt64 | int, b: Application | UInt64 | int, c: Bytes | bytes, /
    ) -> tuple[UInt64, bool]:
        """
        X is the local state of application B, key C in account A. Y is 1 if key existed, else 0
        params: Txn.Accounts offset (or, since v4, an _available_ account address), _available_ application id (or, since v4, a Txn.ForeignApps offset), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

        Native TEAL opcode: [`app_local_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get_ex)
        """

    @staticmethod
    def delete(a: Account | UInt64 | int, b: Bytes | bytes, /) -> None:
        """
        delete key B from account A's local state of the current application
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key.

        Deleting a key which is already absent has no effect on the application local state. (In particular, it does _not_ cause the program to fail.)

        Native TEAL opcode: [`app_local_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_del)
        """

    @staticmethod
    def put(
        a: Account | UInt64 | int, b: Bytes | bytes, c: Bytes | UInt64 | bytes | int, /
    ) -> None:
        """
        write C to key B in account A's local state of the current application
        params: Txn.Accounts offset (or, since v4, an _available_ account address), state key, value.

        Native TEAL opcode: [`app_local_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_put)
        """

class AppParamsGet:
    """
    X is field F from app A. Y is 1 if A exists, else 0 params: Txn.ForeignApps offset or an _available_ app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.
    Native TEAL op: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
    """
    @staticmethod
    def app_approval_program(a: Application | UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        Bytecode of Approval Program

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_clear_state_program(a: Application | UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        Bytecode of Clear State Program

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_global_num_uint(a: Application | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Number of uint64 values allowed in Global State

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_global_num_byte_slice(a: Application | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Number of byte array values allowed in Global State

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_local_num_uint(a: Application | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Number of uint64 values allowed in Local State

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_local_num_byte_slice(a: Application | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Number of byte array values allowed in Local State

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_extra_program_pages(a: Application | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Number of Extra Program Pages of code space

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_creator(a: Application | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Creator address

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

    @staticmethod
    def app_address(a: Application | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Address for which this application has authority

        Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)
        """

class AssetHoldingGet:
    """
    X is field F from account A's holding of asset B. Y is 1 if A is opted into B, else 0 params: Txn.Accounts offset (or, since v4, an _available_ address), asset id (or, since v4, a Txn.ForeignAssets offset). Return: did_exist flag (1 if the asset existed and 0 otherwise), value.
    Native TEAL op: [`asset_holding_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_holding_get)
    """
    @staticmethod
    def asset_balance(
        a: Account | UInt64 | int, b: Asset | UInt64 | int, /
    ) -> tuple[UInt64, bool]:
        """
        Amount of the asset unit held by this account

        Native TEAL opcode: [`asset_holding_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_holding_get)
        """

    @staticmethod
    def asset_frozen(a: Account | UInt64 | int, b: Asset | UInt64 | int, /) -> tuple[bool, bool]:
        """
        Is the asset frozen or not

        Native TEAL opcode: [`asset_holding_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_holding_get)
        """

class AssetParamsGet:
    """
    X is field F from asset A. Y is 1 if A exists, else 0 params: Txn.ForeignAssets offset (or, since v4, an _available_ asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.
    Native TEAL op: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
    """
    @staticmethod
    def asset_total(a: Asset | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Total number of units of this asset

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_decimals(a: Asset | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        See AssetParams.Decimals

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_default_frozen(a: Asset | UInt64 | int, /) -> tuple[bool, bool]:
        """
        Frozen by default or not

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_unit_name(a: Asset | UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        Asset unit name

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_name(a: Asset | UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        Asset name

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_url(a: Asset | UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        URL with additional info about the asset

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_metadata_hash(a: Asset | UInt64 | int, /) -> tuple[Bytes, bool]:
        """
        Arbitrary commitment

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_manager(a: Asset | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Manager address

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_reserve(a: Asset | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Reserve address

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_freeze(a: Asset | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Freeze address

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_clawback(a: Asset | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Clawback address

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

    @staticmethod
    def asset_creator(a: Asset | UInt64 | int, /) -> tuple[Account, bool]:
        """
        Creator address

        Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)
        """

class Block:
    """
    field F of block A. Fail unless A falls between txn.LastValid-1002 and txn.FirstValid (exclusive)
    Native TEAL op: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
    """
    @staticmethod
    def blk_seed(a: UInt64 | int, /) -> Bytes:
        """

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_timestamp(a: UInt64 | int, /) -> UInt64:
        """

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_proposer(a: UInt64 | int, /) -> Account:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_fees_collected(a: UInt64 | int, /) -> UInt64:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_bonus(a: UInt64 | int, /) -> UInt64:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_branch(a: UInt64 | int, /) -> Bytes:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_fee_sink(a: UInt64 | int, /) -> Account:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_protocol(a: UInt64 | int, /) -> Bytes:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_txn_counter(a: UInt64 | int, /) -> UInt64:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

    @staticmethod
    def blk_proposer_payout(a: UInt64 | int, /) -> UInt64:
        """
        Min AVM version: 11

        Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)
        """

class Box:
    """
    Get or modify box state
    Native TEAL ops: [`box_create`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_create), [`box_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_del), [`box_extract`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_extract), [`box_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_get), [`box_len`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_len), [`box_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_put), [`box_replace`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_replace), [`box_resize`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_resize), [`box_splice`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_splice)
    """
    @staticmethod
    def create(a: Bytes | bytes, b: UInt64 | int, /) -> bool:
        """
        create a box named A, of length B. Fail if the name A is empty or B exceeds 32,768. Returns 0 if A already existed, else 1
        Newly created boxes are filled with 0 bytes. `box_create` will fail if the referenced box already exists with a different size. Otherwise, existing boxes are unchanged by `box_create`.

        Native TEAL opcode: [`box_create`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_create)
        """

    @staticmethod
    def delete(a: Bytes | bytes, /) -> bool:
        """
        delete box named A if it exists. Return 1 if A existed, 0 otherwise

        Native TEAL opcode: [`box_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_del)
        """

    @staticmethod
    def extract(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, /) -> Bytes:
        """
        read C bytes from box A, starting at offset B. Fail if A does not exist, or the byte range is outside A's size.

        Native TEAL opcode: [`box_extract`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_extract)
        """

    @staticmethod
    def get(a: Bytes | bytes, /) -> tuple[Bytes, bool]:
        """
        X is the contents of box A if A exists, else ''. Y is 1 if A exists, else 0.
        For boxes that exceed 4,096 bytes, consider `box_create`, `box_extract`, and `box_replace`

        Native TEAL opcode: [`box_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_get)
        """

    @staticmethod
    def length(a: Bytes | bytes, /) -> tuple[UInt64, bool]:
        """
        X is the length of box A if A exists, else 0. Y is 1 if A exists, else 0.

        Native TEAL opcode: [`box_len`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_len)
        """

    @staticmethod
    def put(a: Bytes | bytes, b: Bytes | bytes, /) -> None:
        """
        replaces the contents of box A with byte-array B. Fails if A exists and len(B) != len(box A). Creates A if it does not exist
        For boxes that exceed 4,096 bytes, consider `box_create`, `box_extract`, and `box_replace`

        Native TEAL opcode: [`box_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_put)
        """

    @staticmethod
    def replace(a: Bytes | bytes, b: UInt64 | int, c: Bytes | bytes, /) -> None:
        """
        write byte-array C into box A, starting at offset B. Fail if A does not exist, or the byte range is outside A's size.

        Native TEAL opcode: [`box_replace`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_replace)
        """

    @staticmethod
    def resize(a: Bytes | bytes, b: UInt64 | int, /) -> None:
        """
        change the size of box named A to be of length B, adding zero bytes to end or removing bytes from the end, as needed. Fail if the name A is empty, A is not an existing box, or B exceeds 32,768.

        Native TEAL opcode: [`box_resize`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_resize)
        """

    @staticmethod
    def splice(a: Bytes | bytes, b: UInt64 | int, c: UInt64 | int, d: Bytes | bytes, /) -> None:
        """
        set box A to contain its previous bytes up to index B, followed by D, followed by the original bytes of A that began at index B+C.
        Boxes are of constant length. If C < len(D), then len(D)-C bytes will be removed from the end. If C > len(D), zero bytes will be appended to the end to reach the box length.

        Native TEAL opcode: [`box_splice`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_splice)
        """

class EllipticCurve:
    """
    Elliptic Curve functions
    Native TEAL ops: [`ec_add`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_add), [`ec_map_to`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_map_to), [`ec_multi_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_multi_scalar_mul), [`ec_pairing_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_pairing_check), [`ec_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_scalar_mul), [`ec_subgroup_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_subgroup_check)
    """
    @staticmethod
    def add(g: EC, a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
        """
        for curve points A and B, return the curve point A + B
        A and B are curve points in affine representation: field element X concatenated with field element Y. Field element `Z` is encoded as follows.
        For the base field elements (Fp), `Z` is encoded as a big-endian number and must be lower than the field modulus.
        For the quadratic field extension (Fp2), `Z` is encoded as the concatenation of the individual encoding of the coefficients. For an Fp2 element of the form `Z = Z0 + Z1 i`, where `i` is a formal quadratic non-residue, the encoding of Z is the concatenation of the encoding of `Z0` and `Z1` in this order. (`Z0` and `Z1` must be less than the field modulus).

        The point at infinity is encoded as `(X,Y) = (0,0)`.
        Groups G1 and G2 are denoted additively.

        Fails if A or B is not in G.
        A and/or B are allowed to be the point at infinity.
        Does _not_ check if A and B are in the main prime-order subgroup.
        :param EC g: curve index

        Native TEAL opcode: [`ec_add`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_add)
        """

    @staticmethod
    def map_to(g: EC, a: Bytes | bytes, /) -> Bytes:
        """
        maps field element A to group G
        BN254 points are mapped by the SVDW map. BLS12-381 points are mapped by the SSWU map.
        G1 element inputs are base field elements and G2 element inputs are quadratic field elements, with nearly the same encoding rules (for field elements) as defined in `ec_add`. There is one difference of encoding rule: G1 element inputs do not need to be 0-padded if they fit in less than 32 bytes for BN254 and less than 48 bytes for BLS12-381. (As usual, the empty byte array represents 0.) G2 elements inputs need to be always have the required size.
        :param EC g: curve index

        Native TEAL opcode: [`ec_map_to`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_map_to)
        """

    @staticmethod
    def scalar_mul_multi(g: EC, a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
        """
        for curve points A and scalars B, return curve point B0A0 + B1A1 + B2A2 + ... + BnAn
        A is a list of concatenated points, encoded and checked as described in `ec_add`. B is a list of concatenated scalars which, unlike ec_scalar_mul, must all be exactly 32 bytes long.
        The name `ec_multi_scalar_mul` was chosen to reflect common usage, but a more consistent name would be `ec_multi_scalar_mul`. AVM values are limited to 4096 bytes, so `ec_multi_scalar_mul` is limited by the size of the points in the group being operated upon.
        :param EC g: curve index

        Native TEAL opcode: [`ec_multi_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_multi_scalar_mul)
        """

    @staticmethod
    def pairing_check(g: EC, a: Bytes | bytes, b: Bytes | bytes, /) -> bool:
        """
        1 if the product of the pairing of each point in A with its respective point in B is equal to the identity element of the target group Gt, else 0
        A and B are concatenated points, encoded and checked as described in `ec_add`. A contains points of the group G, B contains points of the associated group (G2 if G is G1, and vice versa). Fails if A and B have a different number of points, or if any point is not in its described group or outside the main prime-order subgroup - a stronger condition than other opcodes. AVM values are limited to 4096 bytes, so `ec_pairing_check` is limited by the size of the points in the groups being operated upon.
        :param EC g: curve index

        Native TEAL opcode: [`ec_pairing_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_pairing_check)
        """

    @staticmethod
    def scalar_mul(g: EC, a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
        """
        for curve point A and scalar B, return the curve point BA, the point A multiplied by the scalar B.
        A is a curve point encoded and checked as described in `ec_add`. Scalar B is interpreted as a big-endian unsigned integer. Fails if B exceeds 32 bytes.
        :param EC g: curve index

        Native TEAL opcode: [`ec_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_scalar_mul)
        """

    @staticmethod
    def subgroup_check(g: EC, a: Bytes | bytes, /) -> bool:
        """
        1 if A is in the main prime-order subgroup of G (including the point at infinity) else 0. Program fails if A is not in G at all.
        :param EC g: curve index

        Native TEAL opcode: [`ec_subgroup_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_subgroup_check)
        """

class GITxn:
    """
    Get values for inner transaction in the last group submitted
    Native TEAL ops: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
    """
    @staticmethod
    def sender(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def fee(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: microalgos

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def first_valid(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: round number

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def first_valid_time(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: UNIX timestamp of block before txn.FirstValid. Fails if negative

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def last_valid(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: round number

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def note(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Any data up to 1024 bytes

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def lease(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: 32 byte lease value

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def receiver(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def amount(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: microalgos

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def close_remainder_to(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def vote_pk(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def selection_pk(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def vote_first(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: The first round that the participation key is valid.

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def vote_last(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: The last round that the participation key is valid.

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def vote_key_dilution(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Dilution for the 2-level participation key

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def type(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Transaction type as bytes

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def type_enum(t: int, /) -> TransactionType:
        """
        :param int t: transaction group index
        :returns TransactionType: Transaction type as integer

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def xfer_asset(t: int, /) -> Asset:
        """
        :param int t: transaction group index
        :returns Asset: Asset ID

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def asset_amount(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: value in Asset's units

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def asset_sender(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address. Source of assets if Sender is the Asset's Clawback address.

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def asset_receiver(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def asset_close_to(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def group_index(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def tx_id(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: The computed ID for this transaction. 32 bytes.

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def application_id(t: int, /) -> Application:
        """
        :param int t: transaction group index
        :returns Application: ApplicationID from ApplicationCall transaction

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def on_completion(t: int, /) -> OnCompleteAction:
        """
        :param int t: transaction group index
        :returns OnCompleteAction: ApplicationCall transaction on completion action

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def application_args(t: int, a: UInt64 | int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Arguments passed to the application in the ApplicationCall transaction

        Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
        """

    @staticmethod
    def num_app_args(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of ApplicationArgs

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def accounts(t: int, a: UInt64 | int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: Accounts listed in the ApplicationCall transaction

        Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
        """

    @staticmethod
    def num_accounts(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of Accounts

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def approval_program(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Approval program

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def clear_state_program(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Clear state program

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def rekey_to(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte Sender's new AuthAddr

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset(t: int, /) -> Asset:
        """
        :param int t: transaction group index
        :returns Asset: Asset ID in asset config transaction

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_total(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Total number of units of this asset created

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_decimals(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of digits to display after the decimal place when displaying the asset

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_default_frozen(t: int, /) -> bool:
        """
        :param int t: transaction group index
        :returns bool: Whether the asset's slots are frozen by default or not, 0 or 1

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_unit_name(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Unit name of the asset

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_name(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: The asset name

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_url(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: URL

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_metadata_hash(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: 32 byte commitment to unspecified asset metadata

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_manager(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_reserve(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_freeze(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def config_asset_clawback(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def freeze_asset(t: int, /) -> Asset:
        """
        :param int t: transaction group index
        :returns Asset: Asset ID being frozen or un-frozen

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def freeze_asset_account(t: int, /) -> Account:
        """
        :param int t: transaction group index
        :returns Account: 32 byte address of the account whose asset slot is being frozen or un-frozen

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def freeze_asset_frozen(t: int, /) -> bool:
        """
        :param int t: transaction group index
        :returns bool: The new frozen value, 0 or 1

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def assets(t: int, a: UInt64 | int, /) -> Asset:
        """
        :param int t: transaction group index
        :returns Asset: Foreign Assets listed in the ApplicationCall transaction

        Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
        """

    @staticmethod
    def num_assets(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of Assets

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def applications(t: int, a: UInt64 | int, /) -> Application:
        """
        :param int t: transaction group index
        :returns Application: Foreign Apps listed in the ApplicationCall transaction

        Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
        """

    @staticmethod
    def num_applications(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of Applications

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def global_num_uint(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of global state integers in ApplicationCall

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def global_num_byte_slice(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of global state byteslices in ApplicationCall

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def local_num_uint(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of local state integers in ApplicationCall

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def local_num_byte_slice(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of local state byteslices in ApplicationCall

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def extra_program_pages(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def nonparticipation(t: int, /) -> bool:
        """
        :param int t: transaction group index
        :returns bool: Marks an account nonparticipating for rewards

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def logs(t: int, a: UInt64 | int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Log messages emitted by an application call (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
        """

    @staticmethod
    def num_logs(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of Logs (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def created_asset_id(t: int, /) -> Asset:
        """
        :param int t: transaction group index
        :returns Asset: Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def created_application_id(t: int, /) -> Application:
        """
        :param int t: transaction group index
        :returns Application: ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def last_log(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: The last message emitted. Empty bytes if none were emitted. Application mode only

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def state_proof_pk(t: int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: 64 byte state proof public key

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def approval_program_pages(t: int, a: UInt64 | int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: Approval Program as an array of pages

        Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
        """

    @staticmethod
    def num_approval_program_pages(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of Approval Program pages

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

    @staticmethod
    def clear_state_program_pages(t: int, a: UInt64 | int, /) -> Bytes:
        """
        :param int t: transaction group index
        :returns Bytes: ClearState Program as an array of pages

        Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)
        """

    @staticmethod
    def num_clear_state_program_pages(t: int, /) -> UInt64:
        """
        :param int t: transaction group index
        :returns UInt64: Number of ClearState Program pages

        Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)
        """

class GTxn:
    """
    Get values for transactions in the current group
    Native TEAL ops: [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
    """
    @staticmethod
    def sender(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def fee(a: UInt64 | int, /) -> UInt64:
        """
        microalgos

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def first_valid(a: UInt64 | int, /) -> UInt64:
        """
        round number

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def first_valid_time(a: UInt64 | int, /) -> UInt64:
        """
        UNIX timestamp of block before txn.FirstValid. Fails if negative

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def last_valid(a: UInt64 | int, /) -> UInt64:
        """
        round number

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def note(a: UInt64 | int, /) -> Bytes:
        """
        Any data up to 1024 bytes

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def lease(a: UInt64 | int, /) -> Bytes:
        """
        32 byte lease value

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def receiver(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def amount(a: UInt64 | int, /) -> UInt64:
        """
        microalgos

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def close_remainder_to(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def vote_pk(a: UInt64 | int, /) -> Bytes:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def selection_pk(a: UInt64 | int, /) -> Bytes:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def vote_first(a: UInt64 | int, /) -> UInt64:
        """
        The first round that the participation key is valid.

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def vote_last(a: UInt64 | int, /) -> UInt64:
        """
        The last round that the participation key is valid.

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def vote_key_dilution(a: UInt64 | int, /) -> UInt64:
        """
        Dilution for the 2-level participation key

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def type(a: UInt64 | int, /) -> Bytes:
        """
        Transaction type as bytes

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def type_enum(a: UInt64 | int, /) -> TransactionType:
        """
        Transaction type as integer

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def xfer_asset(a: UInt64 | int, /) -> Asset:
        """
        Asset ID

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def asset_amount(a: UInt64 | int, /) -> UInt64:
        """
        value in Asset's units

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def asset_sender(a: UInt64 | int, /) -> Account:
        """
        32 byte address. Source of assets if Sender is the Asset's Clawback address.

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def asset_receiver(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def asset_close_to(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def group_index(a: UInt64 | int, /) -> UInt64:
        """
        Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def tx_id(a: UInt64 | int, /) -> Bytes:
        """
        The computed ID for this transaction. 32 bytes.

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def application_id(a: UInt64 | int, /) -> Application:
        """
        ApplicationID from ApplicationCall transaction

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def on_completion(a: UInt64 | int, /) -> OnCompleteAction:
        """
        ApplicationCall transaction on completion action

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def application_args(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        Arguments passed to the application in the ApplicationCall transaction

        Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
        """

    @staticmethod
    def num_app_args(a: UInt64 | int, /) -> UInt64:
        """
        Number of ApplicationArgs

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def accounts(a: UInt64 | int, b: UInt64 | int, /) -> Account:
        """
        Accounts listed in the ApplicationCall transaction

        Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
        """

    @staticmethod
    def num_accounts(a: UInt64 | int, /) -> UInt64:
        """
        Number of Accounts

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def approval_program(a: UInt64 | int, /) -> Bytes:
        """
        Approval program

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def clear_state_program(a: UInt64 | int, /) -> Bytes:
        """
        Clear state program

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def rekey_to(a: UInt64 | int, /) -> Account:
        """
        32 byte Sender's new AuthAddr

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset(a: UInt64 | int, /) -> Asset:
        """
        Asset ID in asset config transaction

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_total(a: UInt64 | int, /) -> UInt64:
        """
        Total number of units of this asset created

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_decimals(a: UInt64 | int, /) -> UInt64:
        """
        Number of digits to display after the decimal place when displaying the asset

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_default_frozen(a: UInt64 | int, /) -> bool:
        """
        Whether the asset's slots are frozen by default or not, 0 or 1

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_unit_name(a: UInt64 | int, /) -> Bytes:
        """
        Unit name of the asset

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_name(a: UInt64 | int, /) -> Bytes:
        """
        The asset name

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_url(a: UInt64 | int, /) -> Bytes:
        """
        URL

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_metadata_hash(a: UInt64 | int, /) -> Bytes:
        """
        32 byte commitment to unspecified asset metadata

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_manager(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_reserve(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_freeze(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def config_asset_clawback(a: UInt64 | int, /) -> Account:
        """
        32 byte address

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def freeze_asset(a: UInt64 | int, /) -> Asset:
        """
        Asset ID being frozen or un-frozen

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def freeze_asset_account(a: UInt64 | int, /) -> Account:
        """
        32 byte address of the account whose asset slot is being frozen or un-frozen

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def freeze_asset_frozen(a: UInt64 | int, /) -> bool:
        """
        The new frozen value, 0 or 1

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def assets(a: UInt64 | int, b: UInt64 | int, /) -> Asset:
        """
        Foreign Assets listed in the ApplicationCall transaction

        Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
        """

    @staticmethod
    def num_assets(a: UInt64 | int, /) -> UInt64:
        """
        Number of Assets

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def applications(a: UInt64 | int, b: UInt64 | int, /) -> Application:
        """
        Foreign Apps listed in the ApplicationCall transaction

        Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
        """

    @staticmethod
    def num_applications(a: UInt64 | int, /) -> UInt64:
        """
        Number of Applications

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def global_num_uint(a: UInt64 | int, /) -> UInt64:
        """
        Number of global state integers in ApplicationCall

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def global_num_byte_slice(a: UInt64 | int, /) -> UInt64:
        """
        Number of global state byteslices in ApplicationCall

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def local_num_uint(a: UInt64 | int, /) -> UInt64:
        """
        Number of local state integers in ApplicationCall

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def local_num_byte_slice(a: UInt64 | int, /) -> UInt64:
        """
        Number of local state byteslices in ApplicationCall

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def extra_program_pages(a: UInt64 | int, /) -> UInt64:
        """
        Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def nonparticipation(a: UInt64 | int, /) -> bool:
        """
        Marks an account nonparticipating for rewards

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def logs(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        Log messages emitted by an application call (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
        """

    @staticmethod
    def num_logs(a: UInt64 | int, /) -> UInt64:
        """
        Number of Logs (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def created_asset_id(a: UInt64 | int, /) -> Asset:
        """
        Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def created_application_id(a: UInt64 | int, /) -> Application:
        """
        ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def last_log(a: UInt64 | int, /) -> Bytes:
        """
        The last message emitted. Empty bytes if none were emitted. Application mode only

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def state_proof_pk(a: UInt64 | int, /) -> Bytes:
        """
        64 byte state proof public key

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def approval_program_pages(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        Approval Program as an array of pages

        Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
        """

    @staticmethod
    def num_approval_program_pages(a: UInt64 | int, /) -> UInt64:
        """
        Number of Approval Program pages

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

    @staticmethod
    def clear_state_program_pages(a: UInt64 | int, b: UInt64 | int, /) -> Bytes:
        """
        ClearState Program as an array of pages

        Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)
        """

    @staticmethod
    def num_clear_state_program_pages(a: UInt64 | int, /) -> UInt64:
        """
        Number of ClearState Program pages

        Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)
        """

class Global:
    """
    Get Global values
    Native TEAL op: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)
    """

    min_txn_fee: typing.Final[UInt64] = ...
    """
    microalgos
    """

    min_balance: typing.Final[UInt64] = ...
    """
    microalgos
    """

    max_txn_life: typing.Final[UInt64] = ...
    """
    rounds
    """

    zero_address: typing.Final[Account] = ...
    """
    32 byte address of all zero bytes
    """

    group_size: typing.Final[UInt64] = ...
    """
    Number of transactions in this atomic transaction group. At least 1
    """

    logic_sig_version: typing.Final[UInt64] = ...
    """
    Maximum supported version
    """

    round: typing.Final[UInt64] = ...
    """
    Current round number. Application mode only.
    """

    latest_timestamp: typing.Final[UInt64] = ...
    """
    Last confirmed block UNIX timestamp. Fails if negative. Application mode only.
    """

    current_application_id: typing.Final[Application] = ...
    """
    ID of current application executing. Application mode only.
    """

    creator_address: typing.Final[Account] = ...
    """
    Address of the creator of the current application. Application mode only.
    """

    current_application_address: typing.Final[Account] = ...
    """
    Address that the current application controls. Application mode only.
    """

    group_id: typing.Final[Bytes] = ...
    """
    ID of the transaction group. 32 zero bytes if the transaction is not part of a group.
    """

    @staticmethod
    def opcode_budget() -> UInt64:
        """
        The remaining cost that can be spent by opcodes in this program.

        Native TEAL opcode: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)
        """

    caller_application_id: typing.Final[UInt64] = ...
    """
    The application ID of the application that called this application. 0 if this application is at the top-level. Application mode only.
    """

    caller_application_address: typing.Final[Account] = ...
    """
    The application address of the application that called this application. ZeroAddress if this application is at the top-level. Application mode only.
    """

    asset_create_min_balance: typing.Final[UInt64] = ...
    """
    The additional minimum balance required to create (and opt-in to) an asset.
    """

    asset_opt_in_min_balance: typing.Final[UInt64] = ...
    """
    The additional minimum balance required to opt-in to an asset.
    """

    genesis_hash: typing.Final[Bytes] = ...
    """
    The Genesis Hash for the network.
    """

    payouts_enabled: typing.Final[bool] = ...
    """
    Whether block proposal payouts are enabled.
    Min AVM version: 11
    """

    payouts_go_online_fee: typing.Final[UInt64] = ...
    """
    The fee required in a keyreg transaction to make an account incentive eligible.
    Min AVM version: 11
    """

    payouts_percent: typing.Final[UInt64] = ...
    """
    The percentage of transaction fees in a block that can be paid to the block proposer.
    Min AVM version: 11
    """

    payouts_min_balance: typing.Final[UInt64] = ...
    """
    The minimum balance an account must have in the agreement round to receive block payouts in the proposal round.
    Min AVM version: 11
    """

    payouts_max_balance: typing.Final[UInt64] = ...
    """
    The maximum balance an account can have in the agreement round to receive block payouts in the proposal round.
    Min AVM version: 11
    """

class ITxn:
    """
    Get values for the last inner transaction
    Native TEAL ops: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
    """
    @staticmethod
    def sender() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def fee() -> UInt64:
        """
        microalgos

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def first_valid() -> UInt64:
        """
        round number

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def first_valid_time() -> UInt64:
        """
        UNIX timestamp of block before txn.FirstValid. Fails if negative

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def last_valid() -> UInt64:
        """
        round number

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def note() -> Bytes:
        """
        Any data up to 1024 bytes

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def lease() -> Bytes:
        """
        32 byte lease value

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def receiver() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def amount() -> UInt64:
        """
        microalgos

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def close_remainder_to() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def vote_pk() -> Bytes:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def selection_pk() -> Bytes:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def vote_first() -> UInt64:
        """
        The first round that the participation key is valid.

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def vote_last() -> UInt64:
        """
        The last round that the participation key is valid.

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def vote_key_dilution() -> UInt64:
        """
        Dilution for the 2-level participation key

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def type() -> Bytes:
        """
        Transaction type as bytes

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def type_enum() -> TransactionType:
        """
        Transaction type as integer

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def xfer_asset() -> Asset:
        """
        Asset ID

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def asset_amount() -> UInt64:
        """
        value in Asset's units

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def asset_sender() -> Account:
        """
        32 byte address. Source of assets if Sender is the Asset's Clawback address.

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def asset_receiver() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def asset_close_to() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def group_index() -> UInt64:
        """
        Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def tx_id() -> Bytes:
        """
        The computed ID for this transaction. 32 bytes.

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def application_id() -> Application:
        """
        ApplicationID from ApplicationCall transaction

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def on_completion() -> OnCompleteAction:
        """
        ApplicationCall transaction on completion action

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def application_args(a: UInt64 | int, /) -> Bytes:
        """
        Arguments passed to the application in the ApplicationCall transaction

        Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
        """

    @staticmethod
    def num_app_args() -> UInt64:
        """
        Number of ApplicationArgs

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def accounts(a: UInt64 | int, /) -> Account:
        """
        Accounts listed in the ApplicationCall transaction

        Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
        """

    @staticmethod
    def num_accounts() -> UInt64:
        """
        Number of Accounts

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def approval_program() -> Bytes:
        """
        Approval program

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def clear_state_program() -> Bytes:
        """
        Clear state program

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def rekey_to() -> Account:
        """
        32 byte Sender's new AuthAddr

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset() -> Asset:
        """
        Asset ID in asset config transaction

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_total() -> UInt64:
        """
        Total number of units of this asset created

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_decimals() -> UInt64:
        """
        Number of digits to display after the decimal place when displaying the asset

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_default_frozen() -> bool:
        """
        Whether the asset's slots are frozen by default or not, 0 or 1

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_unit_name() -> Bytes:
        """
        Unit name of the asset

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_name() -> Bytes:
        """
        The asset name

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_url() -> Bytes:
        """
        URL

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_metadata_hash() -> Bytes:
        """
        32 byte commitment to unspecified asset metadata

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_manager() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_reserve() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_freeze() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def config_asset_clawback() -> Account:
        """
        32 byte address

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def freeze_asset() -> Asset:
        """
        Asset ID being frozen or un-frozen

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def freeze_asset_account() -> Account:
        """
        32 byte address of the account whose asset slot is being frozen or un-frozen

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def freeze_asset_frozen() -> bool:
        """
        The new frozen value, 0 or 1

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def assets(a: UInt64 | int, /) -> Asset:
        """
        Foreign Assets listed in the ApplicationCall transaction

        Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
        """

    @staticmethod
    def num_assets() -> UInt64:
        """
        Number of Assets

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def applications(a: UInt64 | int, /) -> Application:
        """
        Foreign Apps listed in the ApplicationCall transaction

        Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
        """

    @staticmethod
    def num_applications() -> UInt64:
        """
        Number of Applications

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def global_num_uint() -> UInt64:
        """
        Number of global state integers in ApplicationCall

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def global_num_byte_slice() -> UInt64:
        """
        Number of global state byteslices in ApplicationCall

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def local_num_uint() -> UInt64:
        """
        Number of local state integers in ApplicationCall

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def local_num_byte_slice() -> UInt64:
        """
        Number of local state byteslices in ApplicationCall

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def extra_program_pages() -> UInt64:
        """
        Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def nonparticipation() -> bool:
        """
        Marks an account nonparticipating for rewards

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def logs(a: UInt64 | int, /) -> Bytes:
        """
        Log messages emitted by an application call (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
        """

    @staticmethod
    def num_logs() -> UInt64:
        """
        Number of Logs (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def created_asset_id() -> Asset:
        """
        Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def created_application_id() -> Application:
        """
        ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def last_log() -> Bytes:
        """
        The last message emitted. Empty bytes if none were emitted. Application mode only

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def state_proof_pk() -> Bytes:
        """
        64 byte state proof public key

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def approval_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        Approval Program as an array of pages

        Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
        """

    @staticmethod
    def num_approval_program_pages() -> UInt64:
        """
        Number of Approval Program pages

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

    @staticmethod
    def clear_state_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        ClearState Program as an array of pages

        Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)
        """

    @staticmethod
    def num_clear_state_program_pages() -> UInt64:
        """
        Number of ClearState Program pages

        Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)
        """

class ITxnCreate:
    """
    Create inner transactions
    Native TEAL ops: [`itxn_begin`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_begin), [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field), [`itxn_next`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_next), [`itxn_submit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_submit)
    """
    @staticmethod
    def begin() -> None:
        """
        begin preparation of a new inner transaction in a new transaction group
        `itxn_begin` initializes Sender to the application address; Fee to the minimum allowable, taking into account MinTxnFee and credit from overpaying in earlier transactions; FirstValid/LastValid to the values in the invoking transaction, and all other fields to zero or empty values.

        Native TEAL opcode: [`itxn_begin`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_begin)
        """

    @staticmethod
    def next() -> None:
        """
        begin preparation of a new inner transaction in the same transaction group
        `itxn_next` initializes the transaction exactly as `itxn_begin` does

        Native TEAL opcode: [`itxn_next`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_next)
        """

    @staticmethod
    def submit() -> None:
        """
        execute the current inner transaction group. Fail if executing this group would exceed the inner transaction limit, or if any transaction in the group fails.
        `itxn_submit` resets the current transaction so that it can not be resubmitted. A new `itxn_begin` is required to prepare another inner transaction.

        Native TEAL opcode: [`itxn_submit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_submit)
        """

    @staticmethod
    def set_sender(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_fee(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: microalgos

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_note(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: Any data up to 1024 bytes

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_receiver(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_amount(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: microalgos

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_close_remainder_to(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_vote_pk(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_selection_pk(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_vote_first(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: The first round that the participation key is valid.

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_vote_last(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: The last round that the participation key is valid.

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_vote_key_dilution(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Dilution for the 2-level participation key

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_type(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: Transaction type as bytes

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_type_enum(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Transaction type as integer

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_xfer_asset(a: Asset | UInt64 | int, /) -> None:
        """
        :param Asset | UInt64 | int a: Asset ID

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_asset_amount(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: value in Asset's units

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_asset_sender(a: Account, /) -> None:
        """
        :param Account a: 32 byte address. Source of assets if Sender is the Asset's Clawback address.

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_asset_receiver(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_asset_close_to(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_application_id(a: Application | UInt64 | int, /) -> None:
        """
        :param Application | UInt64 | int a: ApplicationID from ApplicationCall transaction

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_on_completion(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: ApplicationCall transaction on completion action

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_application_args(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: Arguments passed to the application in the ApplicationCall transaction

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_accounts(a: Account, /) -> None:
        """
        :param Account a: Accounts listed in the ApplicationCall transaction

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_approval_program(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: Approval program

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_clear_state_program(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: Clear state program

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_rekey_to(a: Account, /) -> None:
        """
        :param Account a: 32 byte Sender's new AuthAddr

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset(a: Asset | UInt64 | int, /) -> None:
        """
        :param Asset | UInt64 | int a: Asset ID in asset config transaction

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_total(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Total number of units of this asset created

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_decimals(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Number of digits to display after the decimal place when displaying the asset

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_default_frozen(a: bool | UInt64 | int, /) -> None:
        """
        :param bool | UInt64 | int a: Whether the asset's slots are frozen by default or not, 0 or 1

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_unit_name(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: Unit name of the asset

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_name(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: The asset name

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_url(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: URL

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_metadata_hash(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: 32 byte commitment to unspecified asset metadata

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_manager(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_reserve(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_freeze(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_config_asset_clawback(a: Account, /) -> None:
        """
        :param Account a: 32 byte address

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_freeze_asset(a: Asset | UInt64 | int, /) -> None:
        """
        :param Asset | UInt64 | int a: Asset ID being frozen or un-frozen

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_freeze_asset_account(a: Account, /) -> None:
        """
        :param Account a: 32 byte address of the account whose asset slot is being frozen or un-frozen

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_freeze_asset_frozen(a: bool | UInt64 | int, /) -> None:
        """
        :param bool | UInt64 | int a: The new frozen value, 0 or 1

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_assets(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Foreign Assets listed in the ApplicationCall transaction

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_applications(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Foreign Apps listed in the ApplicationCall transaction

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_global_num_uint(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Number of global state integers in ApplicationCall

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_global_num_byte_slice(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Number of global state byteslices in ApplicationCall

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_local_num_uint(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Number of local state integers in ApplicationCall

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_local_num_byte_slice(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Number of local state byteslices in ApplicationCall

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_extra_program_pages(a: UInt64 | int, /) -> None:
        """
        :param UInt64 | int a: Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_nonparticipation(a: bool | UInt64 | int, /) -> None:
        """
        :param bool | UInt64 | int a: Marks an account nonparticipating for rewards

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_state_proof_pk(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: 64 byte state proof public key

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_approval_program_pages(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: Approval Program as an array of pages

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

    @staticmethod
    def set_clear_state_program_pages(a: Bytes | bytes, /) -> None:
        """
        :param Bytes | bytes a: ClearState Program as an array of pages

        Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)
        """

class JsonRef:
    """
    key B's value, of type R, from a [valid](jsonspec.md) utf-8 encoded json object A *Warning*: Usage should be restricted to very rare use cases, as JSON decoding is expensive and quite limited. In addition, JSON objects are large and not optimized for size.  Almost all smart contracts should use simpler and smaller methods (such as the [ABI](https://arc.algorand.foundation/ARCs/arc-0004). This opcode should only be used in cases where JSON is only available option, e.g. when a third-party only signs JSON.
    Native TEAL op: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)
    """
    @staticmethod
    def json_string(a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
        """

        Native TEAL opcode: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)
        """

    @staticmethod
    def json_uint64(a: Bytes | bytes, b: Bytes | bytes, /) -> UInt64:
        """

        Native TEAL opcode: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)
        """

    @staticmethod
    def json_object(a: Bytes | bytes, b: Bytes | bytes, /) -> Bytes:
        """

        Native TEAL opcode: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)
        """

class Scratch:
    """
    Load or store scratch values
    Native TEAL ops: [`loads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#loads), [`stores`](https://dev.algorand.co/reference/algorand-teal/opcodes/#stores)
    """
    @staticmethod
    def load_bytes(a: UInt64 | int, /) -> Bytes:
        """
        Ath scratch space value.  All scratch spaces are 0 at program start.

        Native TEAL opcode: [`loads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#loads)
        """

    @staticmethod
    def load_uint64(a: UInt64 | int, /) -> UInt64:
        """
        Ath scratch space value.  All scratch spaces are 0 at program start.

        Native TEAL opcode: [`loads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#loads)
        """

    @staticmethod
    def store(a: UInt64 | int, b: Bytes | UInt64 | bytes | int, /) -> None:
        """
        store B to the Ath scratch space

        Native TEAL opcode: [`stores`](https://dev.algorand.co/reference/algorand-teal/opcodes/#stores)
        """

class Txn:
    """
    Get values for the current executing transaction
    Native TEAL ops: [`txn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txn), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
    """

    sender: typing.Final[Account] = ...
    """
    32 byte address
    """

    fee: typing.Final[UInt64] = ...
    """
    microalgos
    """

    first_valid: typing.Final[UInt64] = ...
    """
    round number
    """

    first_valid_time: typing.Final[UInt64] = ...
    """
    UNIX timestamp of block before txn.FirstValid. Fails if negative
    """

    last_valid: typing.Final[UInt64] = ...
    """
    round number
    """

    note: typing.Final[Bytes] = ...
    """
    Any data up to 1024 bytes
    """

    lease: typing.Final[Bytes] = ...
    """
    32 byte lease value
    """

    receiver: typing.Final[Account] = ...
    """
    32 byte address
    """

    amount: typing.Final[UInt64] = ...
    """
    microalgos
    """

    close_remainder_to: typing.Final[Account] = ...
    """
    32 byte address
    """

    vote_pk: typing.Final[Bytes] = ...
    """
    32 byte address
    """

    selection_pk: typing.Final[Bytes] = ...
    """
    32 byte address
    """

    vote_first: typing.Final[UInt64] = ...
    """
    The first round that the participation key is valid.
    """

    vote_last: typing.Final[UInt64] = ...
    """
    The last round that the participation key is valid.
    """

    vote_key_dilution: typing.Final[UInt64] = ...
    """
    Dilution for the 2-level participation key
    """

    type: typing.Final[Bytes] = ...
    """
    Transaction type as bytes
    """

    type_enum: typing.Final[TransactionType] = ...
    """
    Transaction type as integer
    """

    xfer_asset: typing.Final[Asset] = ...
    """
    Asset ID
    """

    asset_amount: typing.Final[UInt64] = ...
    """
    value in Asset's units
    """

    asset_sender: typing.Final[Account] = ...
    """
    32 byte address. Source of assets if Sender is the Asset's Clawback address.
    """

    asset_receiver: typing.Final[Account] = ...
    """
    32 byte address
    """

    asset_close_to: typing.Final[Account] = ...
    """
    32 byte address
    """

    group_index: typing.Final[UInt64] = ...
    """
    Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1
    """

    tx_id: typing.Final[Bytes] = ...
    """
    The computed ID for this transaction. 32 bytes.
    """

    application_id: typing.Final[Application] = ...
    """
    ApplicationID from ApplicationCall transaction
    """

    on_completion: typing.Final[OnCompleteAction] = ...
    """
    ApplicationCall transaction on completion action
    """

    @staticmethod
    def application_args(a: UInt64 | int, /) -> Bytes:
        """
        Arguments passed to the application in the ApplicationCall transaction

        Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
        """

    num_app_args: typing.Final[UInt64] = ...
    """
    Number of ApplicationArgs
    """

    @staticmethod
    def accounts(a: UInt64 | int, /) -> Account:
        """
        Accounts listed in the ApplicationCall transaction

        Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
        """

    num_accounts: typing.Final[UInt64] = ...
    """
    Number of Accounts
    """

    approval_program: typing.Final[Bytes] = ...
    """
    Approval program
    """

    clear_state_program: typing.Final[Bytes] = ...
    """
    Clear state program
    """

    rekey_to: typing.Final[Account] = ...
    """
    32 byte Sender's new AuthAddr
    """

    config_asset: typing.Final[Asset] = ...
    """
    Asset ID in asset config transaction
    """

    config_asset_total: typing.Final[UInt64] = ...
    """
    Total number of units of this asset created
    """

    config_asset_decimals: typing.Final[UInt64] = ...
    """
    Number of digits to display after the decimal place when displaying the asset
    """

    config_asset_default_frozen: typing.Final[bool] = ...
    """
    Whether the asset's slots are frozen by default or not, 0 or 1
    """

    config_asset_unit_name: typing.Final[Bytes] = ...
    """
    Unit name of the asset
    """

    config_asset_name: typing.Final[Bytes] = ...
    """
    The asset name
    """

    config_asset_url: typing.Final[Bytes] = ...
    """
    URL
    """

    config_asset_metadata_hash: typing.Final[Bytes] = ...
    """
    32 byte commitment to unspecified asset metadata
    """

    config_asset_manager: typing.Final[Account] = ...
    """
    32 byte address
    """

    config_asset_reserve: typing.Final[Account] = ...
    """
    32 byte address
    """

    config_asset_freeze: typing.Final[Account] = ...
    """
    32 byte address
    """

    config_asset_clawback: typing.Final[Account] = ...
    """
    32 byte address
    """

    freeze_asset: typing.Final[Asset] = ...
    """
    Asset ID being frozen or un-frozen
    """

    freeze_asset_account: typing.Final[Account] = ...
    """
    32 byte address of the account whose asset slot is being frozen or un-frozen
    """

    freeze_asset_frozen: typing.Final[bool] = ...
    """
    The new frozen value, 0 or 1
    """

    @staticmethod
    def assets(a: UInt64 | int, /) -> Asset:
        """
        Foreign Assets listed in the ApplicationCall transaction

        Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
        """

    num_assets: typing.Final[UInt64] = ...
    """
    Number of Assets
    """

    @staticmethod
    def applications(a: UInt64 | int, /) -> Application:
        """
        Foreign Apps listed in the ApplicationCall transaction

        Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
        """

    num_applications: typing.Final[UInt64] = ...
    """
    Number of Applications
    """

    global_num_uint: typing.Final[UInt64] = ...
    """
    Number of global state integers in ApplicationCall
    """

    global_num_byte_slice: typing.Final[UInt64] = ...
    """
    Number of global state byteslices in ApplicationCall
    """

    local_num_uint: typing.Final[UInt64] = ...
    """
    Number of local state integers in ApplicationCall
    """

    local_num_byte_slice: typing.Final[UInt64] = ...
    """
    Number of local state byteslices in ApplicationCall
    """

    extra_program_pages: typing.Final[UInt64] = ...
    """
    Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.
    """

    nonparticipation: typing.Final[bool] = ...
    """
    Marks an account nonparticipating for rewards
    """

    @staticmethod
    def logs(a: UInt64 | int, /) -> Bytes:
        """
        Log messages emitted by an application call (only with `itxn` in v5). Application mode only

        Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
        """

    num_logs: typing.Final[UInt64] = ...
    """
    Number of Logs (only with `itxn` in v5). Application mode only
    """

    created_asset_id: typing.Final[Asset] = ...
    """
    Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only
    """

    created_application_id: typing.Final[Application] = ...
    """
    ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only
    """

    last_log: typing.Final[Bytes] = ...
    """
    The last message emitted. Empty bytes if none were emitted. Application mode only
    """

    state_proof_pk: typing.Final[Bytes] = ...
    """
    64 byte state proof public key
    """

    @staticmethod
    def approval_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        Approval Program as an array of pages

        Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
        """

    num_approval_program_pages: typing.Final[UInt64] = ...
    """
    Number of Approval Program pages
    """

    @staticmethod
    def clear_state_program_pages(a: UInt64 | int, /) -> Bytes:
        """
        ClearState Program as an array of pages

        Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)
        """

    num_clear_state_program_pages: typing.Final[UInt64] = ...
    """
    Number of ClearState Program pages
    """

class VoterParamsGet:
    """
    X is field F from online account A as of the balance round: 320 rounds before the current round. Y is 1 if A had positive algos online in the agreement round, else Y is 0 and X is a type specific zero-value
    Native TEAL op: [`voter_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#voter_params_get)
    """
    @staticmethod
    def voter_balance(a: Account | UInt64 | int, /) -> tuple[UInt64, bool]:
        """
        Min AVM version: 11
        :returns tuple[UInt64, bool]: Online stake in microalgos

        Native TEAL opcode: [`voter_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#voter_params_get)
        """

    @staticmethod
    def voter_incentive_eligible(a: Account | UInt64 | int, /) -> tuple[bool, bool]:
        """
        Min AVM version: 11
        :returns tuple[bool, bool]: Had this account opted into block payouts

        Native TEAL opcode: [`voter_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#voter_params_get)
        """
