# CHANGELOG


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
