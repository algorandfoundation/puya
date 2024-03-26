# CHANGELOG


## v0.7.0 (2024-03-26)

### Feature

* separate stubs into their own wheel (#154) ([`9c58ae5`](https://github.com/algorandfoundation/puya/commit/9c58ae5c317a84441132400802f59fff8312c622))

* Allow mutable tuple items to be updated ([`8ea6ed5`](https://github.com/algorandfoundation/puya/commit/8ea6ed5f6580e8df4beede02d3ce3cac5869fd4a))

* warn if a Contract class is implicitly abstract ([`4d6317f`](https://github.com/algorandfoundation/puya/commit/4d6317f10e7e814908ceea2bfa81a78038037975))

* compare `arc4.Address` against `Account` ([`3888220`](https://github.com/algorandfoundation/puya/commit/3888220c6e40a69a2b115db3e46b864915e32183))

* empty constructor for arc4 numeric types, defaults to zero ([`c514753`](https://github.com/algorandfoundation/puya/commit/c514753ee24ad11b67853f81a0cd108a08ab2741))

* allow bytes literal with `BytesBacked.from_bytes` ([`d47be8c`](https://github.com/algorandfoundation/puya/commit/d47be8c8b48b765cb23bb1e5467b0d72b9699309))

* empty constructor for BigUInt() defaults to zero ([`c02079b`](https://github.com/algorandfoundation/puya/commit/c02079b5d84af851ed2fdab2d649eb26a41d2619))

* empty constructor for UInt64() defaults to zero ([`6f79b8a`](https://github.com/algorandfoundation/puya/commit/6f79b8a2c71223b11895ae7dafd8696afc004a92))

* simplify more conditions when we&#39;re in a `select` context ([`7403e7b`](https://github.com/algorandfoundation/puya/commit/7403e7b4fa664f41ccacad8f0500f98d90c19e1d))

* simplify more conditions when we&#39;re in a ConditionalBranch context ([`80f0167`](https://github.com/algorandfoundation/puya/commit/80f0167ed04fc1f2c6af28df26d7ea11fad5f1b7))

* simplify more conditions when we&#39;re in an assert context ([`7f89b6c`](https://github.com/algorandfoundation/puya/commit/7f89b6c706e73a7e87f01e9c762ec57a922e8060))

* allow bytes optimizations to handle `addr` constants, and also `global ZeroAddress` ops ([`a508274`](https://github.com/algorandfoundation/puya/commit/a5082740f8be9a573c4d5ef45b11a08c4e855dc8))

* Allow empty constructors to default to &#34;zero&#34; values for Account, Asset, Application, and arc4.Address ([`3ad9c18`](https://github.com/algorandfoundation/puya/commit/3ad9c18f6732e11323159fe143a4b1f7eb006818))

* Add a validation step to confirm ops used in an app or lsig are available for those respecitve modes ([`8600d4e`](https://github.com/algorandfoundation/puya/commit/8600d4e2dd45dc3e798c31beb58775ba8a14b4cd))

* add empty `arc4.Bool` constructor to mimic `bool()` ([`6175b59`](https://github.com/algorandfoundation/puya/commit/6175b594d3de06a0b00aef41e9dd9c7dea82d9c0))

* remove `encode()` from ARC4 types, an ensure constructors take appropriate values. Ensure all ARC4 types have `from_log` classmethod. Remove `decode()` method and instead have a `native` property that returns decoded values where appropriate ([`146748e`](https://github.com/algorandfoundation/puya/commit/146748e1c09d5493dbd33acc74bfd4684734ad02))

* Allow arc4 types to be used in native tuples in ABI methods ([`0948d83`](https://github.com/algorandfoundation/puya/commit/0948d83f7051b73f0ca84a62ff4718f0a174a2ec))

* add class options for declaring storage values used in ARC32 specifications (#123) ([`5721f4a`](https://github.com/algorandfoundation/puya/commit/5721f4a5e31c58c1a2d9614bc0ff8eaf6c928474))

* allow primitive String type to be used in arc4 methods ([`23fa701`](https://github.com/algorandfoundation/puya/commit/23fa7016997b24a14828fb69e5cb52c211e93fd5))

* add startswith, endswith, and join to String ([`262c679`](https://github.com/algorandfoundation/puya/commit/262c679c208cf2202d65e6b628598e95063a5f12))

* add primitive UTF-8 String type ([`14d35c6`](https://github.com/algorandfoundation/puya/commit/14d35c6a699b6aa54eae1824b9fed3ecd4d91c5b))

* add support for emitting ARC-28 events ([`aa4a651`](https://github.com/algorandfoundation/puya/commit/aa4a6516f2a144545824df7ce31c48ecb1ba13f4))

* allow TEAL optimizer to handle dup/dupn ops when removing stack shuffling of constants, and collapse any repeated elements with a dup/dupn ([`b48db43`](https://github.com/algorandfoundation/puya/commit/b48db43b5be917b534f40f7d37ec8c1ce6e34891))

* added `puyapy.arc4.call_abi` for typed contract to contract calls (#112) ([`3d42df3`](https://github.com/algorandfoundation/puya/commit/3d42df36a29a3867081a79784ce554f6d66b085b))

* add optimization to propagate constants found in Phi nodes resolving to the same constant value ([`1b2e504`](https://github.com/algorandfoundation/puya/commit/1b2e504a8a874323b9519fe94f1f41da54277ed4))

* add is_opted_in method to Account type (#126) ([`e21dc55`](https://github.com/algorandfoundation/puya/commit/e21dc55779fbd18e432a5e57b9e4535be64a8820))

* allow `gtxn.Transaction` as an ABI argument (#127) ([`e31eda8`](https://github.com/algorandfoundation/puya/commit/e31eda8c072bee1efa203427857c39257e2cbd56))

* add asset and application reference types to op module (#124) ([`47741ab`](https://github.com/algorandfoundation/puya/commit/47741ab127aacee6bad6d377053df345cae0f9fb))

* Template variables ([`9d93fee`](https://github.com/algorandfoundation/puya/commit/9d93fee8a089cc894c025d376c51514c789d5a1a))

* pop/popn collapse optimisation ([`0b90505`](https://github.com/algorandfoundation/puya/commit/0b905050313c7eaf88df7af0496f2dcb344e2774))

* Allow slicing Bytes with UInt64. Code generation has also been improved for slicing, and a potential double-evaluation has been fixed. ([`0f9dd79`](https://github.com/algorandfoundation/puya/commit/0f9dd7973283c0268ad94dc30505fe7a0f213e7c))

* implement ordering comparisons for arc4.UIntN and arc4.BigUIntN types ([`f83a397`](https://github.com/algorandfoundation/puya/commit/f83a397caaf938a15be60a1df7307115faa986dc))

* implement missing optimisations for self comparisons ([`24ead20`](https://github.com/algorandfoundation/puya/commit/24ead203c508971fc61d516dfda3a309e355245d))

* improved constant folding, particularly with ARC4 operations ([`17216c4`](https://github.com/algorandfoundation/puya/commit/17216c433a071fb04a5f8bc372de5fbc65544ea7))

* optimisation of extract_uint16/32/64 with constants ([`bf00f0d`](https://github.com/algorandfoundation/puya/commit/bf00f0d40c49ff906aedf2c8f9adfd069659e08e))

* allow optimisation to concat bytes with different encodings ([`e3c6253`](https://github.com/algorandfoundation/puya/commit/e3c6253553f39ea9aa4629a6d859494c274bde29))

* allow itob of a constant to flow through further optimisations ([`ea2ce28`](https://github.com/algorandfoundation/puya/commit/ea2ce28c061cbbb12c2537cf5ea4449d4dcdcca8))

* implement boolean evaluation of ARC4 types ([`aaa32ad`](https://github.com/algorandfoundation/puya/commit/aaa32adafb4b3b355845095162bb34db23e3c637))

* Local/GlobalState custom keys &amp; descriptions ([`e9d5084`](https://github.com/algorandfoundation/puya/commit/e9d5084c472c4ffffc015d530f049627e2f878f1))

* add version option to CLI ([`44b5e7f`](https://github.com/algorandfoundation/puya/commit/44b5e7fb2d83d91a6f2462e4b5b71aeaed7df3fe))

### Fix

* Improve coverage of arc4_copy validator ([`b482ebe`](https://github.com/algorandfoundation/puya/commit/b482ebe12a07389e609b92d5ba57184b44130466))

* arc4.String() gets incorrectly inferred as native String wtype ([`4b12156`](https://github.com/algorandfoundation/puya/commit/4b12156a311cd37b133df192a21bc4da27cf7e4f))

* ensure all `index_multiple` methods have the same signature ([`0c93a47`](https://github.com/algorandfoundation/puya/commit/0c93a47a6f155f3fee42249d0e4a1077557d490c))

* treat ARC4 Tuples with mutable elements as mutable overall ([`7f7a4b6`](https://github.com/algorandfoundation/puya/commit/7f7a4b620ddd52f8fc58bf55e06171345fb875d3))

* fix source location for function signatures ([`14b9eb3`](https://github.com/algorandfoundation/puya/commit/14b9eb31a369f993596a46d053a9db1b57586e0b))

* use repr for literal validation errors ([`2d0feee`](https://github.com/algorandfoundation/puya/commit/2d0feee21828813eb3a67e19a24f2bf635972477))

* add some missing positional-only indicators to stubs, and relax typing.LiteralString to str, it&#39;s not really applicable for our use case ([`f5031a5`](https://github.com/algorandfoundation/puya/commit/f5031a5e88a72b397cbf2cc6ef82c46e3a61e630))

* don&#39;t implicitly map [32]byte to Account in stubs ([`668c2e0`](https://github.com/algorandfoundation/puya/commit/668c2e09afde4a5d372155921de1fa979cefe0c3))

* consistent usage of positional-only arguments in stubs ([`547d62c`](https://github.com/algorandfoundation/puya/commit/547d62c4d1f0f507d3dfda90a84affec94d44f50))

* produce error with incorrect arc4 numeric class usage based on bit-sizes ([`4cb6bbc`](https://github.com/algorandfoundation/puya/commit/4cb6bbc214f8dc1f402a8e2e196fe2115beab49a))

* check for state exceeding known consensus parameters and warn (not an error in case the consensus parameters update before a new compiler release) ([`d65b350`](https://github.com/algorandfoundation/puya/commit/d65b3506886e984e5d607319f2a69d712a19ed61))

* allow references to module constants in StateTotals args ([`550fbd3`](https://github.com/algorandfoundation/puya/commit/550fbd3a62d3929b2126baf8fdc66962269895b1))

* Fix optimizer bug where differing behaviour of extract with &amp; without immediates when length is zero was not accounted for ([`6a8db34`](https://github.com/algorandfoundation/puya/commit/6a8db34e9776502f4ce677ad7d5e470b23d619e6))

* handle tuple return types in method signatures ([`6d31a69`](https://github.com/algorandfoundation/puya/commit/6d31a696afc54ce09fa85ba0b540f4561abd012f))

* don&#39;t inline control ops of Switch or GotoNth nodes if it would result in additional copies in destructured SSA (#130) ([`189847d`](https://github.com/algorandfoundation/puya/commit/189847d0abe26cf9402231957b7fc5fc29026731))

* check for errors between each stage of compiler pipeline ([`b860e5a`](https://github.com/algorandfoundation/puya/commit/b860e5a5520e50c5b92dbe8c023a163046ad401c))

* no longer eliminate expressions outside of dominators in RCE optimization (#119) ([`b6bfc0a`](https://github.com/algorandfoundation/puya/commit/b6bfc0abcb745be02780086dc6182894e1c30bc4))

* Address unexpected Python behaviour in slicing, where end &gt; start would panic instead of returning an empty byte slice ([`52c1666`](https://github.com/algorandfoundation/puya/commit/52c16660985d1a6c46bbd688b0d0a930eb1f7f17))


## v0.6.0 (2024-02-20)

### Feature

* improve coalescing by performing before sequentialisation, thus reducing chances of interference ([`a29fba9`](https://github.com/algorandfoundation/puya/commit/a29fba9d859cf8f201efe4797309f5137cfbc6cd))

* reduce number of iterations required by optimiser by enabling fixed point iteration within ControlOp simplifier optimisation step ([`b7b27d3`](https://github.com/algorandfoundation/puya/commit/b7b27d3e9176c050140f1ad3b5ea66924dceb48a))

* add simple pass to collapse constants repeated &gt;= 2 times by using a dupn ([`47d90d6`](https://github.com/algorandfoundation/puya/commit/47d90d61c37c41de6244171a69b3cef5fdb32556))

* add duplicate block elimination as a post-SSA optimisation, at -O2 or above since it can mess with debugging info quite a bit ([`c13d8fe`](https://github.com/algorandfoundation/puya/commit/c13d8feedd55546d356348cef8acd81639fbb50f))

* add API for creating and submitting inner transactions (#98) ([`6b76183`](https://github.com/algorandfoundation/puya/commit/6b76183ef6ff15b3fa8ad9b9cde60f008d063a4b))

* move ops into their own module ([`7678a7e`](https://github.com/algorandfoundation/puya/commit/7678a7e862a76912b1792326532fadd08919453a))

* fix generated class names that are acronyms (#91) ([`bd3f222`](https://github.com/algorandfoundation/puya/commit/bd3f222904819205b87dce574d0bbbefc6409121))

### Fix

* reduce number of iterations required in TEAL optimiser ([`597b939`](https://github.com/algorandfoundation/puya/commit/597b9393ffa792ec0ddb2a684b10734d5c5910e6))

* reduce number of iterations required in RCE optimizer, and ensure dominator set is stable by sorting it ([`2af7135`](https://github.com/algorandfoundation/puya/commit/2af71351104b92a0cc8f9d126bb59cf2616ca320))

* if simplifying a control op by inlining a block then ensure successor phi arguments are also updated ([`bdbdb11`](https://github.com/algorandfoundation/puya/commit/bdbdb112b2aa526ae4f3a3246665f0fe8adfea30))


## v0.5.1 (2024-02-09)

### Performance

* prevent too many permutations during O2 stack optimizations (#85) ([`4dcdd6a`](https://github.com/algorandfoundation/puya/commit/4dcdd6aff6f511ef5a1a20588fb17bbf25cc3875))


## v0.5.0 (2024-02-06)

### Feature

* Check min_avm_version of intrinsic ops against target avm version for compiler ([`2b3dea0`](https://github.com/algorandfoundation/puya/commit/2b3dea0dcc183111b97ea611d7d6054f861ea304))

* update langspec to v10 ([`be62082`](https://github.com/algorandfoundation/puya/commit/be62082e11d8c3438e7b9da50c26263801a53ed0))

* Optimise constant mod expressions and pre-check for div 0 errors ([`24c5020`](https://github.com/algorandfoundation/puya/commit/24c5020e42b40fef7bdb955a5512879e1df5108d))

### Fix

* Use `Bytes` as the return type where the langspec lists `[32]byte` instead of `Account` ([`41bead7`](https://github.com/algorandfoundation/puya/commit/41bead737514a47450b4052248bd607894010a25))

* improve error output when parsing fails ([`c3d8f25`](https://github.com/algorandfoundation/puya/commit/c3d8f2581a7186bcca643104d5dc0d57a50b317d))

* Don&#39;t unnecessarilly pre-check uranges for forward iteration ([`066088c`](https://github.com/algorandfoundation/puya/commit/066088ce1b205c77e3181be75d7a5a9d32c26a51))

* Don&#39;t raise on div 0 in optimizer as the operation might be pre-checked for != 0 in previous operations ([`6d549ed`](https://github.com/algorandfoundation/puya/commit/6d549edc2b528f19bab47cf00cf47ddc8d4c8a8b))


## v0.4.0 (2024-01-31)

### Feature

* Add scratch space API (#56) ([`ad09eb8`](https://github.com/algorandfoundation/puya/commit/ad09eb8752d4b4ffd74c70a911e38666da4c7245))

### Fix

* fix argument matching order for gtxn, gtxna, gtxnsa, gtxnas. ([`6d10fef`](https://github.com/algorandfoundation/puya/commit/6d10fef805a7e3a667a0e851387df1c09170b6c3))

* correct intrinsic mapping for `RenamedOpCode` types, so that the correct overload gets chosen. This is particularly important for extract, where a 0 immediate for length (along with an immediate for start) behaves very differently to the stack based variant. There is still potential for confusion if the start parameter is a literal vs a constant UInt64, but this at least fixes the inability to get the correct result with the right set of args. ([`7bf88e3`](https://github.com/algorandfoundation/puya/commit/7bf88e3056f80657f30a5eb2be41c7c93086b305))

* fix potential bug when removing an empty entry block that had a goto which was not the next block ([`11c6a3e`](https://github.com/algorandfoundation/puya/commit/11c6a3ecff24a41f6a04d36ec78b2cd64d72557c))

* Add slot range validation to range expressions which specify a step ([`3ccd47f`](https://github.com/algorandfoundation/puya/commit/3ccd47f76289fcea66cdb7199961c2b181b9b318))


## v0.3.0 (2024-01-22)

### Fix

* validate_awst was not called as part of testing ([`71e9fbc`](https://github.com/algorandfoundation/puya/commit/71e9fbca2a445c7222436fc81648fe9cb47f33e7))

* UnusedRegisterCollector no longer visits a Phi&#39;s register, so it can be considered as a potential unused register ([`8b0e91a`](https://github.com/algorandfoundation/puya/commit/8b0e91a1e3fc524e0056f6189879e08edede7741))

* IntrinsicSimplifier now visits source values on Assignment ops ([`2da337e`](https://github.com/algorandfoundation/puya/commit/2da337ea4e84b54eb5a82fd97306b0ead6fdaf91))

* Enforce copying of arc4 mutable types when passing them around so that developers are not fooled by the illusion of reference imutability as arc4 encoded data is still a value type underneath ([`c20e621`](https://github.com/algorandfoundation/puya/commit/c20e62128490d02a75023a3cbd9815e7da7fd574))

* don&#39;t use structlog private fields ([`831bd68`](https://github.com/algorandfoundation/puya/commit/831bd685d5e34d65e28d8f81dd3938483c59d178))

* MyPy incorrectly inferring generic types from first __init__ overload when using classmethod ([`14aecde`](https://github.com/algorandfoundation/puya/commit/14aecde2721a722a5a346c9da5b1d3f457cb26c1))

* Explicitly disallow nested native tuples in abi methods ([`8663945`](https://github.com/algorandfoundation/puya/commit/866394540aacbfa3d10fd6866b15b771da5b2353))

### Performance

* speed up codegen (#48) ([`4c2ed03`](https://github.com/algorandfoundation/puya/commit/4c2ed035437a87496bc1a8d54c1fb7bdb3bff8b7))


## v0.2.0 (2023-12-19)

### Feature

* move subroutine elimination to IR stage (#44) ([`d65c9b6`](https://github.com/algorandfoundation/puya/commit/d65c9b60b12ff662bdd4e123dc95a59eea94f946))

### Fix

* reduce unnecessary usages of VLA ([`9b2cc85`](https://github.com/algorandfoundation/puya/commit/9b2cc85c8453344ad327082e734f3d94ad962ab9))

* relax docstring-parser version constraint for now ([`d15046d`](https://github.com/algorandfoundation/puya/commit/d15046df7ac467d9fa604eaa068fd911a579b778))

* stack ops optimisation looping, including not running at all if -O0 ([`b6eaaa6`](https://github.com/algorandfoundation/puya/commit/b6eaaa6f4257abc7bd4909eaa8034058669e4b70))

* remove support for non bool literals in match cases ([`c4520fb`](https://github.com/algorandfoundation/puya/commit/c4520fb878db15309fbae3401724135d226f653f))

* allow using puyapy primitive types with match statements ([`e669c04`](https://github.com/algorandfoundation/puya/commit/e669c043e8aeaeeadbb2510504083107b17dfd1b))

* use PYTHONUTF8 in compile_all_examples.py to force windows to use utf8 when running puya ([`b4ab579`](https://github.com/algorandfoundation/puya/commit/b4ab57949cb3d493f3ecfc55740ff3dad9b41b20))


## v0.1.3 (2023-12-11)

### Fix

* resolves some bugs with match statements (#25) ([`2c7de55`](https://github.com/algorandfoundation/puya/commit/2c7de55cdbdbc37652195f0ddd1cb541274103e6))

* add back arc4_signature ([`c21dd34`](https://github.com/algorandfoundation/puya/commit/c21dd34e3031d184ee35455ef38afc3aab7f59d1))


## v0.1.2 (2023-12-11)


## v0.1.1 (2023-12-11)


## v0.1.0 (2023-12-11)

### Feature

* change default optimization level to 1 ([`72b205a`](https://github.com/algorandfoundation/puya/commit/72b205ac006663bb64d16b2acdf0bf6870579b59))

* rename executable to puya ([`24659c8`](https://github.com/algorandfoundation/puya/commit/24659c8b451d17b8bbadfb25a19869e11a4deb9e))

### Fix

* log level display in CLI arguments ([`9bfc4e1`](https://github.com/algorandfoundation/puya/commit/9bfc4e13334bfe0f2a9753bc723546ae68f9b858))

* work around windows issue with outputting Phi symbol (#6) ([`6baa9c3`](https://github.com/algorandfoundation/puya/commit/6baa9c3442a8db9863741a9c1c25459d48423c10))

* use utf-8 encoding when running puya from compile_all_examples.py ([`f760e5c`](https://github.com/algorandfoundation/puya/commit/f760e5cfdc7e56f349e7a4c8d5abecb840ecdb56))

* Making compiler name more succinct ([`34bfd04`](https://github.com/algorandfoundation/puya/commit/34bfd04bc73923588f978fe2ea3abe8c6443f990))

* Resolving line endings issues on windows ([`b382d5a`](https://github.com/algorandfoundation/puya/commit/b382d5a49ec8f54d3a4f6402dc0f94d2d22e2981))
