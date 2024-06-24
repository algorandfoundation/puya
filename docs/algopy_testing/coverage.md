# Coverage

See which stubs are implemented completely (pure functions), which are mockable (via context manager), and which are not.

| Name                                        | Implementation Status | Mockable Representation |
| ------------------------------------------- | --------------------- | ----------------------- |
| Primitives (UInt64, BigUInt, Bytes, String) | Fully Implemented     | Yes                     |
| Asset                                       | Partially Implemented | Yes                     |
| Account                                     | Partially Implemented | Yes                     |
| Application                                 | Partially Implemented | Yes                     |
| urange                                      | Fully Implemented     | Yes                     |
| subroutine                                  | Fully Implemented     | Yes                     |
| op. (most operations)                       | Fully Implemented     | Yes                     |
| Txn, GTxn, ITxn                             | Fully Implemented     | Yes                     |
| Global                                      | Fully Implemented     | Yes                     |
| Box                                         | Fully Implemented     | Yes                     |
| Block                                       | Fully Implemented     | Yes                     |
| logicsig                                    | Fully Implemented     | Yes                     |
| log                                         | Fully Implemented     | Yes                     |
| itxn. (inner transactions)                  | Fully Implemented     | Yes                     |
| gtxn. (group transactions)                  | Fully Implemented     | Yes                     |
| ensure_budget                               | Fully Implemented     | Yes                     |
| arc4. (most ARC4 features)                  | Fully Implemented     | Yes                     |
| uenumerate                                  | Not Implemented       | Yes                     |
| op.ITxnCreate                               | Not Implemented       | Yes                     |
| op.EllipticCurve                            | Not Implemented       | Yes                     |
| op.AssetParamsGet                           | Not Implemented       | Yes                     |
| op.AppParamsGet                             | Not Implemented       | Yes                     |
| op.AppLocal                                 | Not Implemented       | Yes                     |
| op.AppGlobal                                | Not Implemented       | Yes                     |
| op.AcctParamsGet                            | Not Implemented       | Yes                     |
| itxn.ApplicationCallInnerTransaction        | Not Implemented       | Yes                     |
| arc4.UFixedNxM                              | Not Implemented       | Yes                     |
| arc4.BigUFixedNxM                           | Not Implemented       | Yes                     |
| arc4.ARC4Contract                           | Not Implemented       | Yes                     |
| StateTotals                                 | Not Implemented       | Yes                     |
