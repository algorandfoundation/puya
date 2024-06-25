# Coverage

See which `algorand-python` stubs are implemented by the `algorand-python-testing` library. There are 3 general categories:

1. **Implemented**: Full native Python equivalent matching AVM computation. For example, `algopy.op.sha256` and other cryptographic operations behave identically in AVM and unit tests written with this library.

2. **Emulated**: Implemented with the aid of the `AlgopyTestContext` manager, which mimics major AVM behavior to allow this abstraction to function as expected in a test context. For example, when you call `Box.put` on an `algopy.Box` object within a test context, it won't interact with the real Algorand network. Instead, it will store the data in the test context manager behind the scenes, while still providing the same interface as the real `Box` class.

3. **Mockable**: No implementation provided, but can be easily mocked or patched to inject intended behavior. For example, `algopy.abi_call` can be mocked to return or act as needed; otherwise, it will raise a "not implemented" exception. Mockable types are exceptional cases where behavior or functionality does not make sense within a unit testing context or would require an unnecessary amount of complexity without significant benefit to the end user (a developer writing offline unit tests).

> Note, below table not exhaustive yet, but will be expanded along with initial stable release.

| Name                                                         | Implementation Status |
| ------------------------------------------------------------ | --------------------- |
| Primitives (UInt64, BigUInt, Bytes, String)                  | Implemented           |
| urange                                                       | Implemented           |
| All crypto ops in op.\* namespace (to be expanded in detail) | Implemented           |
| Txn, GTxn, ITxn                                              | Implemented           |
| arc4.\* namespace (to be expanded in detail)                 | Implemented           |
| uenumerate                                                   | Implemented           |
| op.ITxnCreate                                                | Implemented           |
| StateTotals                                                  | Implemented           |
| Asset                                                        | Emulated              |
| Account                                                      | Emulated              |
| Application                                                  | Emulated              |
| subroutine                                                   | Emulated              |
| Global                                                       | Emulated              |
| Box                                                          | Emulated              |
| Block                                                        | Emulated              |
| logicsig                                                     | Emulated              |
| log                                                          | Emulated              |
| itxn.\* namespace (inner transactions)                       | Emulated              |
| gtxn.\* namespace (group transactions)                       | Emulated              |
| ensure_budget                                                | Mockable              |
| op.EllipticCurve                                             | Mockable              |
| op.AssetParamsGet                                            | Mockable              |
| op.AppParamsGet                                              | Mockable              |
| op.AppLocal                                                  | Mockable              |
| op.AppGlobal                                                 | Mockable              |
| op.AcctParamsGet                                             | Mockable              |
