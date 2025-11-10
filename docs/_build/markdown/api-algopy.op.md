# [`algopy.op`](#module-algopy.op)

## Module Contents

### Classes

| [`AcctParamsGet`](#algopy.op.AcctParamsGet)           | X is field F from account A. Y is 1 if A owns positive algos, else 0<br/>Native TEAL op: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
|-------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`AppGlobal`](#algopy.op.AppGlobal)                   | Get or modify Global app state<br/>Native TEAL ops: [`app_global_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_del), [`app_global_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get), [`app_global_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get_ex), [`app_global_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_put)                                                                                                                                                                                                                                                                                                                                                                         |
| [`AppLocal`](#algopy.op.AppLocal)                     | Get or modify Local app state<br/>Native TEAL ops: [`app_local_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_del), [`app_local_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get), [`app_local_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get_ex), [`app_local_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_put)                                                                                                                                                                                                                                                                                                                                                                                  |
| [`AppParamsGet`](#algopy.op.AppParamsGet)             | X is field F from app A. Y is 1 if A exists, else 0 params: Txn.ForeignApps offset or an *available* app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.<br/>Native TEAL op: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| [`AssetHoldingGet`](#algopy.op.AssetHoldingGet)       | X is field F from account A’s holding of asset B. Y is 1 if A is opted into B, else 0 params: Txn.Accounts offset (or, since v4, an *available* address), asset id (or, since v4, a Txn.ForeignAssets offset). Return: did_exist flag (1 if the asset existed and 0 otherwise), value.<br/>Native TEAL op: [`asset_holding_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_holding_get)                                                                                                                                                                                                                                                                                                                                                                                                         |
| [`AssetParamsGet`](#algopy.op.AssetParamsGet)         | X is field F from asset A. Y is 1 if A exists, else 0 params: Txn.ForeignAssets offset (or, since v4, an *available* asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.<br/>Native TEAL op: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| [`Base64`](#algopy.op.Base64)                         | Available values for the `base64` enum                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [`Block`](#algopy.op.Block)                           | field F of block A. Fail unless A falls between txn.LastValid-1002 and txn.FirstValid (exclusive)<br/>Native TEAL op: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| [`Box`](#algopy.op.Box)                               | Get or modify box state<br/>Native TEAL ops: [`box_create`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_create), [`box_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_del), [`box_extract`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_extract), [`box_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_get), [`box_len`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_len), [`box_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_put), [`box_replace`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_replace), [`box_resize`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_resize), [`box_splice`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_splice) |
| [`EC`](#algopy.op.EC)                                 | Available values for the `EC` enum                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| [`ECDSA`](#algopy.op.ECDSA)                           | Available values for the `ECDSA` enum                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| [`EllipticCurve`](#algopy.op.EllipticCurve)           | Elliptic Curve functions<br/>Native TEAL ops: [`ec_add`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_add), [`ec_map_to`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_map_to), [`ec_multi_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_multi_scalar_mul), [`ec_pairing_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_pairing_check), [`ec_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_scalar_mul), [`ec_subgroup_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_subgroup_check)                                                                                                                                                                                                   |
| [`GITxn`](#algopy.op.GITxn)                           | Get values for inner transaction in the last group submitted<br/>Native TEAL ops: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| [`GTxn`](#algopy.op.GTxn)                             | Get values for transactions in the current group<br/>Native TEAL ops: [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| [`Global`](#algopy.op.Global)                         | Get Global values<br/>Native TEAL op: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [`ITxn`](#algopy.op.ITxn)                             | Get values for the last inner transaction<br/>Native TEAL ops: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| [`ITxnCreate`](#algopy.op.ITxnCreate)                 | Create inner transactions<br/>Native TEAL ops: [`itxn_begin`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_begin), [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field), [`itxn_next`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_next), [`itxn_submit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_submit)                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [`JsonRef`](#algopy.op.JsonRef)                       | key B’s value, of type R, from a [valid]() utf-8 encoded json object A *Warning*: Usage should be restricted to very rare use cases, as JSON decoding is expensive and quite limited. In addition, JSON objects are large and not optimized for size.  Almost all smart contracts should use simpler and smaller methods (such as the [ABI](https://arc.algorand.foundation/ARCs/arc-0004). This opcode should only be used in cases where JSON is only available option, e.g. when a third-party only signs JSON.<br/>Native TEAL op: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)                                                                                                                                                                                               |
| [`MiMCConfigurations`](#algopy.op.MiMCConfigurations) | Available values for the `Mimc Configurations` enum                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| [`Scratch`](#algopy.op.Scratch)                       | Load or store scratch values<br/>Native TEAL ops: [`loads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#loads), [`stores`](https://dev.algorand.co/reference/algorand-teal/opcodes/#stores)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| [`Txn`](#algopy.op.Txn)                               | Get values for the current executing transaction<br/>Native TEAL ops: [`txn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txn), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [`VoterParamsGet`](#algopy.op.VoterParamsGet)         | X is field F from online account A as of the balance round: 320 rounds before the current round. Y is 1 if A had positive algos online in the agreement round, else Y is 0 and X is a type specific zero-value<br/>Native TEAL op: [`voter_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#voter_params_get)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| [`VrfVerify`](#algopy.op.VrfVerify)                   | Available values for the `vrf_verify` enum                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |

### Functions

| [`addw`](#algopy.op.addw)                               | A plus B as a 128-bit result. X is the carry-bit, Y is the low-order 64 bits.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
|---------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`app_opted_in`](#algopy.op.app_opted_in)               | 1 if account A is opted in to application B, else 0<br/>params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset). Return: 1 if opted in and 0 otherwise.                                                                                                                                                                                                                                                                                                                                                                                   |
| [`arg`](#algopy.op.arg)                                 | Ath LogicSig argument                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| [`balance`](#algopy.op.balance)                         | balance for account A, in microalgos. The balance is observed after the effects of previous transactions in the group, and after the fee for the current transaction is deducted. Changes caused by inner transactions are observable immediately following `itxn_submit`<br/>params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset). Return: value.                                                                                                                                                                                     |
| [`base64_decode`](#algopy.op.base64_decode)             | decode A which was base64-encoded using *encoding* E. Fail if A is not base64 encoded with encoding E<br/>*Warning*: Usage should be restricted to very rare use cases. In almost all cases, smart contracts should directly handle non-encoded byte-strings. This opcode should only be used in cases where base64 is the only available option, e.g. interoperability with a third-party that only signs base64 strings.                                                                                                                                                                                                        |
| [`bitlen`](#algopy.op.bitlen)                           | The highest set bit in A. If A is a byte-array, it is interpreted as a big-endian unsigned integer. bitlen of 0 is 0, bitlen of 8 is 4<br/>bitlen interprets arrays as big-endian integers, unlike setbit/getbit                                                                                                                                                                                                                                                                                                                                                                                                                  |
| [`bsqrt`](#algopy.op.bsqrt)                             | The largest integer I such that I^2 <= A. A and I are interpreted as big-endian unsigned integers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| [`btoi`](#algopy.op.btoi)                               | converts big-endian byte array A to uint64. Fails if len(A) > 8. Padded by leading 0s if len(A) < 8.<br/>`btoi` fails if the input is longer than 8 bytes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| [`bzero`](#algopy.op.bzero)                             | zero filled byte-array of length A                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| [`concat`](#algopy.op.concat)                           | join A and B<br/>`concat` fails if the result would be greater than 4096 bytes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| [`divmodw`](#algopy.op.divmodw)                         | W,X = (A,B / C,D); Y,Z = (A,B modulo C,D)<br/>The notation J,K indicates that two uint64 values J and K are interpreted as a uint128 value, with J as the high uint64 and K the low.                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [`divw`](#algopy.op.divw)                               | A,B / C. Fail if C == 0 or if result overflows.<br/>The notation A,B indicates that A and B are interpreted as a uint128 value, with A as the high uint64 and B the low.                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| [`ecdsa_pk_decompress`](#algopy.op.ecdsa_pk_decompress) | decompress pubkey A into components X, Y<br/>The 33 byte public key in a compressed form to be decompressed into X and Y (top) components. All values are big-endian encoded.                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| [`ecdsa_pk_recover`](#algopy.op.ecdsa_pk_recover)       | for (data A, recovery id B, signature C, D) recover a public key<br/>S (top) and R elements of a signature, recovery id and data (bottom) are expected on the stack and used to deriver a public key. All values are big-endian encoded. The signed data must be 32 bytes long.                                                                                                                                                                                                                                                                                                                                                   |
| [`ecdsa_verify`](#algopy.op.ecdsa_verify)               | for (data A, signature B, C and pubkey D, E) verify the signature of the data against the pubkey => {0 or 1}<br/>The 32 byte Y-component of a public key is the last element on the stack, preceded by X-component of a pubkey, preceded by S and R components of a signature, preceded by the data that is fifth element on the stack. All values are big-endian encoded. The signed data must be 32 bytes long, and signatures in lower-S form are only accepted.                                                                                                                                                               |
| [`ed25519verify`](#algopy.op.ed25519verify)             | for (data A, signature B, pubkey C) verify the signature of (“ProgData” || program_hash || data) against the pubkey => {0 or 1}<br/>The 32 byte public key is the last element on the stack, preceded by the 64 byte signature at the second-to-last element on the stack, preceded by the data which was signed at the third-to-last element on the stack.                                                                                                                                                                                                                                                                       |
| [`ed25519verify_bare`](#algopy.op.ed25519verify_bare)   | for (data A, signature B, pubkey C) verify the signature of the data against the pubkey => {0 or 1}                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [`err`](#algopy.op.err)                                 | Fail immediately.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| [`exit`](#algopy.op.exit)                               | use A as success value; end                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| [`exp`](#algopy.op.exp)                                 | A raised to the Bth power. Fail if A == B == 0 and on overflow                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [`expw`](#algopy.op.expw)                               | A raised to the Bth power as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low. Fail if A == B == 0 or if the results exceeds 2^128-1                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| [`extract`](#algopy.op.extract)                         | A range of bytes from A starting at B up to but not including B+C. If B+C is larger than the array length, the program fails<br/>`extract3` can be called using `extract` with no immediates.                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| [`extract_uint16`](#algopy.op.extract_uint16)           | A uint16 formed from a range of big-endian bytes from A starting at B up to but not including B+2. If B+2 is larger than the array length, the program fails                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| [`extract_uint32`](#algopy.op.extract_uint32)           | A uint32 formed from a range of big-endian bytes from A starting at B up to but not including B+4. If B+4 is larger than the array length, the program fails                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| [`extract_uint64`](#algopy.op.extract_uint64)           | A uint64 formed from a range of big-endian bytes from A starting at B up to but not including B+8. If B+8 is larger than the array length, the program fails                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| [`falcon_verify`](#algopy.op.falcon_verify)             | for (data A, compressed-format signature B, pubkey C) verify the signature of data against the pubkey => {0 or 1}<br/>Min AVM version: 12                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| [`gaid`](#algopy.op.gaid)                               | ID of the asset or application created in the Ath transaction of the current group<br/>`gaids` fails unless the requested transaction created an asset or application and A < GroupIndex.                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| [`getbit`](#algopy.op.getbit)                           | Bth bit of (byte-array or integer) A. If B is greater than or equal to the bit length of the value (8\*byte length), the program fails<br/>see explanation of bit ordering in setbit                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [`getbyte`](#algopy.op.getbyte)                         | Bth byte of A, as an integer. If B is greater than or equal to the array length, the program fails                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| [`gload_bytes`](#algopy.op.gload_bytes)                 | Bth scratch space value of the Ath transaction in the current group                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [`gload_uint64`](#algopy.op.gload_uint64)               | Bth scratch space value of the Ath transaction in the current group                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [`itob`](#algopy.op.itob)                               | converts uint64 A to big-endian byte array, always of length 8                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [`keccak256`](#algopy.op.keccak256)                     | Keccak256 hash of value A, yields [32]byte                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| [`mimc`](#algopy.op.mimc)                               | MiMC hash of scalars A, using curve and parameters specified by configuration C<br/>A is a list of concatenated 32 byte big-endian unsigned integer scalars.  Fail if A’s length is not a multiple of 32 or any element exceeds the curve modulus.                                                                                                                                                                                                                                                                                                                                                                                |
| [`min_balance`](#algopy.op.min_balance)                 | minimum required balance for account A, in microalgos. Required balance is affected by ASA, App, and Box usage. When creating or opting into an app, the minimum balance grows before the app code runs, therefore the increase is visible there. When deleting or closing out, the minimum balance decreases after the app executes. Changes caused by inner transactions or box usage are observable immediately following the opcode effecting the change.<br/>params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset). Return: value. |
| [`mulw`](#algopy.op.mulw)                               | A times B as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| [`online_stake`](#algopy.op.online_stake)               | the total online stake in the agreement round<br/>Min AVM version: 11                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| [`replace`](#algopy.op.replace)                         | Copy of A with the bytes starting at B replaced by the bytes of C. Fails if B+len(C) exceeds len(A)<br/>`replace3` can be called using `replace` with no immediates.                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [`select_bytes`](#algopy.op.select_bytes)               | selects one of two values based on top-of-stack: B if C != 0, else A                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [`select_uint64`](#algopy.op.select_uint64)             | selects one of two values based on top-of-stack: B if C != 0, else A                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [`setbit_bytes`](#algopy.op.setbit_bytes)               | Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8\*byte length), the program fails<br/>When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.                                                                                            |
| [`setbit_uint64`](#algopy.op.setbit_uint64)             | Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8\*byte length), the program fails<br/>When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.                                                                                            |
| [`setbyte`](#algopy.op.setbyte)                         | Copy of A with the Bth byte set to small integer (between 0..255) C. If B is greater than or equal to the array length, the program fails                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| [`sha256`](#algopy.op.sha256)                           | SHA256 hash of value A, yields [32]byte                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| [`sha3_256`](#algopy.op.sha3_256)                       | SHA3_256 hash of value A, yields [32]byte                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| [`sha512_256`](#algopy.op.sha512_256)                   | SHA512_256 hash of value A, yields [32]byte                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| [`shl`](#algopy.op.shl)                                 | A times 2^B, modulo 2^64                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| [`shr`](#algopy.op.shr)                                 | A divided by 2^B                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| [`sqrt`](#algopy.op.sqrt)                               | The largest integer I such that I^2 <= A                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| [`substring`](#algopy.op.substring)                     | A range of bytes from A starting at B up to but not including C. If C < B, or either is larger than the array length, the program fails                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| [`sumhash512`](#algopy.op.sumhash512)                   | sumhash512 of value A, yields [64]byte<br/>Min AVM version: 13                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [`vrf_verify`](#algopy.op.vrf_verify)                   | Verify the proof B of message A against pubkey C. Returns vrf output and verification flag.<br/>`VrfAlgorand` is the VRF used in Algorand. It is ECVRF-ED25519-SHA512-Elligator2, specified in the IETF internet draft [draft-irtf-cfrg-vrf-03](https://datatracker.ietf.org/doc/draft-irtf-cfrg-vrf/03/).                                                                                                                                                                                                                                                                                                                        |

### API

#### *class* algopy.op.AcctParamsGet

X is field F from account A. Y is 1 if A owns positive algos, else 0
Native TEAL op: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_auth_addr

**static* acct_auth_addr(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Address the account is rekeyed to.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_balance

**static* acct_balance(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Account balance in microalgos

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_incentive_eligible

**static* acct_incentive_eligible(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[bool](https://docs.python.org/3/library/functions.html#bool), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Min AVM version: 11

* **Returns tuple[bool, bool]:**
  Has this account opted into block payouts

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_last_heartbeat

**static* acct_last_heartbeat(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Min AVM version: 11

* **Returns tuple[UInt64, bool]:**
  The round number of the last block this account sent a heartbeat.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_last_proposed

**static* acct_last_proposed(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Min AVM version: 11

* **Returns tuple[UInt64, bool]:**
  The round number of the last block this account proposed.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_min_balance

**static* acct_min_balance(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Minimum required balance for account, in microalgos

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_apps_created

**static* acct_total_apps_created(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The number of existing apps created by this account.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_apps_opted_in

**static* acct_total_apps_opted_in(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The number of apps this account is opted into.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_assets

**static* acct_total_assets(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The numbers of ASAs held by this account (including ASAs this account created).

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_assets_created

**static* acct_total_assets_created(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The number of existing ASAs created by this account.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_box_bytes

**static* acct_total_box_bytes(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The total number of bytes used by this account’s app’s box keys and values.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_boxes

**static* acct_total_boxes(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The number of existing boxes created by this account’s app.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_extra_app_pages

**static* acct_total_extra_app_pages(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The number of extra app code pages used by this account.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_num_byte_slice

**static* acct_total_num_byte_slice(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The total number of byte array values allocated by this account in Global and Local States.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

##### *static* acct_total_num_uint

**static* acct_total_num_uint(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

The total number of uint64 values allocated by this account in Global and Local States.

Native TEAL opcode: [`acct_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#acct_params_get)

#### *class* algopy.op.AppGlobal

Get or modify Global app state
Native TEAL ops: [`app_global_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_del), [`app_global_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get), [`app_global_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get_ex), [`app_global_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_put)

##### *static* delete

**static* delete(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

delete key A from the global state of the current application
params: state key.

Deleting a key which is already absent has no effect on the application global state. (In particular, it does *not* cause the program to fail.)

Native TEAL opcode: [`app_global_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_del)

##### *static* get_bytes

**static* get_bytes(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

global state of the key A in the current application
params: state key. Return: value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_global_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get)

##### *static* get_ex_bytes

**static* get_ex_bytes(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

X is the global state of application A, key B. Y is 1 if key existed, else 0
params: Txn.ForeignApps offset (or, since v4, an *available* application id), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_global_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get_ex)

##### *static* get_ex_uint64

**static* get_ex_uint64(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

X is the global state of application A, key B. Y is 1 if key existed, else 0
params: Txn.ForeignApps offset (or, since v4, an *available* application id), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_global_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get_ex)

##### *static* get_uint64

**static* get_uint64(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

global state of the key A in the current application
params: state key. Return: value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_global_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_get)

##### *static* put

**static* put(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

write B to key A in the global state of the current application

Native TEAL opcode: [`app_global_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_global_put)

#### *class* algopy.op.AppLocal

Get or modify Local app state
Native TEAL ops: [`app_local_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_del), [`app_local_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get), [`app_local_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get_ex), [`app_local_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_put)

##### *static* delete

**static* delete(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

delete key B from account A’s local state of the current application
params: Txn.Accounts offset (or, since v4, an *available* account address), state key.

Deleting a key which is already absent has no effect on the application local state. (In particular, it does *not* cause the program to fail.)

Native TEAL opcode: [`app_local_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_del)

##### *static* get_bytes

**static* get_bytes(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

local state of the key B in the current application in account A
params: Txn.Accounts offset (or, since v4, an *available* account address), state key. Return: value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_local_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get)

##### *static* get_ex_bytes

**static* get_ex_bytes(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

X is the local state of application B, key C in account A. Y is 1 if key existed, else 0
params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_local_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get_ex)

##### *static* get_ex_uint64

**static* get_ex_uint64(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

X is the local state of application B, key C in account A. Y is 1 if key existed, else 0
params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset), state key. Return: did_exist flag (top of the stack, 1 if the application and key existed and 0 otherwise), value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_local_get_ex`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get_ex)

##### *static* get_uint64

**static* get_uint64(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

local state of the key B in the current application in account A
params: Txn.Accounts offset (or, since v4, an *available* account address), state key. Return: value. The value is zero (of type uint64) if the key does not exist.

Native TEAL opcode: [`app_local_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_get)

##### *static* put

**static* put(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

write C to key B in account A’s local state of the current application
params: Txn.Accounts offset (or, since v4, an *available* account address), state key, value.

Native TEAL opcode: [`app_local_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_local_put)

#### *class* algopy.op.AppParamsGet

X is field F from app A. Y is 1 if A exists, else 0 params: Txn.ForeignApps offset or an *available* app id. Return: did_exist flag (1 if the application existed and 0 otherwise), value.
Native TEAL op: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_address

**static* app_address(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Address for which this application has authority

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_approval_program

**static* app_approval_program(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Bytecode of Approval Program

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_clear_state_program

**static* app_clear_state_program(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Bytecode of Clear State Program

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_creator

**static* app_creator(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Creator address

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_extra_program_pages

**static* app_extra_program_pages(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Number of Extra Program Pages of code space

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_global_num_byte_slice

**static* app_global_num_byte_slice(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Number of byte array values allowed in Global State

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_global_num_uint

**static* app_global_num_uint(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Number of uint64 values allowed in Global State

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_local_num_byte_slice

**static* app_local_num_byte_slice(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Number of byte array values allowed in Local State

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_local_num_uint

**static* app_local_num_uint(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Number of uint64 values allowed in Local State

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

##### *static* app_version

**static* app_version(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Min AVM version: 12

* **Returns tuple[UInt64, bool]:**
  Version of the app, incremented each time the approval or clear program changes

Native TEAL opcode: [`app_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_params_get)

#### *class* algopy.op.AssetHoldingGet

X is field F from account A’s holding of asset B. Y is 1 if A is opted into B, else 0 params: Txn.Accounts offset (or, since v4, an *available* address), asset id (or, since v4, a Txn.ForeignAssets offset). Return: did_exist flag (1 if the asset existed and 0 otherwise), value.
Native TEAL op: [`asset_holding_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_holding_get)

##### *static* asset_balance

**static* asset_balance(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Amount of the asset unit held by this account

Native TEAL opcode: [`asset_holding_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_holding_get)

##### *static* asset_frozen

**static* asset_frozen(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[bool](https://docs.python.org/3/library/functions.html#bool), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Is the asset frozen or not

Native TEAL opcode: [`asset_holding_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_holding_get)

#### *class* algopy.op.AssetParamsGet

X is field F from asset A. Y is 1 if A exists, else 0 params: Txn.ForeignAssets offset (or, since v4, an *available* asset id. Return: did_exist flag (1 if the asset existed and 0 otherwise), value.
Native TEAL op: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_clawback

**static* asset_clawback(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Clawback address

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_creator

**static* asset_creator(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Creator address

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_decimals

**static* asset_decimals(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

See AssetParams.Decimals

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_default_frozen

**static* asset_default_frozen(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[bool](https://docs.python.org/3/library/functions.html#bool), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Frozen by default or not

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_freeze

**static* asset_freeze(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Freeze address

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_manager

**static* asset_manager(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Manager address

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_metadata_hash

**static* asset_metadata_hash(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Arbitrary commitment

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_name

**static* asset_name(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Asset name

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_reserve

**static* asset_reserve(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Account](api-algopy.md#algopy.Account), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Reserve address

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_total

**static* asset_total(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Total number of units of this asset

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_unit_name

**static* asset_unit_name(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Asset unit name

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

##### *static* asset_url

**static* asset_url(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

URL with additional info about the asset

Native TEAL opcode: [`asset_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#asset_params_get)

#### *class* algopy.op.Base64

Available values for the `base64` enum

##### Initialization

Initialize self.  See help(type(self)) for accurate signature.

##### \_\_add_\_

*\_\_add_\_()*

Return self+value.

##### \_\_contains_\_

*\_\_contains_\_()*

Return bool(key in self).

##### \_\_delattr_\_

*\_\_delattr_\_()*

Implement delattr(self, name).

##### \_\_dir_\_

*\_\_dir_\_()*

Default dir() implementation.

##### \_\_eq_\_

*\_\_eq_\_()*

Return self==value.

##### \_\_format_\_

*\_\_format_\_()*

Return a formatted version of the string as described by format_spec.

##### \_\_ge_\_

*\_\_ge_\_()*

Return self>=value.

##### \_\_getattribute_\_

*\_\_getattribute_\_()*

Return getattr(self, name).

##### \_\_getitem_\_

*\_\_getitem_\_()*

Return self[key].

##### \_\_getstate_\_

*\_\_getstate_\_()*

Helper for pickle.

##### \_\_gt_\_

*\_\_gt_\_()*

Return self>value.

##### \_\_hash_\_

*\_\_hash_\_()*

Return hash(self).

##### \_\_iter_\_

*\_\_iter_\_()*

Implement iter(self).

##### \_\_le_\_

*\_\_le_\_()*

Return self<=value.

##### \_\_len_\_

*\_\_len_\_()*

Return len(self).

##### \_\_lt_\_

*\_\_lt_\_()*

Return self<value.

##### \_\_mod_\_

*\_\_mod_\_()*

Return self%value.

##### \_\_mul_\_

*\_\_mul_\_()*

Return self\*value.

##### \_\_ne_\_

*\_\_ne_\_()*

Return self!=value.

##### \_\_new_\_

*\_\_new_\_()*

Create and return a new object.  See help(type) for accurate signature.

##### \_\_reduce_\_

*\_\_reduce_\_()*

Helper for pickle.

##### \_\_reduce_ex_\_

*\_\_reduce_ex_\_()*

Helper for pickle.

##### \_\_repr_\_

*\_\_repr_\_()*

Return repr(self).

##### \_\_rmod_\_

*\_\_rmod_\_()*

Return value%self.

##### \_\_rmul_\_

*\_\_rmul_\_()*

Return value\*self.

##### \_\_setattr_\_

*\_\_setattr_\_()*

Implement setattr(self, name, value).

##### \_\_sizeof_\_

*\_\_sizeof_\_()*

Return the size of the string in memory, in bytes.

##### \_\_str_\_

*\_\_str_\_()*

Return str(self).

##### capitalize

*capitalize()*

Return a capitalized version of the string.

More specifically, make the first character have upper case and the rest lower
case.

##### casefold

*casefold()*

Return a version of the string suitable for caseless comparisons.

##### center

*center()*

Return a centered string of length width.

Padding is done using the specified fill character (default is a space).

##### count

*count()*

S.count(sub[, start[, end]]) -> int

Return the number of non-overlapping occurrences of substring sub in
string S[start:end].  Optional arguments start and end are
interpreted as in slice notation.

##### encode

*encode()*

Encode the string using the codec registered for encoding.

encoding
The encoding in which to encode the string.
errors
The error handling scheme to use for encoding errors.
The default is ‘strict’ meaning that encoding errors raise a
UnicodeEncodeError.  Other possible values are ‘ignore’, ‘replace’ and
‘xmlcharrefreplace’ as well as any other name registered with
codecs.register_error that can handle UnicodeEncodeErrors.

##### endswith

*endswith()*

S.endswith(suffix[, start[, end]]) -> bool

Return True if S ends with the specified suffix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
suffix can also be a tuple of strings to try.

##### expandtabs

*expandtabs()*

Return a copy where all tab characters are expanded using spaces.

If tabsize is not given, a tab size of 8 characters is assumed.

##### find

*find()*

S.find(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### format

*format()*

S.format(\*args, \*\*kwargs) -> str

Return a formatted version of S, using substitutions from args and kwargs.
The substitutions are identified by braces (‘{’ and ‘}’).

##### format_map

*format_map()*

S.format_map(mapping) -> str

Return a formatted version of S, using substitutions from mapping.
The substitutions are identified by braces (‘{’ and ‘}’).

##### index

*index()*

S.index(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### isalnum

*isalnum()*

Return True if the string is an alpha-numeric string, False otherwise.

A string is alpha-numeric if all characters in the string are alpha-numeric and
there is at least one character in the string.

##### isalpha

*isalpha()*

Return True if the string is an alphabetic string, False otherwise.

A string is alphabetic if all characters in the string are alphabetic and there
is at least one character in the string.

##### isascii

*isascii()*

Return True if all characters in the string are ASCII, False otherwise.

ASCII characters have code points in the range U+0000-U+007F.
Empty string is ASCII too.

##### isdecimal

*isdecimal()*

Return True if the string is a decimal string, False otherwise.

A string is a decimal string if all characters in the string are decimal and
there is at least one character in the string.

##### isdigit

*isdigit()*

Return True if the string is a digit string, False otherwise.

A string is a digit string if all characters in the string are digits and there
is at least one character in the string.

##### isidentifier

*isidentifier()*

Return True if the string is a valid Python identifier, False otherwise.

Call keyword.iskeyword(s) to test whether string s is a reserved identifier,
such as “def” or “class”.

##### islower

*islower()*

Return True if the string is a lowercase string, False otherwise.

A string is lowercase if all cased characters in the string are lowercase and
there is at least one cased character in the string.

##### isnumeric

*isnumeric()*

Return True if the string is a numeric string, False otherwise.

A string is numeric if all characters in the string are numeric and there is at
least one character in the string.

##### isprintable

*isprintable()*

Return True if the string is printable, False otherwise.

A string is printable if all of its characters are considered printable in
repr() or if it is empty.

##### isspace

*isspace()*

Return True if the string is a whitespace string, False otherwise.

A string is whitespace if all characters in the string are whitespace and there
is at least one character in the string.

##### istitle

*istitle()*

Return True if the string is a title-cased string, False otherwise.

In a title-cased string, upper- and title-case characters may only
follow uncased characters and lowercase characters only cased ones.

##### isupper

*isupper()*

Return True if the string is an uppercase string, False otherwise.

A string is uppercase if all cased characters in the string are uppercase and
there is at least one cased character in the string.

##### join

*join()*

Concatenate any number of strings.

The string whose method is called is inserted in between each given string.
The result is returned as a new string.

Example: ‘.’.join([‘ab’, ‘pq’, ‘rs’]) -> ‘ab.pq.rs’

##### ljust

*ljust()*

Return a left-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### lower

*lower()*

Return a copy of the string converted to lowercase.

##### lstrip

*lstrip()*

Return a copy of the string with leading whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### partition

*partition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string.  If the separator is found,
returns a 3-tuple containing the part before the separator, the separator
itself, and the part after it.

If the separator is not found, returns a 3-tuple containing the original string
and two empty strings.

##### removeprefix

*removeprefix()*

Return a str with the given prefix string removed if present.

If the string starts with the prefix string, return string[len(prefix):].
Otherwise, return a copy of the original string.

##### removesuffix

*removesuffix()*

Return a str with the given suffix string removed if present.

If the string ends with the suffix string and that suffix is not empty,
return string[:-len(suffix)]. Otherwise, return a copy of the original
string.

##### replace

*replace()*

Return a copy with all occurrences of substring old replaced by new.

count
Maximum number of occurrences to replace.
-1 (the default value) means replace all occurrences.

If the optional argument count is given, only the first count occurrences are
replaced.

##### rfind

*rfind()*

S.rfind(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### rindex

*rindex()*

S.rindex(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### rjust

*rjust()*

Return a right-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### rpartition

*rpartition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string, starting at the end. If
the separator is found, returns a 3-tuple containing the part before the
separator, the separator itself, and the part after it.

If the separator is not found, returns a 3-tuple containing two empty strings
and the original string.

##### rsplit

*rsplit()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the end of the string and works to the front.

##### rstrip

*rstrip()*

Return a copy of the string with trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### split

*split()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the front of the string and works to the end.

Note, str.split() is mainly useful for data that has been intentionally
delimited.  With natural text that includes punctuation, consider using
the regular expression module.

##### splitlines

*splitlines()*

Return a list of the lines in the string, breaking at line boundaries.

Line breaks are not included in the resulting list unless keepends is given and
true.

##### startswith

*startswith()*

S.startswith(prefix[, start[, end]]) -> bool

Return True if S starts with the specified prefix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
prefix can also be a tuple of strings to try.

##### strip

*strip()*

Return a copy of the string with leading and trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### swapcase

*swapcase()*

Convert uppercase characters to lowercase and lowercase characters to uppercase.

##### title

*title()*

Return a version of the string where each word is titlecased.

More specifically, words start with uppercased characters and all remaining
cased characters have lower case.

##### translate

*translate()*

Replace each character in the string using the given translation table.

table
Translation table, which must be a mapping of Unicode ordinals to
Unicode ordinals, strings, or None.

The table must implement lookup/indexing via **getitem**, for instance a
dictionary or list.  If this operation raises LookupError, the character is
left untouched.  Characters mapped to None are deleted.

##### upper

*upper()*

Return a copy of the string converted to uppercase.

##### zfill

*zfill()*

Pad a numeric string with zeros on the left, to fill a field of the given width.

The string is never truncated.

#### *class* algopy.op.Block

field F of block A. Fail unless A falls between txn.LastValid-1002 and txn.FirstValid (exclusive)
Native TEAL op: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_bonus

**static* blk_bonus(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_branch

**static* blk_branch(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_fee_sink

**static* blk_fee_sink(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_fees_collected

**static* blk_fees_collected(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_proposer

**static* blk_proposer(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_proposer_payout

**static* blk_proposer_payout(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_protocol

**static* blk_protocol(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_seed

**static* blk_seed(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_timestamp

**static* blk_timestamp(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

##### *static* blk_txn_counter

**static* blk_txn_counter(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Min AVM version: 11

Native TEAL opcode: [`block`](https://dev.algorand.co/reference/algorand-teal/opcodes/#block)

#### *class* algopy.op.Box

Get or modify box state
Native TEAL ops: [`box_create`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_create), [`box_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_del), [`box_extract`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_extract), [`box_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_get), [`box_len`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_len), [`box_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_put), [`box_replace`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_replace), [`box_resize`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_resize), [`box_splice`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_splice)

##### *static* create

**static* create(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

create a box named A, of length B. Fail if the name A is empty or B exceeds 32,768. Returns 0 if A already existed, else 1
Newly created boxes are filled with 0 bytes. `box_create` will fail if the referenced box already exists with a different size. Otherwise, existing boxes are unchanged by `box_create`.

Native TEAL opcode: [`box_create`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_create)

##### *static* delete

**static* delete(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

delete box named A if it exists. Return 1 if A existed, 0 otherwise

Native TEAL opcode: [`box_del`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_del)

##### *static* extract

**static* extract(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

read C bytes from box A, starting at offset B. Fail if A does not exist, or the byte range is outside A’s size.

Native TEAL opcode: [`box_extract`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_extract)

##### *static* get

**static* get(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

X is the contents of box A if A exists, else ‘’. Y is 1 if A exists, else 0.
For boxes that exceed 4,096 bytes, consider `box_create`, `box_extract`, and `box_replace`

Native TEAL opcode: [`box_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_get)

##### *static* length

**static* length(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

X is the length of box A if A exists, else 0. Y is 1 if A exists, else 0.

Native TEAL opcode: [`box_len`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_len)

##### *static* put

**static* put(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

replaces the contents of box A with byte-array B. Fails if A exists and len(B) != len(box A). Creates A if it does not exist
For boxes that exceed 4,096 bytes, consider `box_create`, `box_extract`, and `box_replace`

Native TEAL opcode: [`box_put`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_put)

##### *static* replace

**static* replace(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

write byte-array C into box A, starting at offset B. Fail if A does not exist, or the byte range is outside A’s size.

Native TEAL opcode: [`box_replace`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_replace)

##### *static* resize

**static* resize(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

change the size of box named A to be of length B, adding zero bytes to end or removing bytes from the end, as needed. Fail if the name A is empty, A is not an existing box, or B exceeds 32,768.

Native TEAL opcode: [`box_resize`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_resize)

##### *static* splice

**static* splice(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), d: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

set box A to contain its previous bytes up to index B, followed by D, followed by the original bytes of A that began at index B+C.
Boxes are of constant length. If C < len(D), then len(D)-C bytes will be removed from the end. If C > len(D), zero bytes will be appended to the end to reach the box length.

Native TEAL opcode: [`box_splice`](https://dev.algorand.co/reference/algorand-teal/opcodes/#box_splice)

#### *class* algopy.op.EC

Available values for the `EC` enum

##### Initialization

Initialize self.  See help(type(self)) for accurate signature.

##### BLS12_381g1 *: [algopy.op.EC]

*BLS12_381g1 *: [algopy.op.EC](#algopy.op.EC)**

Ellipsis

G1 of the BLS 12-381 curve. Points encoded as 48 byte X following by 48 byte Y

##### BLS12_381g2 *: [algopy.op.EC]

*BLS12_381g2 *: [algopy.op.EC](#algopy.op.EC)**

Ellipsis

G2 of the BLS 12-381 curve. Points encoded as 96 byte X following by 96 byte Y

##### BN254g1 *: [algopy.op.EC]

*BN254g1 *: [algopy.op.EC](#algopy.op.EC)**

Ellipsis

G1 of the BN254 curve. Points encoded as 32 byte X following by 32 byte Y

##### BN254g2 *: [algopy.op.EC]

*BN254g2 *: [algopy.op.EC](#algopy.op.EC)**

Ellipsis

G2 of the BN254 curve. Points encoded as 64 byte X following by 64 byte Y

##### \_\_add_\_

*\_\_add_\_()*

Return self+value.

##### \_\_contains_\_

*\_\_contains_\_()*

Return bool(key in self).

##### \_\_delattr_\_

*\_\_delattr_\_()*

Implement delattr(self, name).

##### \_\_dir_\_

*\_\_dir_\_()*

Default dir() implementation.

##### \_\_eq_\_

*\_\_eq_\_()*

Return self==value.

##### \_\_format_\_

*\_\_format_\_()*

Return a formatted version of the string as described by format_spec.

##### \_\_ge_\_

*\_\_ge_\_()*

Return self>=value.

##### \_\_getattribute_\_

*\_\_getattribute_\_()*

Return getattr(self, name).

##### \_\_getitem_\_

*\_\_getitem_\_()*

Return self[key].

##### \_\_getstate_\_

*\_\_getstate_\_()*

Helper for pickle.

##### \_\_gt_\_

*\_\_gt_\_()*

Return self>value.

##### \_\_hash_\_

*\_\_hash_\_()*

Return hash(self).

##### \_\_iter_\_

*\_\_iter_\_()*

Implement iter(self).

##### \_\_le_\_

*\_\_le_\_()*

Return self<=value.

##### \_\_len_\_

*\_\_len_\_()*

Return len(self).

##### \_\_lt_\_

*\_\_lt_\_()*

Return self<value.

##### \_\_mod_\_

*\_\_mod_\_()*

Return self%value.

##### \_\_mul_\_

*\_\_mul_\_()*

Return self\*value.

##### \_\_ne_\_

*\_\_ne_\_()*

Return self!=value.

##### \_\_new_\_

*\_\_new_\_()*

Create and return a new object.  See help(type) for accurate signature.

##### \_\_reduce_\_

*\_\_reduce_\_()*

Helper for pickle.

##### \_\_reduce_ex_\_

*\_\_reduce_ex_\_()*

Helper for pickle.

##### \_\_repr_\_

*\_\_repr_\_()*

Return repr(self).

##### \_\_rmod_\_

*\_\_rmod_\_()*

Return value%self.

##### \_\_rmul_\_

*\_\_rmul_\_()*

Return value\*self.

##### \_\_setattr_\_

*\_\_setattr_\_()*

Implement setattr(self, name, value).

##### \_\_sizeof_\_

*\_\_sizeof_\_()*

Return the size of the string in memory, in bytes.

##### \_\_str_\_

*\_\_str_\_()*

Return str(self).

##### capitalize

*capitalize()*

Return a capitalized version of the string.

More specifically, make the first character have upper case and the rest lower
case.

##### casefold

*casefold()*

Return a version of the string suitable for caseless comparisons.

##### center

*center()*

Return a centered string of length width.

Padding is done using the specified fill character (default is a space).

##### count

*count()*

S.count(sub[, start[, end]]) -> int

Return the number of non-overlapping occurrences of substring sub in
string S[start:end].  Optional arguments start and end are
interpreted as in slice notation.

##### encode

*encode()*

Encode the string using the codec registered for encoding.

encoding
The encoding in which to encode the string.
errors
The error handling scheme to use for encoding errors.
The default is ‘strict’ meaning that encoding errors raise a
UnicodeEncodeError.  Other possible values are ‘ignore’, ‘replace’ and
‘xmlcharrefreplace’ as well as any other name registered with
codecs.register_error that can handle UnicodeEncodeErrors.

##### endswith

*endswith()*

S.endswith(suffix[, start[, end]]) -> bool

Return True if S ends with the specified suffix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
suffix can also be a tuple of strings to try.

##### expandtabs

*expandtabs()*

Return a copy where all tab characters are expanded using spaces.

If tabsize is not given, a tab size of 8 characters is assumed.

##### find

*find()*

S.find(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### format

*format()*

S.format(\*args, \*\*kwargs) -> str

Return a formatted version of S, using substitutions from args and kwargs.
The substitutions are identified by braces (‘{’ and ‘}’).

##### format_map

*format_map()*

S.format_map(mapping) -> str

Return a formatted version of S, using substitutions from mapping.
The substitutions are identified by braces (‘{’ and ‘}’).

##### index

*index()*

S.index(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### isalnum

*isalnum()*

Return True if the string is an alpha-numeric string, False otherwise.

A string is alpha-numeric if all characters in the string are alpha-numeric and
there is at least one character in the string.

##### isalpha

*isalpha()*

Return True if the string is an alphabetic string, False otherwise.

A string is alphabetic if all characters in the string are alphabetic and there
is at least one character in the string.

##### isascii

*isascii()*

Return True if all characters in the string are ASCII, False otherwise.

ASCII characters have code points in the range U+0000-U+007F.
Empty string is ASCII too.

##### isdecimal

*isdecimal()*

Return True if the string is a decimal string, False otherwise.

A string is a decimal string if all characters in the string are decimal and
there is at least one character in the string.

##### isdigit

*isdigit()*

Return True if the string is a digit string, False otherwise.

A string is a digit string if all characters in the string are digits and there
is at least one character in the string.

##### isidentifier

*isidentifier()*

Return True if the string is a valid Python identifier, False otherwise.

Call keyword.iskeyword(s) to test whether string s is a reserved identifier,
such as “def” or “class”.

##### islower

*islower()*

Return True if the string is a lowercase string, False otherwise.

A string is lowercase if all cased characters in the string are lowercase and
there is at least one cased character in the string.

##### isnumeric

*isnumeric()*

Return True if the string is a numeric string, False otherwise.

A string is numeric if all characters in the string are numeric and there is at
least one character in the string.

##### isprintable

*isprintable()*

Return True if the string is printable, False otherwise.

A string is printable if all of its characters are considered printable in
repr() or if it is empty.

##### isspace

*isspace()*

Return True if the string is a whitespace string, False otherwise.

A string is whitespace if all characters in the string are whitespace and there
is at least one character in the string.

##### istitle

*istitle()*

Return True if the string is a title-cased string, False otherwise.

In a title-cased string, upper- and title-case characters may only
follow uncased characters and lowercase characters only cased ones.

##### isupper

*isupper()*

Return True if the string is an uppercase string, False otherwise.

A string is uppercase if all cased characters in the string are uppercase and
there is at least one cased character in the string.

##### join

*join()*

Concatenate any number of strings.

The string whose method is called is inserted in between each given string.
The result is returned as a new string.

Example: ‘.’.join([‘ab’, ‘pq’, ‘rs’]) -> ‘ab.pq.rs’

##### ljust

*ljust()*

Return a left-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### lower

*lower()*

Return a copy of the string converted to lowercase.

##### lstrip

*lstrip()*

Return a copy of the string with leading whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### partition

*partition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string.  If the separator is found,
returns a 3-tuple containing the part before the separator, the separator
itself, and the part after it.

If the separator is not found, returns a 3-tuple containing the original string
and two empty strings.

##### removeprefix

*removeprefix()*

Return a str with the given prefix string removed if present.

If the string starts with the prefix string, return string[len(prefix):].
Otherwise, return a copy of the original string.

##### removesuffix

*removesuffix()*

Return a str with the given suffix string removed if present.

If the string ends with the suffix string and that suffix is not empty,
return string[:-len(suffix)]. Otherwise, return a copy of the original
string.

##### replace

*replace()*

Return a copy with all occurrences of substring old replaced by new.

count
Maximum number of occurrences to replace.
-1 (the default value) means replace all occurrences.

If the optional argument count is given, only the first count occurrences are
replaced.

##### rfind

*rfind()*

S.rfind(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### rindex

*rindex()*

S.rindex(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### rjust

*rjust()*

Return a right-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### rpartition

*rpartition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string, starting at the end. If
the separator is found, returns a 3-tuple containing the part before the
separator, the separator itself, and the part after it.

If the separator is not found, returns a 3-tuple containing two empty strings
and the original string.

##### rsplit

*rsplit()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the end of the string and works to the front.

##### rstrip

*rstrip()*

Return a copy of the string with trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### split

*split()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the front of the string and works to the end.

Note, str.split() is mainly useful for data that has been intentionally
delimited.  With natural text that includes punctuation, consider using
the regular expression module.

##### splitlines

*splitlines()*

Return a list of the lines in the string, breaking at line boundaries.

Line breaks are not included in the resulting list unless keepends is given and
true.

##### startswith

*startswith()*

S.startswith(prefix[, start[, end]]) -> bool

Return True if S starts with the specified prefix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
prefix can also be a tuple of strings to try.

##### strip

*strip()*

Return a copy of the string with leading and trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### swapcase

*swapcase()*

Convert uppercase characters to lowercase and lowercase characters to uppercase.

##### title

*title()*

Return a version of the string where each word is titlecased.

More specifically, words start with uppercased characters and all remaining
cased characters have lower case.

##### translate

*translate()*

Replace each character in the string using the given translation table.

table
Translation table, which must be a mapping of Unicode ordinals to
Unicode ordinals, strings, or None.

The table must implement lookup/indexing via **getitem**, for instance a
dictionary or list.  If this operation raises LookupError, the character is
left untouched.  Characters mapped to None are deleted.

##### upper

*upper()*

Return a copy of the string converted to uppercase.

##### zfill

*zfill()*

Pad a numeric string with zeros on the left, to fill a field of the given width.

The string is never truncated.

#### *class* algopy.op.ECDSA

Available values for the `ECDSA` enum

##### Initialization

Initialize self.  See help(type(self)) for accurate signature.

##### Secp256k1 *: [algopy.op.ECDSA]

*Secp256k1 *: [algopy.op.ECDSA](#algopy.op.ECDSA)**

Ellipsis

secp256k1 curve, used in Bitcoin

##### Secp256r1 *: [algopy.op.ECDSA]

*Secp256r1 *: [algopy.op.ECDSA](#algopy.op.ECDSA)**

Ellipsis

secp256r1 curve, NIST standard

##### \_\_add_\_

*\_\_add_\_()*

Return self+value.

##### \_\_contains_\_

*\_\_contains_\_()*

Return bool(key in self).

##### \_\_delattr_\_

*\_\_delattr_\_()*

Implement delattr(self, name).

##### \_\_dir_\_

*\_\_dir_\_()*

Default dir() implementation.

##### \_\_eq_\_

*\_\_eq_\_()*

Return self==value.

##### \_\_format_\_

*\_\_format_\_()*

Return a formatted version of the string as described by format_spec.

##### \_\_ge_\_

*\_\_ge_\_()*

Return self>=value.

##### \_\_getattribute_\_

*\_\_getattribute_\_()*

Return getattr(self, name).

##### \_\_getitem_\_

*\_\_getitem_\_()*

Return self[key].

##### \_\_getstate_\_

*\_\_getstate_\_()*

Helper for pickle.

##### \_\_gt_\_

*\_\_gt_\_()*

Return self>value.

##### \_\_hash_\_

*\_\_hash_\_()*

Return hash(self).

##### \_\_iter_\_

*\_\_iter_\_()*

Implement iter(self).

##### \_\_le_\_

*\_\_le_\_()*

Return self<=value.

##### \_\_len_\_

*\_\_len_\_()*

Return len(self).

##### \_\_lt_\_

*\_\_lt_\_()*

Return self<value.

##### \_\_mod_\_

*\_\_mod_\_()*

Return self%value.

##### \_\_mul_\_

*\_\_mul_\_()*

Return self\*value.

##### \_\_ne_\_

*\_\_ne_\_()*

Return self!=value.

##### \_\_new_\_

*\_\_new_\_()*

Create and return a new object.  See help(type) for accurate signature.

##### \_\_reduce_\_

*\_\_reduce_\_()*

Helper for pickle.

##### \_\_reduce_ex_\_

*\_\_reduce_ex_\_()*

Helper for pickle.

##### \_\_repr_\_

*\_\_repr_\_()*

Return repr(self).

##### \_\_rmod_\_

*\_\_rmod_\_()*

Return value%self.

##### \_\_rmul_\_

*\_\_rmul_\_()*

Return value\*self.

##### \_\_setattr_\_

*\_\_setattr_\_()*

Implement setattr(self, name, value).

##### \_\_sizeof_\_

*\_\_sizeof_\_()*

Return the size of the string in memory, in bytes.

##### \_\_str_\_

*\_\_str_\_()*

Return str(self).

##### capitalize

*capitalize()*

Return a capitalized version of the string.

More specifically, make the first character have upper case and the rest lower
case.

##### casefold

*casefold()*

Return a version of the string suitable for caseless comparisons.

##### center

*center()*

Return a centered string of length width.

Padding is done using the specified fill character (default is a space).

##### count

*count()*

S.count(sub[, start[, end]]) -> int

Return the number of non-overlapping occurrences of substring sub in
string S[start:end].  Optional arguments start and end are
interpreted as in slice notation.

##### encode

*encode()*

Encode the string using the codec registered for encoding.

encoding
The encoding in which to encode the string.
errors
The error handling scheme to use for encoding errors.
The default is ‘strict’ meaning that encoding errors raise a
UnicodeEncodeError.  Other possible values are ‘ignore’, ‘replace’ and
‘xmlcharrefreplace’ as well as any other name registered with
codecs.register_error that can handle UnicodeEncodeErrors.

##### endswith

*endswith()*

S.endswith(suffix[, start[, end]]) -> bool

Return True if S ends with the specified suffix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
suffix can also be a tuple of strings to try.

##### expandtabs

*expandtabs()*

Return a copy where all tab characters are expanded using spaces.

If tabsize is not given, a tab size of 8 characters is assumed.

##### find

*find()*

S.find(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### format

*format()*

S.format(\*args, \*\*kwargs) -> str

Return a formatted version of S, using substitutions from args and kwargs.
The substitutions are identified by braces (‘{’ and ‘}’).

##### format_map

*format_map()*

S.format_map(mapping) -> str

Return a formatted version of S, using substitutions from mapping.
The substitutions are identified by braces (‘{’ and ‘}’).

##### index

*index()*

S.index(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### isalnum

*isalnum()*

Return True if the string is an alpha-numeric string, False otherwise.

A string is alpha-numeric if all characters in the string are alpha-numeric and
there is at least one character in the string.

##### isalpha

*isalpha()*

Return True if the string is an alphabetic string, False otherwise.

A string is alphabetic if all characters in the string are alphabetic and there
is at least one character in the string.

##### isascii

*isascii()*

Return True if all characters in the string are ASCII, False otherwise.

ASCII characters have code points in the range U+0000-U+007F.
Empty string is ASCII too.

##### isdecimal

*isdecimal()*

Return True if the string is a decimal string, False otherwise.

A string is a decimal string if all characters in the string are decimal and
there is at least one character in the string.

##### isdigit

*isdigit()*

Return True if the string is a digit string, False otherwise.

A string is a digit string if all characters in the string are digits and there
is at least one character in the string.

##### isidentifier

*isidentifier()*

Return True if the string is a valid Python identifier, False otherwise.

Call keyword.iskeyword(s) to test whether string s is a reserved identifier,
such as “def” or “class”.

##### islower

*islower()*

Return True if the string is a lowercase string, False otherwise.

A string is lowercase if all cased characters in the string are lowercase and
there is at least one cased character in the string.

##### isnumeric

*isnumeric()*

Return True if the string is a numeric string, False otherwise.

A string is numeric if all characters in the string are numeric and there is at
least one character in the string.

##### isprintable

*isprintable()*

Return True if the string is printable, False otherwise.

A string is printable if all of its characters are considered printable in
repr() or if it is empty.

##### isspace

*isspace()*

Return True if the string is a whitespace string, False otherwise.

A string is whitespace if all characters in the string are whitespace and there
is at least one character in the string.

##### istitle

*istitle()*

Return True if the string is a title-cased string, False otherwise.

In a title-cased string, upper- and title-case characters may only
follow uncased characters and lowercase characters only cased ones.

##### isupper

*isupper()*

Return True if the string is an uppercase string, False otherwise.

A string is uppercase if all cased characters in the string are uppercase and
there is at least one cased character in the string.

##### join

*join()*

Concatenate any number of strings.

The string whose method is called is inserted in between each given string.
The result is returned as a new string.

Example: ‘.’.join([‘ab’, ‘pq’, ‘rs’]) -> ‘ab.pq.rs’

##### ljust

*ljust()*

Return a left-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### lower

*lower()*

Return a copy of the string converted to lowercase.

##### lstrip

*lstrip()*

Return a copy of the string with leading whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### partition

*partition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string.  If the separator is found,
returns a 3-tuple containing the part before the separator, the separator
itself, and the part after it.

If the separator is not found, returns a 3-tuple containing the original string
and two empty strings.

##### removeprefix

*removeprefix()*

Return a str with the given prefix string removed if present.

If the string starts with the prefix string, return string[len(prefix):].
Otherwise, return a copy of the original string.

##### removesuffix

*removesuffix()*

Return a str with the given suffix string removed if present.

If the string ends with the suffix string and that suffix is not empty,
return string[:-len(suffix)]. Otherwise, return a copy of the original
string.

##### replace

*replace()*

Return a copy with all occurrences of substring old replaced by new.

count
Maximum number of occurrences to replace.
-1 (the default value) means replace all occurrences.

If the optional argument count is given, only the first count occurrences are
replaced.

##### rfind

*rfind()*

S.rfind(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### rindex

*rindex()*

S.rindex(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### rjust

*rjust()*

Return a right-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### rpartition

*rpartition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string, starting at the end. If
the separator is found, returns a 3-tuple containing the part before the
separator, the separator itself, and the part after it.

If the separator is not found, returns a 3-tuple containing two empty strings
and the original string.

##### rsplit

*rsplit()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the end of the string and works to the front.

##### rstrip

*rstrip()*

Return a copy of the string with trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### split

*split()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the front of the string and works to the end.

Note, str.split() is mainly useful for data that has been intentionally
delimited.  With natural text that includes punctuation, consider using
the regular expression module.

##### splitlines

*splitlines()*

Return a list of the lines in the string, breaking at line boundaries.

Line breaks are not included in the resulting list unless keepends is given and
true.

##### startswith

*startswith()*

S.startswith(prefix[, start[, end]]) -> bool

Return True if S starts with the specified prefix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
prefix can also be a tuple of strings to try.

##### strip

*strip()*

Return a copy of the string with leading and trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### swapcase

*swapcase()*

Convert uppercase characters to lowercase and lowercase characters to uppercase.

##### title

*title()*

Return a version of the string where each word is titlecased.

More specifically, words start with uppercased characters and all remaining
cased characters have lower case.

##### translate

*translate()*

Replace each character in the string using the given translation table.

table
Translation table, which must be a mapping of Unicode ordinals to
Unicode ordinals, strings, or None.

The table must implement lookup/indexing via **getitem**, for instance a
dictionary or list.  If this operation raises LookupError, the character is
left untouched.  Characters mapped to None are deleted.

##### upper

*upper()*

Return a copy of the string converted to uppercase.

##### zfill

*zfill()*

Pad a numeric string with zeros on the left, to fill a field of the given width.

The string is never truncated.

#### *class* algopy.op.EllipticCurve

Elliptic Curve functions
Native TEAL ops: [`ec_add`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_add), [`ec_map_to`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_map_to), [`ec_multi_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_multi_scalar_mul), [`ec_pairing_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_pairing_check), [`ec_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_scalar_mul), [`ec_subgroup_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_subgroup_check)

##### *static* add

**static* add(g: [algopy.op.EC](#algopy.op.EC), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

for curve points A and B, return the curve point A + B
A and B are curve points in affine representation: field element X concatenated with field element Y. Field element `Z` is encoded as follows.
For the base field elements (Fp), `Z` is encoded as a big-endian number and must be lower than the field modulus.
For the quadratic field extension (Fp2), `Z` is encoded as the concatenation of the individual encoding of the coefficients. For an Fp2 element of the form `Z = Z0 + Z1 i`, where `i` is a formal quadratic non-residue, the encoding of Z is the concatenation of the encoding of `Z0` and `Z1` in this order. (`Z0` and `Z1` must be less than the field modulus).

The point at infinity is encoded as `(X,Y) = (0,0)`.
Groups G1 and G2 are denoted additively.

Fails if A or B is not in G.
A and/or B are allowed to be the point at infinity.
Does *not* check if A and B are in the main prime-order subgroup.

* **Parameters:**
  **g** ([*EC*](#algopy.op.EC)) – curve index

Native TEAL opcode: [`ec_add`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_add)

##### *static* map_to

**static* map_to(g: [algopy.op.EC](#algopy.op.EC), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

maps field element A to group G
BN254 points are mapped by the SVDW map. BLS12-381 points are mapped by the SSWU map.
G1 element inputs are base field elements and G2 element inputs are quadratic field elements, with nearly the same encoding rules (for field elements) as defined in `ec_add`. There is one difference of encoding rule: G1 element inputs do not need to be 0-padded if they fit in less than 32 bytes for BN254 and less than 48 bytes for BLS12-381. (As usual, the empty byte array represents 0.) G2 elements inputs need to be always have the required size.

* **Parameters:**
  **g** ([*EC*](#algopy.op.EC)) – curve index

Native TEAL opcode: [`ec_map_to`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_map_to)

##### *static* pairing_check

**static* pairing_check(g: [algopy.op.EC](#algopy.op.EC), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

1 if the product of the pairing of each point in A with its respective point in B is equal to the identity element of the target group Gt, else 0
A and B are concatenated points, encoded and checked as described in `ec_add`. A contains points of the group G, B contains points of the associated group (G2 if G is G1, and vice versa). Fails if A and B have a different number of points, or if any point is not in its described group or outside the main prime-order subgroup - a stronger condition than other opcodes. AVM values are limited to 4096 bytes, so `ec_pairing_check` is limited by the size of the points in the groups being operated upon.

* **Parameters:**
  **g** ([*EC*](#algopy.op.EC)) – curve index

Native TEAL opcode: [`ec_pairing_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_pairing_check)

##### *static* scalar_mul

**static* scalar_mul(g: [algopy.op.EC](#algopy.op.EC), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

for curve point A and scalar B, return the curve point BA, the point A multiplied by the scalar B.
A is a curve point encoded and checked as described in `ec_add`. Scalar B is interpreted as a big-endian unsigned integer. Fails if B exceeds 32 bytes.

* **Parameters:**
  **g** ([*EC*](#algopy.op.EC)) – curve index

Native TEAL opcode: [`ec_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_scalar_mul)

##### *static* scalar_mul_multi

**static* scalar_mul_multi(g: [algopy.op.EC](#algopy.op.EC), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

for curve points A and scalars B, return curve point B0A0 + B1A1 + B2A2 + … + BnAn
A is a list of concatenated points, encoded and checked as described in `ec_add`. B is a list of concatenated scalars which, unlike ec_scalar_mul, must all be exactly 32 bytes long.
The name `ec_multi_scalar_mul` was chosen to reflect common usage, but a more consistent name would be `ec_multi_scalar_mul`. AVM values are limited to 4096 bytes, so `ec_multi_scalar_mul` is limited by the size of the points in the group being operated upon.

* **Parameters:**
  **g** ([*EC*](#algopy.op.EC)) – curve index

Native TEAL opcode: [`ec_multi_scalar_mul`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_multi_scalar_mul)

##### *static* subgroup_check

**static* subgroup_check(g: [algopy.op.EC](#algopy.op.EC), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

1 if A is in the main prime-order subgroup of G (including the point at infinity) else 0. Program fails if A is not in G at all.

* **Parameters:**
  **g** ([*EC*](#algopy.op.EC)) – curve index

Native TEAL opcode: [`ec_subgroup_check`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ec_subgroup_check)

#### *class* algopy.op.GITxn

Get values for inner transaction in the last group submitted
Native TEAL ops: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* accounts

**static* accounts(t: [int](https://docs.python.org/3/library/functions.html#int), a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  Accounts listed in the ApplicationCall transaction

Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* amount

**static* amount(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  microalgos

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* application_args

**static* application_args(t: [int](https://docs.python.org/3/library/functions.html#int), a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Arguments passed to the application in the ApplicationCall transaction

Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* application_id

**static* application_id(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Application:**
  ApplicationID from ApplicationCall transaction

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* applications

**static* applications(t: [int](https://docs.python.org/3/library/functions.html#int), a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Application:**
  Foreign Apps listed in the ApplicationCall transaction

Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* approval_program

**static* approval_program(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Approval program

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* approval_program_pages

**static* approval_program_pages(t: [int](https://docs.python.org/3/library/functions.html#int), a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Approval Program as an array of pages

Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* asset_amount

**static* asset_amount(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  value in Asset’s units

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* asset_close_to

**static* asset_close_to(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* asset_receiver

**static* asset_receiver(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* asset_sender

**static* asset_sender(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address. Source of assets if Sender is the Asset’s Clawback address.

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* assets

**static* assets(t: [int](https://docs.python.org/3/library/functions.html#int), a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Asset:**
  Foreign Assets listed in the ApplicationCall transaction

Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* clear_state_program

**static* clear_state_program(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Clear state program

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* clear_state_program_pages

**static* clear_state_program_pages(t: [int](https://docs.python.org/3/library/functions.html#int), a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  ClearState Program as an array of pages

Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* close_remainder_to

**static* close_remainder_to(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset

**static* config_asset(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Asset:**
  Asset ID in asset config transaction

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_clawback

**static* config_asset_clawback(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_decimals

**static* config_asset_decimals(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of digits to display after the decimal place when displaying the asset

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_default_frozen

**static* config_asset_default_frozen(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns bool:**
  Whether the asset’s slots are frozen by default or not, 0 or 1

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_freeze

**static* config_asset_freeze(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_manager

**static* config_asset_manager(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_metadata_hash

**static* config_asset_metadata_hash(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  32 byte commitment to unspecified asset metadata

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_name

**static* config_asset_name(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  The asset name

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_reserve

**static* config_asset_reserve(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_total

**static* config_asset_total(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Total number of units of this asset created

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_unit_name

**static* config_asset_unit_name(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Unit name of the asset

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* config_asset_url

**static* config_asset_url(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  URL

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* created_application_id

**static* created_application_id(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Application:**
  ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* created_asset_id

**static* created_asset_id(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Asset:**
  Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* extra_program_pages

**static* extra_program_pages(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* fee

**static* fee(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  microalgos

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* first_valid

**static* first_valid(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  round number

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* first_valid_time

**static* first_valid_time(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  UNIX timestamp of block before txn.FirstValid. Fails if negative

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* freeze_asset

**static* freeze_asset(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Asset:**
  Asset ID being frozen or un-frozen

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* freeze_asset_account

**static* freeze_asset_account(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address of the account whose asset slot is being frozen or un-frozen

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* freeze_asset_frozen

**static* freeze_asset_frozen(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns bool:**
  The new frozen value, 0 or 1

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* global_num_byte_slice

**static* global_num_byte_slice(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of global state byteslices in ApplicationCall

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* global_num_uint

**static* global_num_uint(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of global state integers in ApplicationCall

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* group_index

**static* group_index(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* last_log

**static* last_log(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  The last message emitted. Empty bytes if none were emitted. Application mode only

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* last_valid

**static* last_valid(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  round number

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* lease

**static* lease(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  32 byte lease value

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* local_num_byte_slice

**static* local_num_byte_slice(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of local state byteslices in ApplicationCall

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* local_num_uint

**static* local_num_uint(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of local state integers in ApplicationCall

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* logs

**static* logs(t: [int](https://docs.python.org/3/library/functions.html#int), a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Log messages emitted by an application call (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gitxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxna), [`gitxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxnas)

##### *static* nonparticipation

**static* nonparticipation(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns bool:**
  Marks an account nonparticipating for rewards

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* note

**static* note(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Any data up to 1024 bytes

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* num_accounts

**static* num_accounts(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of Accounts

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* num_app_args

**static* num_app_args(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of ApplicationArgs

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* num_applications

**static* num_applications(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of Applications

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* num_approval_program_pages

**static* num_approval_program_pages(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of Approval Program pages

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* num_assets

**static* num_assets(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of Assets

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* num_clear_state_program_pages

**static* num_clear_state_program_pages(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of ClearState Program pages

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* num_logs

**static* num_logs(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Number of Logs (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* on_completion

**static* on_completion(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns OnCompleteAction:**
  ApplicationCall transaction on completion action

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* receiver

**static* receiver(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* reject_version

**static* reject_version(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Min AVM version: 12

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Application version for which the txn must reject

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* rekey_to

**static* rekey_to(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte Sender’s new AuthAddr

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* selection_pk

**static* selection_pk(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* sender

**static* sender(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Account:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* state_proof_pk

**static* state_proof_pk(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  State proof public key

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* tx_id

**static* tx_id(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  The computed ID for this transaction. 32 bytes.

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* type

**static* type(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  Transaction type as bytes

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* type_enum

**static* type_enum(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns TransactionType:**
  Transaction type as integer

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* vote_first

**static* vote_first(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  The first round that the participation key is valid.

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* vote_key_dilution

**static* vote_key_dilution(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  Dilution for the 2-level participation key

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* vote_last

**static* vote_last(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns UInt64:**
  The last round that the participation key is valid.

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* vote_pk

**static* vote_pk(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Bytes:**
  32 byte address

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

##### *static* xfer_asset

**static* xfer_asset(t: [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

* **Parameters:**
  **t** ([*int*](https://docs.python.org/3/library/functions.html#int)) – transaction group index
* **Returns Asset:**
  Asset ID

Native TEAL opcode: [`gitxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gitxn)

#### *class* algopy.op.GTxn

Get values for transactions in the current group
Native TEAL ops: [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* accounts

**static* accounts(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

Accounts listed in the ApplicationCall transaction

Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* amount

**static* amount(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* application_args

**static* application_args(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Arguments passed to the application in the ApplicationCall transaction

Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* application_id

**static* application_id(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID from ApplicationCall transaction

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* applications

**static* applications(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

Foreign Apps listed in the ApplicationCall transaction

Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* approval_program

**static* approval_program(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Approval program

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* approval_program_pages

**static* approval_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Approval Program as an array of pages

Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* asset_amount

**static* asset_amount(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

value in Asset’s units

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* asset_close_to

**static* asset_close_to(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* asset_receiver

**static* asset_receiver(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* asset_sender

**static* asset_sender(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address. Source of assets if Sender is the Asset’s Clawback address.

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* assets

**static* assets(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

Foreign Assets listed in the ApplicationCall transaction

Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* clear_state_program

**static* clear_state_program(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Clear state program

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* clear_state_program_pages

**static* clear_state_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

ClearState Program as an array of pages

Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* close_remainder_to

**static* close_remainder_to(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset

**static* config_asset(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID in asset config transaction

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_clawback

**static* config_asset_clawback(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_decimals

**static* config_asset_decimals(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of digits to display after the decimal place when displaying the asset

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_default_frozen

**static* config_asset_default_frozen(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

Whether the asset’s slots are frozen by default or not, 0 or 1

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_freeze

**static* config_asset_freeze(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_manager

**static* config_asset_manager(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_metadata_hash

**static* config_asset_metadata_hash(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte commitment to unspecified asset metadata

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_name

**static* config_asset_name(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The asset name

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_reserve

**static* config_asset_reserve(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_total

**static* config_asset_total(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Total number of units of this asset created

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_unit_name

**static* config_asset_unit_name(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Unit name of the asset

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* config_asset_url

**static* config_asset_url(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

URL

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* created_application_id

**static* created_application_id(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* created_asset_id

**static* created_asset_id(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* extra_program_pages

**static* extra_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* fee

**static* fee(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* first_valid

**static* first_valid(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* first_valid_time

**static* first_valid_time(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* freeze_asset

**static* freeze_asset(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID being frozen or un-frozen

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* freeze_asset_account

**static* freeze_asset_account(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address of the account whose asset slot is being frozen or un-frozen

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* freeze_asset_frozen

**static* freeze_asset_frozen(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

The new frozen value, 0 or 1

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* global_num_byte_slice

**static* global_num_byte_slice(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state byteslices in ApplicationCall

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* global_num_uint

**static* global_num_uint(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state integers in ApplicationCall

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* group_index

**static* group_index(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* last_log

**static* last_log(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The last message emitted. Empty bytes if none were emitted. Application mode only

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* last_valid

**static* last_valid(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* lease

**static* lease(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* local_num_byte_slice

**static* local_num_byte_slice(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state byteslices in ApplicationCall

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* local_num_uint

**static* local_num_uint(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state integers in ApplicationCall

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* logs

**static* logs(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Log messages emitted by an application call (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gtxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxna), [`gtxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnas), [`gtxnsa`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsa), [`gtxnsas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxnsas)

##### *static* nonparticipation

**static* nonparticipation(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

Marks an account nonparticipating for rewards

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* note

**static* note(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* num_accounts

**static* num_accounts(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Accounts

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* num_app_args

**static* num_app_args(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ApplicationArgs

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* num_applications

**static* num_applications(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Applications

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* num_approval_program_pages

**static* num_approval_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Approval Program pages

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* num_assets

**static* num_assets(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Assets

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* num_clear_state_program_pages

**static* num_clear_state_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ClearState Program pages

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* num_logs

**static* num_logs(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Logs (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* on_completion

**static* on_completion(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction)*

ApplicationCall transaction on completion action

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* receiver

**static* receiver(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* reject_version

**static* reject_version(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Min AVM version: 12

* **Returns UInt64:**
  Application version for which the txn must reject

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* rekey_to

**static* rekey_to(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* selection_pk

**static* selection_pk(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* sender

**static* sender(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* state_proof_pk

**static* state_proof_pk(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

State proof public key

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* tx_id

**static* tx_id(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* type

**static* type(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* type_enum

**static* type_enum(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* vote_first

**static* vote_first(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The first round that the participation key is valid.

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* vote_key_dilution

**static* vote_key_dilution(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Dilution for the 2-level participation key

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* vote_last

**static* vote_last(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The last round that the participation key is valid.

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* vote_pk

**static* vote_pk(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

##### *static* xfer_asset

**static* xfer_asset(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID

Native TEAL opcode: [`gtxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxn), [`gtxns`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gtxns)

#### *class* algopy.op.Global

Get Global values
Native TEAL op: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)

##### asset_create_min_balance *: [Final]

*asset_create_min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The additional minimum balance required to create (and opt-in to) an asset.

##### asset_opt_in_min_balance *: [Final]

*asset_opt_in_min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The additional minimum balance required to opt-in to an asset.

##### caller_application_address *: [Final]

*caller_application_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

The application address of the application that called this application. ZeroAddress if this application is at the top-level. Application mode only.

##### caller_application_id *: [Final]

*caller_application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The application ID of the application that called this application. 0 if this application is at the top-level. Application mode only.

##### creator_address *: [Final]

*creator_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

Address of the creator of the current application. Application mode only.

##### current_application_address *: [Final]

*current_application_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

Address that the current application controls. Application mode only.

##### current_application_id *: [Final]

*current_application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Application](api-algopy.md#algopy.Application)]**

Ellipsis

ID of current application executing. Application mode only.

##### genesis_hash *: [Final]

*genesis_hash *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

The Genesis Hash for the network.

##### group_id *: [Final]

*group_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

ID of the transaction group. 32 zero bytes if the transaction is not part of a group.

##### group_size *: [Final]

*group_size *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of transactions in this atomic transaction group. At least 1

##### latest_timestamp *: [Final]

*latest_timestamp *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Last confirmed block UNIX timestamp. Fails if negative. Application mode only.

##### logic_sig_version *: [Final]

*logic_sig_version *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Maximum supported version

##### max_txn_life *: [Final]

*max_txn_life *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

rounds

##### min_balance *: [Final]

*min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

microalgos

##### min_txn_fee *: [Final]

*min_txn_fee *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

microalgos

##### *static* opcode_budget

**static* opcode_budget() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The remaining cost that can be spent by opcodes in this program.

Native TEAL opcode: [`global`](https://dev.algorand.co/reference/algorand-teal/opcodes/#global)

##### payouts_enabled *: [Final]

*payouts_enabled *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]**

Ellipsis

Whether block proposal payouts are enabled.
Min AVM version: 11

##### payouts_go_online_fee *: [Final]

*payouts_go_online_fee *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The fee required in a keyreg transaction to make an account incentive eligible.
Min AVM version: 11

##### payouts_max_balance *: [Final]

*payouts_max_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The maximum balance an account can have in the agreement round to receive block payouts in the proposal round.
Min AVM version: 11

##### payouts_min_balance *: [Final]

*payouts_min_balance *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The minimum balance an account must have in the agreement round to receive block payouts in the proposal round.
Min AVM version: 11

##### payouts_percent *: [Final]

*payouts_percent *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The percentage of transaction fees in a block that can be paid to the block proposer.
Min AVM version: 11

##### round *: [Final]

*round *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Current round number. Application mode only.

##### zero_address *: [Final]

*zero_address *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address of all zero bytes

#### *class* algopy.op.ITxn

Get values for the last inner transaction
Native TEAL ops: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* accounts

**static* accounts(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

Accounts listed in the ApplicationCall transaction

Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* amount

**static* amount() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* application_args

**static* application_args(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Arguments passed to the application in the ApplicationCall transaction

Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* application_id

**static* application_id() → [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID from ApplicationCall transaction

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* applications

**static* applications(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

Foreign Apps listed in the ApplicationCall transaction

Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* approval_program

**static* approval_program() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Approval program

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* approval_program_pages

**static* approval_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Approval Program as an array of pages

Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* asset_amount

**static* asset_amount() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

value in Asset’s units

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* asset_close_to

**static* asset_close_to() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* asset_receiver

**static* asset_receiver() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* asset_sender

**static* asset_sender() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address. Source of assets if Sender is the Asset’s Clawback address.

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* assets

**static* assets(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

Foreign Assets listed in the ApplicationCall transaction

Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* clear_state_program

**static* clear_state_program() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Clear state program

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* clear_state_program_pages

**static* clear_state_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

ClearState Program as an array of pages

Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* close_remainder_to

**static* close_remainder_to() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset

**static* config_asset() → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID in asset config transaction

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_clawback

**static* config_asset_clawback() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_decimals

**static* config_asset_decimals() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of digits to display after the decimal place when displaying the asset

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_default_frozen

**static* config_asset_default_frozen() → [bool](https://docs.python.org/3/library/functions.html#bool)*

Whether the asset’s slots are frozen by default or not, 0 or 1

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_freeze

**static* config_asset_freeze() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_manager

**static* config_asset_manager() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_metadata_hash

**static* config_asset_metadata_hash() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte commitment to unspecified asset metadata

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_name

**static* config_asset_name() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The asset name

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_reserve

**static* config_asset_reserve() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_total

**static* config_asset_total() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Total number of units of this asset created

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_unit_name

**static* config_asset_unit_name() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Unit name of the asset

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* config_asset_url

**static* config_asset_url() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

URL

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* created_application_id

**static* created_application_id() → [algopy.Application](api-algopy.md#algopy.Application)*

ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* created_asset_id

**static* created_asset_id() → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* extra_program_pages

**static* extra_program_pages() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* fee

**static* fee() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

microalgos

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* first_valid

**static* first_valid() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* first_valid_time

**static* first_valid_time() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

UNIX timestamp of block before txn.FirstValid. Fails if negative

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* freeze_asset

**static* freeze_asset() → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID being frozen or un-frozen

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* freeze_asset_account

**static* freeze_asset_account() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address of the account whose asset slot is being frozen or un-frozen

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* freeze_asset_frozen

**static* freeze_asset_frozen() → [bool](https://docs.python.org/3/library/functions.html#bool)*

The new frozen value, 0 or 1

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* global_num_byte_slice

**static* global_num_byte_slice() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state byteslices in ApplicationCall

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* global_num_uint

**static* global_num_uint() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of global state integers in ApplicationCall

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* group_index

**static* group_index() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* last_log

**static* last_log() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The last message emitted. Empty bytes if none were emitted. Application mode only

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* last_valid

**static* last_valid() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

round number

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* lease

**static* lease() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte lease value

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* local_num_byte_slice

**static* local_num_byte_slice() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state byteslices in ApplicationCall

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* local_num_uint

**static* local_num_uint() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of local state integers in ApplicationCall

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* logs

**static* logs(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Log messages emitted by an application call (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`itxna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxna), [`itxnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxnas)

##### *static* nonparticipation

**static* nonparticipation() → [bool](https://docs.python.org/3/library/functions.html#bool)*

Marks an account nonparticipating for rewards

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* note

**static* note() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Any data up to 1024 bytes

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* num_accounts

**static* num_accounts() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Accounts

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* num_app_args

**static* num_app_args() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ApplicationArgs

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* num_applications

**static* num_applications() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Applications

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* num_approval_program_pages

**static* num_approval_program_pages() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Approval Program pages

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* num_assets

**static* num_assets() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Assets

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* num_clear_state_program_pages

**static* num_clear_state_program_pages() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of ClearState Program pages

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* num_logs

**static* num_logs() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Number of Logs (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* on_completion

**static* on_completion() → [algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction)*

ApplicationCall transaction on completion action

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* receiver

**static* receiver() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* reject_version

**static* reject_version() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Min AVM version: 12

* **Returns UInt64:**
  Application version for which the txn must reject

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* rekey_to

**static* rekey_to() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte Sender’s new AuthAddr

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* selection_pk

**static* selection_pk() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* sender

**static* sender() → [algopy.Account](api-algopy.md#algopy.Account)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* state_proof_pk

**static* state_proof_pk() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

State proof public key

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* tx_id

**static* tx_id() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

The computed ID for this transaction. 32 bytes.

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* type

**static* type() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Transaction type as bytes

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* type_enum

**static* type_enum() → [algopy.TransactionType](api-algopy.md#algopy.TransactionType)*

Transaction type as integer

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* vote_first

**static* vote_first() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The first round that the participation key is valid.

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* vote_key_dilution

**static* vote_key_dilution() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Dilution for the 2-level participation key

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* vote_last

**static* vote_last() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The last round that the participation key is valid.

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* vote_pk

**static* vote_pk() → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

32 byte address

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

##### *static* xfer_asset

**static* xfer_asset() → [algopy.Asset](api-algopy.md#algopy.Asset)*

Asset ID

Native TEAL opcode: [`itxn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn)

#### *class* algopy.op.ITxnCreate

Create inner transactions
Native TEAL ops: [`itxn_begin`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_begin), [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field), [`itxn_next`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_next), [`itxn_submit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_submit)

##### *static* begin

**static* begin() → [None](https://docs.python.org/3/library/constants.html#None)*

begin preparation of a new inner transaction in a new transaction group
`itxn_begin` initializes Sender to the application address; Fee to the minimum allowable, taking into account MinTxnFee and credit from overpaying in earlier transactions; FirstValid/LastValid to the values in the invoking transaction, and all other fields to zero or empty values.

Native TEAL opcode: [`itxn_begin`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_begin)

##### *static* next

**static* next() → [None](https://docs.python.org/3/library/constants.html#None)*

begin preparation of a new inner transaction in the same transaction group
`itxn_next` initializes the transaction exactly as `itxn_begin` does

Native TEAL opcode: [`itxn_next`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_next)

##### *static* set_accounts

**static* set_accounts(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – Accounts listed in the ApplicationCall transaction

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_amount

**static* set_amount(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – microalgos

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_application_args

**static* set_application_args(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – Arguments passed to the application in the ApplicationCall transaction

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_application_id

**static* set_application_id(a: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Application*](api-algopy.md#algopy.Application) *|* [*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – ApplicationID from ApplicationCall transaction

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_applications

**static* set_applications(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Foreign Apps listed in the ApplicationCall transaction

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_approval_program

**static* set_approval_program(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – Approval program

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_approval_program_pages

**static* set_approval_program_pages(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – Approval Program as an array of pages

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_asset_amount

**static* set_asset_amount(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – value in Asset’s units

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_asset_close_to

**static* set_asset_close_to(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_asset_receiver

**static* set_asset_receiver(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_asset_sender

**static* set_asset_sender(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address. Source of assets if Sender is the Asset’s Clawback address.

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_assets

**static* set_assets(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Foreign Assets listed in the ApplicationCall transaction

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_clear_state_program

**static* set_clear_state_program(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – Clear state program

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_clear_state_program_pages

**static* set_clear_state_program_pages(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – ClearState Program as an array of pages

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_close_remainder_to

**static* set_close_remainder_to(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset

**static* set_config_asset(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Asset*](api-algopy.md#algopy.Asset) *|* [*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Asset ID in asset config transaction

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_clawback

**static* set_config_asset_clawback(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_decimals

**static* set_config_asset_decimals(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Number of digits to display after the decimal place when displaying the asset

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_default_frozen

**static* set_config_asset_default_frozen(a: [bool](https://docs.python.org/3/library/functions.html#bool), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the asset’s slots are frozen by default or not, 0 or 1

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_freeze

**static* set_config_asset_freeze(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_manager

**static* set_config_asset_manager(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_metadata_hash

**static* set_config_asset_metadata_hash(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – 32 byte commitment to unspecified asset metadata

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_name

**static* set_config_asset_name(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – The asset name

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_reserve

**static* set_config_asset_reserve(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_total

**static* set_config_asset_total(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Total number of units of this asset created

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_unit_name

**static* set_config_asset_unit_name(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – Unit name of the asset

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_config_asset_url

**static* set_config_asset_url(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – URL

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_extra_program_pages

**static* set_extra_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_fee

**static* set_fee(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – microalgos

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_freeze_asset

**static* set_freeze_asset(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Asset*](api-algopy.md#algopy.Asset) *|* [*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Asset ID being frozen or un-frozen

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_freeze_asset_account

**static* set_freeze_asset_account(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address of the account whose asset slot is being frozen or un-frozen

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_freeze_asset_frozen

**static* set_freeze_asset_frozen(a: [bool](https://docs.python.org/3/library/functions.html#bool), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – The new frozen value, 0 or 1

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_global_num_byte_slice

**static* set_global_num_byte_slice(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Number of global state byteslices in ApplicationCall

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_global_num_uint

**static* set_global_num_uint(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Number of global state integers in ApplicationCall

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_local_num_byte_slice

**static* set_local_num_byte_slice(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Number of local state byteslices in ApplicationCall

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_local_num_uint

**static* set_local_num_uint(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Number of local state integers in ApplicationCall

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_nonparticipation

**static* set_nonparticipation(a: [bool](https://docs.python.org/3/library/functions.html#bool), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Marks an account nonparticipating for rewards

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_note

**static* set_note(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – Any data up to 1024 bytes

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_on_completion

**static* set_on_completion(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – ApplicationCall transaction on completion action

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_receiver

**static* set_receiver(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_reject_version

**static* set_reject_version(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

Min AVM version: 12

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Application version for which the txn must reject

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_rekey_to

**static* set_rekey_to(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte Sender’s new AuthAddr

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_selection_pk

**static* set_selection_pk(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_sender

**static* set_sender(a: [algopy.Account](api-algopy.md#algopy.Account), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Account*](api-algopy.md#algopy.Account)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_state_proof_pk

**static* set_state_proof_pk(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – State proof public key

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_type

**static* set_type(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – Transaction type as bytes

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_type_enum

**static* set_type_enum(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Transaction type as integer

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_vote_first

**static* set_vote_first(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – The first round that the participation key is valid.

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_vote_key_dilution

**static* set_vote_key_dilution(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Dilution for the 2-level participation key

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_vote_last

**static* set_vote_last(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – The last round that the participation key is valid.

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_vote_pk

**static* set_vote_pk(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Bytes*](api-algopy.md#algopy.Bytes) *|* [*bytes*](https://docs.python.org/3/library/stdtypes.html#bytes)) – 32 byte address

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* set_xfer_asset

**static* set_xfer_asset(a: [algopy.Asset](api-algopy.md#algopy.Asset) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

* **Parameters:**
  **a** ([*Asset*](api-algopy.md#algopy.Asset) *|* [*UInt64*](api-algopy.md#algopy.UInt64) *|* [*int*](https://docs.python.org/3/library/functions.html#int)) – Asset ID

Native TEAL opcode: [`itxn_field`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_field)

##### *static* submit

**static* submit() → [None](https://docs.python.org/3/library/constants.html#None)*

execute the current inner transaction group. Fail if executing this group would exceed the inner transaction limit, or if any transaction in the group fails.
`itxn_submit` resets the current transaction so that it can not be resubmitted. A new `itxn_begin` is required to prepare another inner transaction.

Native TEAL opcode: [`itxn_submit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itxn_submit)

#### *class* algopy.op.JsonRef

key B’s value, of type R, from a [valid]() utf-8 encoded json object A *Warning*: Usage should be restricted to very rare use cases, as JSON decoding is expensive and quite limited. In addition, JSON objects are large and not optimized for size.  Almost all smart contracts should use simpler and smaller methods (such as the [ABI](https://arc.algorand.foundation/ARCs/arc-0004). This opcode should only be used in cases where JSON is only available option, e.g. when a third-party only signs JSON.
Native TEAL op: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)

##### *static* json_object

**static* json_object(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Native TEAL opcode: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)

##### *static* json_string

**static* json_string(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Native TEAL opcode: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)

##### *static* json_uint64

**static* json_uint64(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Native TEAL opcode: [`json_ref`](https://dev.algorand.co/reference/algorand-teal/opcodes/#json_ref)

#### *class* algopy.op.MiMCConfigurations

Available values for the `Mimc Configurations` enum

##### Initialization

Initialize self.  See help(type(self)) for accurate signature.

##### BLS12_381Mp111 *: [algopy.op.MiMCConfigurations]

*BLS12_381Mp111 *: [algopy.op.MiMCConfigurations](#algopy.op.MiMCConfigurations)**

Ellipsis

MiMC configuration for the BLS12-381 curve with Miyaguchi-Preneel mode, 111 rounds, exponent 5, seed “seed”
Min AVM version: 11

##### BN254Mp110 *: [algopy.op.MiMCConfigurations]

*BN254Mp110 *: [algopy.op.MiMCConfigurations](#algopy.op.MiMCConfigurations)**

Ellipsis

MiMC configuration for the BN254 curve with Miyaguchi-Preneel mode, 110 rounds, exponent 5, seed “seed”
Min AVM version: 11

##### \_\_add_\_

*\_\_add_\_()*

Return self+value.

##### \_\_contains_\_

*\_\_contains_\_()*

Return bool(key in self).

##### \_\_delattr_\_

*\_\_delattr_\_()*

Implement delattr(self, name).

##### \_\_dir_\_

*\_\_dir_\_()*

Default dir() implementation.

##### \_\_eq_\_

*\_\_eq_\_()*

Return self==value.

##### \_\_format_\_

*\_\_format_\_()*

Return a formatted version of the string as described by format_spec.

##### \_\_ge_\_

*\_\_ge_\_()*

Return self>=value.

##### \_\_getattribute_\_

*\_\_getattribute_\_()*

Return getattr(self, name).

##### \_\_getitem_\_

*\_\_getitem_\_()*

Return self[key].

##### \_\_getstate_\_

*\_\_getstate_\_()*

Helper for pickle.

##### \_\_gt_\_

*\_\_gt_\_()*

Return self>value.

##### \_\_hash_\_

*\_\_hash_\_()*

Return hash(self).

##### \_\_iter_\_

*\_\_iter_\_()*

Implement iter(self).

##### \_\_le_\_

*\_\_le_\_()*

Return self<=value.

##### \_\_len_\_

*\_\_len_\_()*

Return len(self).

##### \_\_lt_\_

*\_\_lt_\_()*

Return self<value.

##### \_\_mod_\_

*\_\_mod_\_()*

Return self%value.

##### \_\_mul_\_

*\_\_mul_\_()*

Return self\*value.

##### \_\_ne_\_

*\_\_ne_\_()*

Return self!=value.

##### \_\_new_\_

*\_\_new_\_()*

Create and return a new object.  See help(type) for accurate signature.

##### \_\_reduce_\_

*\_\_reduce_\_()*

Helper for pickle.

##### \_\_reduce_ex_\_

*\_\_reduce_ex_\_()*

Helper for pickle.

##### \_\_repr_\_

*\_\_repr_\_()*

Return repr(self).

##### \_\_rmod_\_

*\_\_rmod_\_()*

Return value%self.

##### \_\_rmul_\_

*\_\_rmul_\_()*

Return value\*self.

##### \_\_setattr_\_

*\_\_setattr_\_()*

Implement setattr(self, name, value).

##### \_\_sizeof_\_

*\_\_sizeof_\_()*

Return the size of the string in memory, in bytes.

##### \_\_str_\_

*\_\_str_\_()*

Return str(self).

##### capitalize

*capitalize()*

Return a capitalized version of the string.

More specifically, make the first character have upper case and the rest lower
case.

##### casefold

*casefold()*

Return a version of the string suitable for caseless comparisons.

##### center

*center()*

Return a centered string of length width.

Padding is done using the specified fill character (default is a space).

##### count

*count()*

S.count(sub[, start[, end]]) -> int

Return the number of non-overlapping occurrences of substring sub in
string S[start:end].  Optional arguments start and end are
interpreted as in slice notation.

##### encode

*encode()*

Encode the string using the codec registered for encoding.

encoding
The encoding in which to encode the string.
errors
The error handling scheme to use for encoding errors.
The default is ‘strict’ meaning that encoding errors raise a
UnicodeEncodeError.  Other possible values are ‘ignore’, ‘replace’ and
‘xmlcharrefreplace’ as well as any other name registered with
codecs.register_error that can handle UnicodeEncodeErrors.

##### endswith

*endswith()*

S.endswith(suffix[, start[, end]]) -> bool

Return True if S ends with the specified suffix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
suffix can also be a tuple of strings to try.

##### expandtabs

*expandtabs()*

Return a copy where all tab characters are expanded using spaces.

If tabsize is not given, a tab size of 8 characters is assumed.

##### find

*find()*

S.find(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### format

*format()*

S.format(\*args, \*\*kwargs) -> str

Return a formatted version of S, using substitutions from args and kwargs.
The substitutions are identified by braces (‘{’ and ‘}’).

##### format_map

*format_map()*

S.format_map(mapping) -> str

Return a formatted version of S, using substitutions from mapping.
The substitutions are identified by braces (‘{’ and ‘}’).

##### index

*index()*

S.index(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### isalnum

*isalnum()*

Return True if the string is an alpha-numeric string, False otherwise.

A string is alpha-numeric if all characters in the string are alpha-numeric and
there is at least one character in the string.

##### isalpha

*isalpha()*

Return True if the string is an alphabetic string, False otherwise.

A string is alphabetic if all characters in the string are alphabetic and there
is at least one character in the string.

##### isascii

*isascii()*

Return True if all characters in the string are ASCII, False otherwise.

ASCII characters have code points in the range U+0000-U+007F.
Empty string is ASCII too.

##### isdecimal

*isdecimal()*

Return True if the string is a decimal string, False otherwise.

A string is a decimal string if all characters in the string are decimal and
there is at least one character in the string.

##### isdigit

*isdigit()*

Return True if the string is a digit string, False otherwise.

A string is a digit string if all characters in the string are digits and there
is at least one character in the string.

##### isidentifier

*isidentifier()*

Return True if the string is a valid Python identifier, False otherwise.

Call keyword.iskeyword(s) to test whether string s is a reserved identifier,
such as “def” or “class”.

##### islower

*islower()*

Return True if the string is a lowercase string, False otherwise.

A string is lowercase if all cased characters in the string are lowercase and
there is at least one cased character in the string.

##### isnumeric

*isnumeric()*

Return True if the string is a numeric string, False otherwise.

A string is numeric if all characters in the string are numeric and there is at
least one character in the string.

##### isprintable

*isprintable()*

Return True if the string is printable, False otherwise.

A string is printable if all of its characters are considered printable in
repr() or if it is empty.

##### isspace

*isspace()*

Return True if the string is a whitespace string, False otherwise.

A string is whitespace if all characters in the string are whitespace and there
is at least one character in the string.

##### istitle

*istitle()*

Return True if the string is a title-cased string, False otherwise.

In a title-cased string, upper- and title-case characters may only
follow uncased characters and lowercase characters only cased ones.

##### isupper

*isupper()*

Return True if the string is an uppercase string, False otherwise.

A string is uppercase if all cased characters in the string are uppercase and
there is at least one cased character in the string.

##### join

*join()*

Concatenate any number of strings.

The string whose method is called is inserted in between each given string.
The result is returned as a new string.

Example: ‘.’.join([‘ab’, ‘pq’, ‘rs’]) -> ‘ab.pq.rs’

##### ljust

*ljust()*

Return a left-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### lower

*lower()*

Return a copy of the string converted to lowercase.

##### lstrip

*lstrip()*

Return a copy of the string with leading whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### partition

*partition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string.  If the separator is found,
returns a 3-tuple containing the part before the separator, the separator
itself, and the part after it.

If the separator is not found, returns a 3-tuple containing the original string
and two empty strings.

##### removeprefix

*removeprefix()*

Return a str with the given prefix string removed if present.

If the string starts with the prefix string, return string[len(prefix):].
Otherwise, return a copy of the original string.

##### removesuffix

*removesuffix()*

Return a str with the given suffix string removed if present.

If the string ends with the suffix string and that suffix is not empty,
return string[:-len(suffix)]. Otherwise, return a copy of the original
string.

##### replace

*replace()*

Return a copy with all occurrences of substring old replaced by new.

count
Maximum number of occurrences to replace.
-1 (the default value) means replace all occurrences.

If the optional argument count is given, only the first count occurrences are
replaced.

##### rfind

*rfind()*

S.rfind(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### rindex

*rindex()*

S.rindex(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### rjust

*rjust()*

Return a right-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### rpartition

*rpartition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string, starting at the end. If
the separator is found, returns a 3-tuple containing the part before the
separator, the separator itself, and the part after it.

If the separator is not found, returns a 3-tuple containing two empty strings
and the original string.

##### rsplit

*rsplit()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the end of the string and works to the front.

##### rstrip

*rstrip()*

Return a copy of the string with trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### split

*split()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the front of the string and works to the end.

Note, str.split() is mainly useful for data that has been intentionally
delimited.  With natural text that includes punctuation, consider using
the regular expression module.

##### splitlines

*splitlines()*

Return a list of the lines in the string, breaking at line boundaries.

Line breaks are not included in the resulting list unless keepends is given and
true.

##### startswith

*startswith()*

S.startswith(prefix[, start[, end]]) -> bool

Return True if S starts with the specified prefix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
prefix can also be a tuple of strings to try.

##### strip

*strip()*

Return a copy of the string with leading and trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### swapcase

*swapcase()*

Convert uppercase characters to lowercase and lowercase characters to uppercase.

##### title

*title()*

Return a version of the string where each word is titlecased.

More specifically, words start with uppercased characters and all remaining
cased characters have lower case.

##### translate

*translate()*

Replace each character in the string using the given translation table.

table
Translation table, which must be a mapping of Unicode ordinals to
Unicode ordinals, strings, or None.

The table must implement lookup/indexing via **getitem**, for instance a
dictionary or list.  If this operation raises LookupError, the character is
left untouched.  Characters mapped to None are deleted.

##### upper

*upper()*

Return a copy of the string converted to uppercase.

##### zfill

*zfill()*

Pad a numeric string with zeros on the left, to fill a field of the given width.

The string is never truncated.

#### *class* algopy.op.Scratch

Load or store scratch values
Native TEAL ops: [`loads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#loads), [`stores`](https://dev.algorand.co/reference/algorand-teal/opcodes/#stores)

##### *static* load_bytes

**static* load_bytes(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Ath scratch space value.  All scratch spaces are 0 at program start.

Native TEAL opcode: [`loads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#loads)

##### *static* load_uint64

**static* load_uint64(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Ath scratch space value.  All scratch spaces are 0 at program start.

Native TEAL opcode: [`loads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#loads)

##### *static* store

**static* store(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [int](https://docs.python.org/3/library/functions.html#int), /) → [None](https://docs.python.org/3/library/constants.html#None)*

store B to the Ath scratch space

Native TEAL opcode: [`stores`](https://dev.algorand.co/reference/algorand-teal/opcodes/#stores)

#### *class* algopy.op.Txn

Get values for the current executing transaction
Native TEAL ops: [`txn`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txn), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### *static* accounts

**static* accounts(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Account](api-algopy.md#algopy.Account)*

Accounts listed in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### amount *: [Final]

*amount *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

microalgos

##### *static* application_args

**static* application_args(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Arguments passed to the application in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### application_id *: [Final]

*application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Application](api-algopy.md#algopy.Application)]**

Ellipsis

ApplicationID from ApplicationCall transaction

##### *static* applications

**static* applications(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Application](api-algopy.md#algopy.Application)*

Foreign Apps listed in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### approval_program *: [Final]

*approval_program *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

Approval program

##### *static* approval_program_pages

**static* approval_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Approval Program as an array of pages

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### asset_amount *: [Final]

*asset_amount *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

value in Asset’s units

##### asset_close_to *: [Final]

*asset_close_to *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### asset_receiver *: [Final]

*asset_receiver *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### asset_sender *: [Final]

*asset_sender *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address. Source of assets if Sender is the Asset’s Clawback address.

##### *static* assets

**static* assets(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Asset](api-algopy.md#algopy.Asset)*

Foreign Assets listed in the ApplicationCall transaction

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### clear_state_program *: [Final]

*clear_state_program *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

Clear state program

##### *static* clear_state_program_pages

**static* clear_state_program_pages(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

ClearState Program as an array of pages

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### close_remainder_to *: [Final]

*close_remainder_to *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### config_asset *: [Final]

*config_asset *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](api-algopy.md#algopy.Asset)]**

Ellipsis

Asset ID in asset config transaction

##### config_asset_clawback *: [Final]

*config_asset_clawback *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### config_asset_decimals *: [Final]

*config_asset_decimals *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of digits to display after the decimal place when displaying the asset

##### config_asset_default_frozen *: [Final]

*config_asset_default_frozen *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]**

Ellipsis

Whether the asset’s slots are frozen by default or not, 0 or 1

##### config_asset_freeze *: [Final]

*config_asset_freeze *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### config_asset_manager *: [Final]

*config_asset_manager *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### config_asset_metadata_hash *: [Final]

*config_asset_metadata_hash *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

32 byte commitment to unspecified asset metadata

##### config_asset_name *: [Final]

*config_asset_name *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

The asset name

##### config_asset_reserve *: [Final]

*config_asset_reserve *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### config_asset_total *: [Final]

*config_asset_total *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Total number of units of this asset created

##### config_asset_unit_name *: [Final]

*config_asset_unit_name *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

Unit name of the asset

##### config_asset_url *: [Final]

*config_asset_url *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

URL

##### created_application_id *: [Final]

*created_application_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Application](api-algopy.md#algopy.Application)]**

Ellipsis

ApplicationID allocated by the creation of an application (only with `itxn` in v5). Application mode only

##### created_asset_id *: [Final]

*created_asset_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](api-algopy.md#algopy.Asset)]**

Ellipsis

Asset ID allocated by the creation of an ASA (only with `itxn` in v5). Application mode only

##### extra_program_pages *: [Final]

*extra_program_pages *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of additional pages for each of the application’s approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program.

##### fee *: [Final]

*fee *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

microalgos

##### first_valid *: [Final]

*first_valid *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

round number

##### first_valid_time *: [Final]

*first_valid_time *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

UNIX timestamp of block before txn.FirstValid. Fails if negative

##### freeze_asset *: [Final]

*freeze_asset *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](api-algopy.md#algopy.Asset)]**

Ellipsis

Asset ID being frozen or un-frozen

##### freeze_asset_account *: [Final]

*freeze_asset_account *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address of the account whose asset slot is being frozen or un-frozen

##### freeze_asset_frozen *: [Final]

*freeze_asset_frozen *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]**

Ellipsis

The new frozen value, 0 or 1

##### global_num_byte_slice *: [Final]

*global_num_byte_slice *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of global state byteslices in ApplicationCall

##### global_num_uint *: [Final]

*global_num_uint *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of global state integers in ApplicationCall

##### group_index *: [Final]

*group_index *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Position of this transaction within an atomic transaction group. A stand-alone transaction is implicitly element 0 in a group of 1

##### last_log *: [Final]

*last_log *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

The last message emitted. Empty bytes if none were emitted. Application mode only

##### last_valid *: [Final]

*last_valid *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

round number

##### lease *: [Final]

*lease *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

32 byte lease value

##### local_num_byte_slice *: [Final]

*local_num_byte_slice *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of local state byteslices in ApplicationCall

##### local_num_uint *: [Final]

*local_num_uint *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of local state integers in ApplicationCall

##### *static* logs

**static* logs(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Log messages emitted by an application call (only with `itxn` in v5). Application mode only

Native TEAL opcode: [`txna`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txna), [`txnas`](https://dev.algorand.co/reference/algorand-teal/opcodes/#txnas)

##### nonparticipation *: [Final]

*nonparticipation *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[bool](https://docs.python.org/3/library/functions.html#bool)]**

Ellipsis

Marks an account nonparticipating for rewards

##### note *: [Final]

*note *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

Any data up to 1024 bytes

##### num_accounts *: [Final]

*num_accounts *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of Accounts

##### num_app_args *: [Final]

*num_app_args *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of ApplicationArgs

##### num_applications *: [Final]

*num_applications *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of Applications

##### num_approval_program_pages *: [Final]

*num_approval_program_pages *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of Approval Program pages

##### num_assets *: [Final]

*num_assets *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of Assets

##### num_clear_state_program_pages *: [Final]

*num_clear_state_program_pages *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of ClearState Program pages

##### num_logs *: [Final]

*num_logs *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Number of Logs (only with `itxn` in v5). Application mode only

##### on_completion *: [Final]

*on_completion *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.OnCompleteAction](api-algopy.md#algopy.OnCompleteAction)]**

Ellipsis

ApplicationCall transaction on completion action

##### receiver *: [Final]

*receiver *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### reject_version *: [Final]

*reject_version *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Application version for which the txn must reject
Min AVM version: 12

##### rekey_to *: [Final]

*rekey_to *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte Sender’s new AuthAddr

##### selection_pk *: [Final]

*selection_pk *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

32 byte address

##### sender *: [Final]

*sender *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Account](api-algopy.md#algopy.Account)]**

Ellipsis

32 byte address

##### state_proof_pk *: [Final]

*state_proof_pk *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

State proof public key

##### tx_id *: [Final]

*tx_id *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

The computed ID for this transaction. 32 bytes.

##### type *: [Final]

*type *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

Transaction type as bytes

##### type_enum *: [Final]

*type_enum *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.TransactionType](api-algopy.md#algopy.TransactionType)]**

Ellipsis

Transaction type as integer

##### vote_first *: [Final]

*vote_first *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The first round that the participation key is valid.

##### vote_key_dilution *: [Final]

*vote_key_dilution *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

Dilution for the 2-level participation key

##### vote_last *: [Final]

*vote_last *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.UInt64](api-algopy.md#algopy.UInt64)]**

Ellipsis

The last round that the participation key is valid.

##### vote_pk *: [Final]

*vote_pk *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Bytes](api-algopy.md#algopy.Bytes)]**

Ellipsis

32 byte address

##### xfer_asset *: [Final]

*xfer_asset *: [Final](https://docs.python.org/3/library/typing.html#typing.Final)[[algopy.Asset](api-algopy.md#algopy.Asset)]**

Ellipsis

Asset ID

#### *class* algopy.op.VoterParamsGet

X is field F from online account A as of the balance round: 320 rounds before the current round. Y is 1 if A had positive algos online in the agreement round, else Y is 0 and X is a type specific zero-value
Native TEAL op: [`voter_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#voter_params_get)

##### *static* voter_balance

**static* voter_balance(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Min AVM version: 11

* **Returns tuple[UInt64, bool]:**
  Online stake in microalgos

Native TEAL opcode: [`voter_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#voter_params_get)

##### *static* voter_incentive_eligible

**static* voter_incentive_eligible(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[bool](https://docs.python.org/3/library/functions.html#bool), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Min AVM version: 11

* **Returns tuple[bool, bool]:**
  Had this account opted into block payouts

Native TEAL opcode: [`voter_params_get`](https://dev.algorand.co/reference/algorand-teal/opcodes/#voter_params_get)

#### *class* algopy.op.VrfVerify

Available values for the `vrf_verify` enum

##### Initialization

Initialize self.  See help(type(self)) for accurate signature.

##### \_\_add_\_

*\_\_add_\_()*

Return self+value.

##### \_\_contains_\_

*\_\_contains_\_()*

Return bool(key in self).

##### \_\_delattr_\_

*\_\_delattr_\_()*

Implement delattr(self, name).

##### \_\_dir_\_

*\_\_dir_\_()*

Default dir() implementation.

##### \_\_eq_\_

*\_\_eq_\_()*

Return self==value.

##### \_\_format_\_

*\_\_format_\_()*

Return a formatted version of the string as described by format_spec.

##### \_\_ge_\_

*\_\_ge_\_()*

Return self>=value.

##### \_\_getattribute_\_

*\_\_getattribute_\_()*

Return getattr(self, name).

##### \_\_getitem_\_

*\_\_getitem_\_()*

Return self[key].

##### \_\_getstate_\_

*\_\_getstate_\_()*

Helper for pickle.

##### \_\_gt_\_

*\_\_gt_\_()*

Return self>value.

##### \_\_hash_\_

*\_\_hash_\_()*

Return hash(self).

##### \_\_iter_\_

*\_\_iter_\_()*

Implement iter(self).

##### \_\_le_\_

*\_\_le_\_()*

Return self<=value.

##### \_\_len_\_

*\_\_len_\_()*

Return len(self).

##### \_\_lt_\_

*\_\_lt_\_()*

Return self<value.

##### \_\_mod_\_

*\_\_mod_\_()*

Return self%value.

##### \_\_mul_\_

*\_\_mul_\_()*

Return self\*value.

##### \_\_ne_\_

*\_\_ne_\_()*

Return self!=value.

##### \_\_new_\_

*\_\_new_\_()*

Create and return a new object.  See help(type) for accurate signature.

##### \_\_reduce_\_

*\_\_reduce_\_()*

Helper for pickle.

##### \_\_reduce_ex_\_

*\_\_reduce_ex_\_()*

Helper for pickle.

##### \_\_repr_\_

*\_\_repr_\_()*

Return repr(self).

##### \_\_rmod_\_

*\_\_rmod_\_()*

Return value%self.

##### \_\_rmul_\_

*\_\_rmul_\_()*

Return value\*self.

##### \_\_setattr_\_

*\_\_setattr_\_()*

Implement setattr(self, name, value).

##### \_\_sizeof_\_

*\_\_sizeof_\_()*

Return the size of the string in memory, in bytes.

##### \_\_str_\_

*\_\_str_\_()*

Return str(self).

##### capitalize

*capitalize()*

Return a capitalized version of the string.

More specifically, make the first character have upper case and the rest lower
case.

##### casefold

*casefold()*

Return a version of the string suitable for caseless comparisons.

##### center

*center()*

Return a centered string of length width.

Padding is done using the specified fill character (default is a space).

##### count

*count()*

S.count(sub[, start[, end]]) -> int

Return the number of non-overlapping occurrences of substring sub in
string S[start:end].  Optional arguments start and end are
interpreted as in slice notation.

##### encode

*encode()*

Encode the string using the codec registered for encoding.

encoding
The encoding in which to encode the string.
errors
The error handling scheme to use for encoding errors.
The default is ‘strict’ meaning that encoding errors raise a
UnicodeEncodeError.  Other possible values are ‘ignore’, ‘replace’ and
‘xmlcharrefreplace’ as well as any other name registered with
codecs.register_error that can handle UnicodeEncodeErrors.

##### endswith

*endswith()*

S.endswith(suffix[, start[, end]]) -> bool

Return True if S ends with the specified suffix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
suffix can also be a tuple of strings to try.

##### expandtabs

*expandtabs()*

Return a copy where all tab characters are expanded using spaces.

If tabsize is not given, a tab size of 8 characters is assumed.

##### find

*find()*

S.find(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### format

*format()*

S.format(\*args, \*\*kwargs) -> str

Return a formatted version of S, using substitutions from args and kwargs.
The substitutions are identified by braces (‘{’ and ‘}’).

##### format_map

*format_map()*

S.format_map(mapping) -> str

Return a formatted version of S, using substitutions from mapping.
The substitutions are identified by braces (‘{’ and ‘}’).

##### index

*index()*

S.index(sub[, start[, end]]) -> int

Return the lowest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### isalnum

*isalnum()*

Return True if the string is an alpha-numeric string, False otherwise.

A string is alpha-numeric if all characters in the string are alpha-numeric and
there is at least one character in the string.

##### isalpha

*isalpha()*

Return True if the string is an alphabetic string, False otherwise.

A string is alphabetic if all characters in the string are alphabetic and there
is at least one character in the string.

##### isascii

*isascii()*

Return True if all characters in the string are ASCII, False otherwise.

ASCII characters have code points in the range U+0000-U+007F.
Empty string is ASCII too.

##### isdecimal

*isdecimal()*

Return True if the string is a decimal string, False otherwise.

A string is a decimal string if all characters in the string are decimal and
there is at least one character in the string.

##### isdigit

*isdigit()*

Return True if the string is a digit string, False otherwise.

A string is a digit string if all characters in the string are digits and there
is at least one character in the string.

##### isidentifier

*isidentifier()*

Return True if the string is a valid Python identifier, False otherwise.

Call keyword.iskeyword(s) to test whether string s is a reserved identifier,
such as “def” or “class”.

##### islower

*islower()*

Return True if the string is a lowercase string, False otherwise.

A string is lowercase if all cased characters in the string are lowercase and
there is at least one cased character in the string.

##### isnumeric

*isnumeric()*

Return True if the string is a numeric string, False otherwise.

A string is numeric if all characters in the string are numeric and there is at
least one character in the string.

##### isprintable

*isprintable()*

Return True if the string is printable, False otherwise.

A string is printable if all of its characters are considered printable in
repr() or if it is empty.

##### isspace

*isspace()*

Return True if the string is a whitespace string, False otherwise.

A string is whitespace if all characters in the string are whitespace and there
is at least one character in the string.

##### istitle

*istitle()*

Return True if the string is a title-cased string, False otherwise.

In a title-cased string, upper- and title-case characters may only
follow uncased characters and lowercase characters only cased ones.

##### isupper

*isupper()*

Return True if the string is an uppercase string, False otherwise.

A string is uppercase if all cased characters in the string are uppercase and
there is at least one cased character in the string.

##### join

*join()*

Concatenate any number of strings.

The string whose method is called is inserted in between each given string.
The result is returned as a new string.

Example: ‘.’.join([‘ab’, ‘pq’, ‘rs’]) -> ‘ab.pq.rs’

##### ljust

*ljust()*

Return a left-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### lower

*lower()*

Return a copy of the string converted to lowercase.

##### lstrip

*lstrip()*

Return a copy of the string with leading whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### partition

*partition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string.  If the separator is found,
returns a 3-tuple containing the part before the separator, the separator
itself, and the part after it.

If the separator is not found, returns a 3-tuple containing the original string
and two empty strings.

##### removeprefix

*removeprefix()*

Return a str with the given prefix string removed if present.

If the string starts with the prefix string, return string[len(prefix):].
Otherwise, return a copy of the original string.

##### removesuffix

*removesuffix()*

Return a str with the given suffix string removed if present.

If the string ends with the suffix string and that suffix is not empty,
return string[:-len(suffix)]. Otherwise, return a copy of the original
string.

##### replace

*replace()*

Return a copy with all occurrences of substring old replaced by new.

count
Maximum number of occurrences to replace.
-1 (the default value) means replace all occurrences.

If the optional argument count is given, only the first count occurrences are
replaced.

##### rfind

*rfind()*

S.rfind(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Return -1 on failure.

##### rindex

*rindex()*

S.rindex(sub[, start[, end]]) -> int

Return the highest index in S where substring sub is found,
such that sub is contained within S[start:end].  Optional
arguments start and end are interpreted as in slice notation.

Raises ValueError when the substring is not found.

##### rjust

*rjust()*

Return a right-justified string of length width.

Padding is done using the specified fill character (default is a space).

##### rpartition

*rpartition()*

Partition the string into three parts using the given separator.

This will search for the separator in the string, starting at the end. If
the separator is found, returns a 3-tuple containing the part before the
separator, the separator itself, and the part after it.

If the separator is not found, returns a 3-tuple containing two empty strings
and the original string.

##### rsplit

*rsplit()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the end of the string and works to the front.

##### rstrip

*rstrip()*

Return a copy of the string with trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### split

*split()*

Return a list of the substrings in the string, using sep as the separator string.

sep
The separator used to split the string.

```none
When set to None (the default value), will split on any whitespace
character (including \n \r \t \f and spaces) and will discard
empty strings from the result.
```

maxsplit
Maximum number of splits.
-1 (the default value) means no limit.

Splitting starts at the front of the string and works to the end.

Note, str.split() is mainly useful for data that has been intentionally
delimited.  With natural text that includes punctuation, consider using
the regular expression module.

##### splitlines

*splitlines()*

Return a list of the lines in the string, breaking at line boundaries.

Line breaks are not included in the resulting list unless keepends is given and
true.

##### startswith

*startswith()*

S.startswith(prefix[, start[, end]]) -> bool

Return True if S starts with the specified prefix, False otherwise.
With optional start, test S beginning at that position.
With optional end, stop comparing S at that position.
prefix can also be a tuple of strings to try.

##### strip

*strip()*

Return a copy of the string with leading and trailing whitespace removed.

If chars is given and not None, remove characters in chars instead.

##### swapcase

*swapcase()*

Convert uppercase characters to lowercase and lowercase characters to uppercase.

##### title

*title()*

Return a version of the string where each word is titlecased.

More specifically, words start with uppercased characters and all remaining
cased characters have lower case.

##### translate

*translate()*

Replace each character in the string using the given translation table.

table
Translation table, which must be a mapping of Unicode ordinals to
Unicode ordinals, strings, or None.

The table must implement lookup/indexing via **getitem**, for instance a
dictionary or list.  If this operation raises LookupError, the character is
left untouched.  Characters mapped to None are deleted.

##### upper

*upper()*

Return a copy of the string converted to uppercase.

##### zfill

*zfill()*

Pad a numeric string with zeros on the left, to fill a field of the given width.

The string is never truncated.

##### algopy.op.addw

*algopy.op.addw(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [algopy.UInt64](api-algopy.md#algopy.UInt64)]*

A plus B as a 128-bit result. X is the carry-bit, Y is the low-order 64 bits.

Native TEAL opcode: [`addw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#addw)

##### algopy.op.app_opted_in

*algopy.op.app_opted_in(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.Application](api-algopy.md#algopy.Application) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

1 if account A is opted in to application B, else 0
params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset). Return: 1 if opted in and 0 otherwise.

Native TEAL opcode: [`app_opted_in`](https://dev.algorand.co/reference/algorand-teal/opcodes/#app_opted_in)

##### algopy.op.arg

*algopy.op.arg(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Ath LogicSig argument

Native TEAL opcode: [`arg`](https://dev.algorand.co/reference/algorand-teal/opcodes/#arg), [`args`](https://dev.algorand.co/reference/algorand-teal/opcodes/#args)

##### algopy.op.balance

*algopy.op.balance(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

balance for account A, in microalgos. The balance is observed after the effects of previous transactions in the group, and after the fee for the current transaction is deducted. Changes caused by inner transactions are observable immediately following `itxn_submit`
params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset). Return: value.

Native TEAL opcode: [`balance`](https://dev.algorand.co/reference/algorand-teal/opcodes/#balance)

##### algopy.op.base64_decode

*algopy.op.base64_decode(e: [algopy.op.Base64](#algopy.op.Base64), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

decode A which was base64-encoded using *encoding* E. Fail if A is not base64 encoded with encoding E
*Warning*: Usage should be restricted to very rare use cases. In almost all cases, smart contracts should directly handle non-encoded byte-strings. This opcode should only be used in cases where base64 is the only available option, e.g. interoperability with a third-party that only signs base64 strings.

Decodes A using the base64 encoding E. Specify the encoding with an immediate arg either as URL and Filename Safe (`URLEncoding`) or Standard (`StdEncoding`). See [RFC 4648 sections 4 and 5](https://rfc-editor.org/rfc/rfc4648.html#section-4). It is assumed that the encoding ends with the exact number of `=` padding characters as required by the RFC. When padding occurs, any unused pad bits in the encoding must be set to zero or the decoding will fail. The special cases of `\n` and `\r` are allowed but completely ignored. An error will result when attempting to decode a string with a character that is not in the encoding alphabet or not one of `=`, `\r`, or `\n`.

* **Parameters:**
  **e** ([*Base64*](#algopy.op.Base64)) – encoding index

Native TEAL opcode: [`base64_decode`](https://dev.algorand.co/reference/algorand-teal/opcodes/#base64_decode)

##### algopy.op.bitlen

*algopy.op.bitlen(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The highest set bit in A. If A is a byte-array, it is interpreted as a big-endian unsigned integer. bitlen of 0 is 0, bitlen of 8 is 4
bitlen interprets arrays as big-endian integers, unlike setbit/getbit

Native TEAL opcode: [`bitlen`](https://dev.algorand.co/reference/algorand-teal/opcodes/#bitlen)

##### algopy.op.bsqrt

*algopy.op.bsqrt(a: [algopy.BigUInt](api-algopy.md#algopy.BigUInt) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.BigUInt](api-algopy.md#algopy.BigUInt)*

The largest integer I such that I^2 <= A. A and I are interpreted as big-endian unsigned integers

Native TEAL opcode: [`bsqrt`](https://dev.algorand.co/reference/algorand-teal/opcodes/#bsqrt)

##### algopy.op.btoi

*algopy.op.btoi(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

converts big-endian byte array A to uint64. Fails if len(A) > 8. Padded by leading 0s if len(A) < 8.
`btoi` fails if the input is longer than 8 bytes.

Native TEAL opcode: [`btoi`](https://dev.algorand.co/reference/algorand-teal/opcodes/#btoi)

##### algopy.op.bzero

*algopy.op.bzero(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

zero filled byte-array of length A

Native TEAL opcode: [`bzero`](https://dev.algorand.co/reference/algorand-teal/opcodes/#bzero)

##### algopy.op.concat

*algopy.op.concat(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

join A and B
`concat` fails if the result would be greater than 4096 bytes.

Native TEAL opcode: [`concat`](https://dev.algorand.co/reference/algorand-teal/opcodes/#concat)

##### algopy.op.divmodw

*algopy.op.divmodw(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), d: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [algopy.UInt64](api-algopy.md#algopy.UInt64), [algopy.UInt64](api-algopy.md#algopy.UInt64), [algopy.UInt64](api-algopy.md#algopy.UInt64)]*

W,X = (A,B / C,D); Y,Z = (A,B modulo C,D)
The notation J,K indicates that two uint64 values J and K are interpreted as a uint128 value, with J as the high uint64 and K the low.

Native TEAL opcode: [`divmodw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#divmodw)

##### algopy.op.divw

*algopy.op.divw(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

A,B / C. Fail if C == 0 or if result overflows.
The notation A,B indicates that A and B are interpreted as a uint128 value, with A as the high uint64 and B the low.

Native TEAL opcode: [`divw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#divw)

##### algopy.op.ecdsa_pk_decompress

*algopy.op.ecdsa_pk_decompress(v: [algopy.op.ECDSA](#algopy.op.ECDSA), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [algopy.Bytes](api-algopy.md#algopy.Bytes)]*

decompress pubkey A into components X, Y
The 33 byte public key in a compressed form to be decompressed into X and Y (top) components. All values are big-endian encoded.

* **Parameters:**
  **v** ([*ECDSA*](#algopy.op.ECDSA)) – curve index

Native TEAL opcode: [`ecdsa_pk_decompress`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ecdsa_pk_decompress)

##### algopy.op.ecdsa_pk_recover

*algopy.op.ecdsa_pk_recover(v: [algopy.op.ECDSA](#algopy.op.ECDSA), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), d: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [algopy.Bytes](api-algopy.md#algopy.Bytes)]*

for (data A, recovery id B, signature C, D) recover a public key
S (top) and R elements of a signature, recovery id and data (bottom) are expected on the stack and used to deriver a public key. All values are big-endian encoded. The signed data must be 32 bytes long.

* **Parameters:**
  **v** ([*ECDSA*](#algopy.op.ECDSA)) – curve index

Native TEAL opcode: [`ecdsa_pk_recover`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ecdsa_pk_recover)

##### algopy.op.ecdsa_verify

*algopy.op.ecdsa_verify(v: [algopy.op.ECDSA](#algopy.op.ECDSA), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), d: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), e: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

for (data A, signature B, C and pubkey D, E) verify the signature of the data against the pubkey => {0 or 1}
The 32 byte Y-component of a public key is the last element on the stack, preceded by X-component of a pubkey, preceded by S and R components of a signature, preceded by the data that is fifth element on the stack. All values are big-endian encoded. The signed data must be 32 bytes long, and signatures in lower-S form are only accepted.

* **Parameters:**
  **v** ([*ECDSA*](#algopy.op.ECDSA)) – curve index

Native TEAL opcode: [`ecdsa_verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ecdsa_verify)

##### algopy.op.ed25519verify

*algopy.op.ed25519verify(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

for (data A, signature B, pubkey C) verify the signature of (“ProgData” || program_hash || data) against the pubkey => {0 or 1}
The 32 byte public key is the last element on the stack, preceded by the 64 byte signature at the second-to-last element on the stack, preceded by the data which was signed at the third-to-last element on the stack.

Native TEAL opcode: [`ed25519verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ed25519verify)

##### algopy.op.ed25519verify_bare

*algopy.op.ed25519verify_bare(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

for (data A, signature B, pubkey C) verify the signature of the data against the pubkey => {0 or 1}

Native TEAL opcode: [`ed25519verify_bare`](https://dev.algorand.co/reference/algorand-teal/opcodes/#ed25519verify_bare)

##### algopy.op.err

*algopy.op.err() → [Never](https://docs.python.org/3/library/typing.html#typing.Never)*

Fail immediately.

* **Returns typing.Never:**
  Halts program

Native TEAL opcode: [`err`](https://dev.algorand.co/reference/algorand-teal/opcodes/#err)

##### algopy.op.exit

*algopy.op.exit(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [Never](https://docs.python.org/3/library/typing.html#typing.Never)*

use A as success value; end

* **Returns typing.Never:**
  Halts program

Native TEAL opcode: [`return`](https://dev.algorand.co/reference/algorand-teal/opcodes/#return)

##### algopy.op.exp

*algopy.op.exp(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

A raised to the Bth power. Fail if A == B == 0 and on overflow

Native TEAL opcode: [`exp`](https://dev.algorand.co/reference/algorand-teal/opcodes/#exp)

##### algopy.op.expw

*algopy.op.expw(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [algopy.UInt64](api-algopy.md#algopy.UInt64)]*

A raised to the Bth power as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low. Fail if A == B == 0 or if the results exceeds 2^128-1

Native TEAL opcode: [`expw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#expw)

##### algopy.op.extract

*algopy.op.extract(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

A range of bytes from A starting at B up to but not including B+C. If B+C is larger than the array length, the program fails
`extract3` can be called using `extract` with no immediates.

Native TEAL opcode: [`extract`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract), [`extract3`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract3)

##### algopy.op.extract_uint16

*algopy.op.extract_uint16(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

A uint16 formed from a range of big-endian bytes from A starting at B up to but not including B+2. If B+2 is larger than the array length, the program fails

Native TEAL opcode: [`extract_uint16`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract_uint16)

##### algopy.op.extract_uint32

*algopy.op.extract_uint32(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

A uint32 formed from a range of big-endian bytes from A starting at B up to but not including B+4. If B+4 is larger than the array length, the program fails

Native TEAL opcode: [`extract_uint32`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract_uint32)

##### algopy.op.extract_uint64

*algopy.op.extract_uint64(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

A uint64 formed from a range of big-endian bytes from A starting at B up to but not including B+8. If B+8 is larger than the array length, the program fails

Native TEAL opcode: [`extract_uint64`](https://dev.algorand.co/reference/algorand-teal/opcodes/#extract_uint64)

##### algopy.op.falcon_verify

*algopy.op.falcon_verify(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

for (data A, compressed-format signature B, pubkey C) verify the signature of data against the pubkey => {0 or 1}
Min AVM version: 12

Native TEAL opcode: [`falcon_verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#falcon_verify)

##### algopy.op.gaid

*algopy.op.gaid(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

ID of the asset or application created in the Ath transaction of the current group
`gaids` fails unless the requested transaction created an asset or application and A < GroupIndex.

Native TEAL opcode: [`gaid`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gaid), [`gaids`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gaids)

##### algopy.op.getbit

*algopy.op.getbit(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [bool](https://docs.python.org/3/library/functions.html#bool)*

Bth bit of (byte-array or integer) A. If B is greater than or equal to the bit length of the value (8\*byte length), the program fails
see explanation of bit ordering in setbit

Native TEAL opcode: [`getbit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#getbit)

##### algopy.op.getbyte

*algopy.op.getbyte(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Bth byte of A, as an integer. If B is greater than or equal to the array length, the program fails

Native TEAL opcode: [`getbyte`](https://dev.algorand.co/reference/algorand-teal/opcodes/#getbyte)

##### algopy.op.gload_bytes

*algopy.op.gload_bytes(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Bth scratch space value of the Ath transaction in the current group

Native TEAL opcode: [`gload`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gload), [`gloads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloads), [`gloadss`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloadss)

##### algopy.op.gload_uint64

*algopy.op.gload_uint64(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Bth scratch space value of the Ath transaction in the current group

Native TEAL opcode: [`gload`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gload), [`gloads`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloads), [`gloadss`](https://dev.algorand.co/reference/algorand-teal/opcodes/#gloadss)

##### algopy.op.itob

*algopy.op.itob(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

converts uint64 A to big-endian byte array, always of length 8

Native TEAL opcode: [`itob`](https://dev.algorand.co/reference/algorand-teal/opcodes/#itob)

##### algopy.op.keccak256

*algopy.op.keccak256(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Keccak256 hash of value A, yields [32]byte

Native TEAL opcode: [`keccak256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#keccak256)

##### algopy.op.mimc

*algopy.op.mimc(c: [algopy.op.MiMCConfigurations](#algopy.op.MiMCConfigurations), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

MiMC hash of scalars A, using curve and parameters specified by configuration C
A is a list of concatenated 32 byte big-endian unsigned integer scalars.  Fail if A’s length is not a multiple of 32 or any element exceeds the curve modulus.

The MiMC hash function has known collisions since any input which is a multiple of the elliptic curve modulus will hash to the same value. MiMC is thus not a general purpose hash function, but meant to be used in zero knowledge applications to match a zk-circuit implementation.
Min AVM version: 11

* **Parameters:**
  **c** ([*MiMCConfigurations*](#algopy.op.MiMCConfigurations)) – configuration index

Native TEAL opcode: [`mimc`](https://dev.algorand.co/reference/algorand-teal/opcodes/#mimc)

##### algopy.op.min_balance

*algopy.op.min_balance(a: [algopy.Account](api-algopy.md#algopy.Account) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

minimum required balance for account A, in microalgos. Required balance is affected by ASA, App, and Box usage. When creating or opting into an app, the minimum balance grows before the app code runs, therefore the increase is visible there. When deleting or closing out, the minimum balance decreases after the app executes. Changes caused by inner transactions or box usage are observable immediately following the opcode effecting the change.
params: Txn.Accounts offset (or, since v4, an *available* account address), *available* application id (or, since v4, a Txn.ForeignApps offset). Return: value.

Native TEAL opcode: [`min_balance`](https://dev.algorand.co/reference/algorand-teal/opcodes/#min_balance)

##### algopy.op.mulw

*algopy.op.mulw(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.UInt64](api-algopy.md#algopy.UInt64), [algopy.UInt64](api-algopy.md#algopy.UInt64)]*

A times B as a 128-bit result in two uint64s. X is the high 64 bits, Y is the low

Native TEAL opcode: [`mulw`](https://dev.algorand.co/reference/algorand-teal/opcodes/#mulw)

##### algopy.op.online_stake

*algopy.op.online_stake() → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

the total online stake in the agreement round
Min AVM version: 11

Native TEAL opcode: [`online_stake`](https://dev.algorand.co/reference/algorand-teal/opcodes/#online_stake)

##### algopy.op.replace

*algopy.op.replace(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Copy of A with the bytes starting at B replaced by the bytes of C. Fails if B+len(C) exceeds len(A)
`replace3` can be called using `replace` with no immediates.

Native TEAL opcode: [`replace2`](https://dev.algorand.co/reference/algorand-teal/opcodes/#replace2), [`replace3`](https://dev.algorand.co/reference/algorand-teal/opcodes/#replace3)

##### algopy.op.select_bytes

*algopy.op.select_bytes(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), c: [bool](https://docs.python.org/3/library/functions.html#bool) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

selects one of two values based on top-of-stack: B if C != 0, else A

Native TEAL opcode: [`select`](https://dev.algorand.co/reference/algorand-teal/opcodes/#select)

##### algopy.op.select_uint64

*algopy.op.select_uint64(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [bool](https://docs.python.org/3/library/functions.html#bool) | [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

selects one of two values based on top-of-stack: B if C != 0, else A

Native TEAL opcode: [`select`](https://dev.algorand.co/reference/algorand-teal/opcodes/#select)

##### algopy.op.setbit_bytes

*algopy.op.setbit_bytes(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [bool](https://docs.python.org/3/library/functions.html#bool), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8\*byte length), the program fails
When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.

Native TEAL opcode: [`setbit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#setbit)

##### algopy.op.setbit_uint64

*algopy.op.setbit_uint64(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [bool](https://docs.python.org/3/library/functions.html#bool), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

Copy of (byte-array or integer) A, with the Bth bit set to (0 or 1) C. If B is greater than or equal to the bit length of the value (8\*byte length), the program fails
When A is a uint64, index 0 is the least significant bit. Setting bit 3 to 1 on the integer 0 yields 8, or 2^3. When A is a byte array, index 0 is the leftmost bit of the leftmost byte. Setting bits 0 through 11 to 1 in a 4-byte-array of 0s yields the byte array 0xfff00000. Setting bit 3 to 1 on the 1-byte-array 0x00 yields the byte array 0x10.

Native TEAL opcode: [`setbit`](https://dev.algorand.co/reference/algorand-teal/opcodes/#setbit)

##### algopy.op.setbyte

*algopy.op.setbyte(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

Copy of A with the Bth byte set to small integer (between 0..255) C. If B is greater than or equal to the array length, the program fails

Native TEAL opcode: [`setbyte`](https://dev.algorand.co/reference/algorand-teal/opcodes/#setbyte)

##### algopy.op.sha256

*algopy.op.sha256(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

SHA256 hash of value A, yields [32]byte

Native TEAL opcode: [`sha256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sha256)

##### algopy.op.sha3_256

*algopy.op.sha3_256(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

SHA3_256 hash of value A, yields [32]byte

Native TEAL opcode: [`sha3_256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sha3_256)

##### algopy.op.sha512_256

*algopy.op.sha512_256(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

SHA512_256 hash of value A, yields [32]byte

Native TEAL opcode: [`sha512_256`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sha512_256)

##### algopy.op.shl

*algopy.op.shl(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

A times 2^B, modulo 2^64

Native TEAL opcode: [`shl`](https://dev.algorand.co/reference/algorand-teal/opcodes/#shl)

##### algopy.op.shr

*algopy.op.shr(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

A divided by 2^B

Native TEAL opcode: [`shr`](https://dev.algorand.co/reference/algorand-teal/opcodes/#shr)

##### algopy.op.sqrt

*algopy.op.sqrt(a: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.UInt64](api-algopy.md#algopy.UInt64)*

The largest integer I such that I^2 <= A

Native TEAL opcode: [`sqrt`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sqrt)

##### algopy.op.substring

*algopy.op.substring(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), c: [algopy.UInt64](api-algopy.md#algopy.UInt64) | [int](https://docs.python.org/3/library/functions.html#int), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

A range of bytes from A starting at B up to but not including C. If C < B, or either is larger than the array length, the program fails

Native TEAL opcode: [`substring`](https://dev.algorand.co/reference/algorand-teal/opcodes/#substring), [`substring3`](https://dev.algorand.co/reference/algorand-teal/opcodes/#substring3)

##### algopy.op.sumhash512

*algopy.op.sumhash512(a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [algopy.Bytes](api-algopy.md#algopy.Bytes)*

sumhash512 of value A, yields [64]byte
Min AVM version: 13

Native TEAL opcode: [`sumhash512`](https://dev.algorand.co/reference/algorand-teal/opcodes/#sumhash512)

##### algopy.op.vrf_verify

*algopy.op.vrf_verify(s: [algopy.op.VrfVerify](#algopy.op.VrfVerify), a: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), b: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), c: [algopy.Bytes](api-algopy.md#algopy.Bytes) | [bytes](https://docs.python.org/3/library/stdtypes.html#bytes), /) → [tuple](https://docs.python.org/3/library/stdtypes.html#tuple)[[algopy.Bytes](api-algopy.md#algopy.Bytes), [bool](https://docs.python.org/3/library/functions.html#bool)]*

Verify the proof B of message A against pubkey C. Returns vrf output and verification flag.
`VrfAlgorand` is the VRF used in Algorand. It is ECVRF-ED25519-SHA512-Elligator2, specified in the IETF internet draft [draft-irtf-cfrg-vrf-03](https://datatracker.ietf.org/doc/draft-irtf-cfrg-vrf/03/).

* **Parameters:**
  **s** ([*VrfVerify*](#algopy.op.VrfVerify)) – parameters index

Native TEAL opcode: [`vrf_verify`](https://dev.algorand.co/reference/algorand-teal/opcodes/#vrf_verify)
