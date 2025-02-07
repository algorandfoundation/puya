# CHANGELOG
## v4.3.3 (2025-02-07)

### Fix

* remove validation for ARC-32 and ARC-56 default args, and leave this to the app clients to resolve correctly ([`7fc803d`](https://github.com/algorandfoundation/puya/commit/7fc803d76e343db264018f3df6df357aa47a21a6))

## v4.3.2 (2025-02-07)

### Fix

* fix encoding of an array of arc4 bools when extending from a tuple of elements ([`20ba953`](https://github.com/algorandfoundation/puya/commit/20ba95355692ea5ec72d1f59e1fb3edb61169681))

## v4.3.1 (2025-01-31)

### Fix

* bump stubs version ([`a72cfb2`](https://github.com/algorandfoundation/puya/commit/a72cfb2f1437e9b24ef32f58a00843d62fe8d423))

## v4.3.0 (2025-01-31)

### Feature

* ARC-56 / ARC-32 constant default argument support ([`68aefcf`](https://github.com/algorandfoundation/puya/commit/68aefcfdb75a7ae9bc181f3528d6db409bc79de4))

### Fix

* prevent compilation failure when custom ARC4 approval method doesn&#39;t call super and thus doesn&#39;t generate a router ([`f90c44f`](https://github.com/algorandfoundation/puya/commit/f90c44f3bc62637399763832db5775ae57a50582))

### Documentation

* Fix incorrect example and add additional text explaining the difference between global state approaches ([`e38df61`](https://github.com/algorandfoundation/puya/commit/e38df617e5f9b1f36ba1beed0e8b46de4ff2fc01))

## v4.2.1 (2025-01-27)

### Fix

* Don&#39;t inline TEAL blocks with a single predecessor when their label is referenced multiple times. This issue could occur when there is a default fall through block in a switch or match scenario, which is also targeted by said op, and would cause a compilation failure. ([`d193042`](https://github.com/algorandfoundation/puya/commit/d193042b58e9f377804abb7a4d94ef2bc84ac3fd))

### Documentation

* make `algopy.arc4.Struct._replace` visible in docs ([`cd88089`](https://github.com/algorandfoundation/puya/commit/cd88089ea67ff154abfee5c09f6eed26f95b823e))

## v4.2.0 (2025-01-20)

### Feature

* support _replace method on ARC4Struct ([`3b1268d`](https://github.com/algorandfoundation/puya/commit/3b1268da00bd20bd507cb392e2aac37675a0e478))

* update ops with AVM 11 changes ([`6814370`](https://github.com/algorandfoundation/puya/commit/68143702a37dc90d4e95fc97ae5ba90a8c98e306))

### Fix

* prevent compilation failure when there are multiple functions inlined into another function and at least one of them unconditionally exits the program ([`9e78626`](https://github.com/algorandfoundation/puya/commit/9e786260ce0f0d3b3206f61cf7518b43b8572b8c))

* `algopy.LocalState.get` now works with `account` keyword argument ([`0722493`](https://github.com/algorandfoundation/puya/commit/07224938c750aa2ad2fe26032d9081739dc05939))

### Documentation

* add documentation on how to update langspec.json to support new AVM versions ([`a06b254`](https://github.com/algorandfoundation/puya/commit/a06b25425b6c583a04f2735400cdd7febd25f5a6))

## v4.1.1 (2025-01-13)

### Fix

* accept address or index param for VoterParamsGet methods (#369) ([`8cb9ffc`](https://github.com/algorandfoundation/puya/commit/8cb9ffc38e34563f2335b12e767d6794478fe7f8))

## v4.1.0 (2025-01-11)

### Feature

* optimizer enhancements ([`4bc09cb`](https://github.com/algorandfoundation/puya/commit/4bc09cbe5a589ea4ae255aa59adab8c45775d495))

### Fix

* ensure chained linear jumps are inlined as part of post-SSA optimization ([`9a3ff3a`](https://github.com/algorandfoundation/puya/commit/9a3ff3a9909cc2d410283baba688a4fea572bcd9))

* don&#39;t attempt to assemble contracts that aren&#39;t explicitly selected for compilation and may not have template variables defined ([`e933640`](https://github.com/algorandfoundation/puya/commit/e9336402eb4e19d637a54dd230c1316df664f930))

* correctly handle name collisions with structs in ARC-56 ([`5a4f134`](https://github.com/algorandfoundation/puya/commit/5a4f13487dfa1f95b893430c91e385951f2a4e40))

* Identify WTuples by name when treating them as structs in an ABI method ([`1db0efc`](https://github.com/algorandfoundation/puya/commit/1db0efc3d0d7871e86bcac01ee0ab872e2250424))

### Documentation

* add debugger ref; remove note from algopy testing doc as its no longer in preview (#368) ([`d3ff6d1`](https://github.com/algorandfoundation/puya/commit/d3ff6d17cc9b37c38d233bdc07aea10485fe96e9))

  * docs: add debugger ref; remove note from algopy testing doc as its no longer in preview

  * docs: apply suggestions from code review

  Co-authored-by: Rob Moore (MakerX) &lt;rob.moore@makerx.com.au&gt;

* add initial array adr (#362) ([`1f278f4`](https://github.com/algorandfoundation/puya/commit/1f278f4b2e4867e1b986a9b4ca1818c8c1ea9870))

  * docs: add initial array adr * docs: add feedback suggestion

## v4.0.0 (2024-11-14)

### Breaking

* raise an error when attempting to iterate a tuple of mutable values ([`43a364e`](https://github.com/algorandfoundation/puya/commit/43a364e0131e580565cbdfa3d8f44e9b78621252))

  BREAKING CHANGE: iterating a tuple of mutable types will now raise an error as they cannot be copied

* passing a mutable value more than once to a subroutine will now raise an error as allowing it would break semantic compatability ([`dac51be`](https://github.com/algorandfoundation/puya/commit/dac51be3c5cc3487ac303e9160fd9d8bd7b17788))

  BREAKING CHANGE: passing a mutable value more than once to a subroutine causes an error

* raise an error when attempting to modify immutable arrays such as `algopy.arc4.Address` ([`9450c7a`](https://github.com/algorandfoundation/puya/commit/9450c7a615712010067f494cc57d0ceb48f021f4))

  BREAKING CHANGE: modifying an `algopy.arc4.Address` will now raise an error

### Feature

* use extract3 instead of substring3 for bytes indexing ([`4954155`](https://github.com/algorandfoundation/puya/commit/4954155cc668f9a59d0a04c56fcb1af509978115))

* remove ops with no side effects when result is not used ([`ea34059`](https://github.com/algorandfoundation/puya/commit/ea3405928c5097934ecea0100c41c878ee51a258))

* ARC-56 application specifications can now be output using the `--output-arc56` option ([`2d3eb49`](https://github.com/algorandfoundation/puya/commit/2d3eb49c11d2db8a2ed6de04c16be33facbcdfb2))

* add `.copy()` to arc4.Tuple ([`fe7a0ea`](https://github.com/algorandfoundation/puya/commit/fe7a0ead47a44ea4c77538ccc45d3823eb6d41de))

* add support for AVM version 11 ([`0c31697`](https://github.com/algorandfoundation/puya/commit/0c31697053554d4fc64e9e49ad86eba6057fa67a))

* allow variable rebinding of mutable parameter values ([`253168a`](https://github.com/algorandfoundation/puya/commit/253168a63b92a39a4a2b596d7760175875b39a1d))

### Fix

* ensure expressions are only evaluated once ([`359956c`](https://github.com/algorandfoundation/puya/commit/359956c9e216222388aa10a001dbbd92305bcb35))

* prevent errors trying to optimize dig 0 ([`bf52c36`](https://github.com/algorandfoundation/puya/commit/bf52c363039d43ad3c4a361f7e288ea7a330c10c))

* improve error message when a self parameter is missing from a method declaration ([`8153cfb`](https://github.com/algorandfoundation/puya/commit/8153cfbdb30aace1c34bd2e64b0418f1b4678a96))

* use read location for variable source locations, rather than where the variable was last defined ([`27e2659`](https://github.com/algorandfoundation/puya/commit/27e26597fd4c577cd69e7af2d9795860c06e36f2))

* correctly determine if an `algopy.arc4.Struct` sub-class is immutable or not based on `frozen` class parameter and immutability of fields ([`0491d0b`](https://github.com/algorandfoundation/puya/commit/0491d0bc9f2be7bf8f2ba5cf54cfc600abe698e6))

## v3.6.0 (2024-11-04)

### Fix

* ensure paths are normalised in Puya source maps ([`29224ef`](https://github.com/algorandfoundation/puya/commit/29224ef7c689d9b7cc837c27367af0bfd1e447c0))

## v3.5.0 (2024-10-30)

### Feature

* add `_replace` implementation for named tuples, make `algopy.CompiledContract` and `algopy.CompiledLogicSig` named tuples ([`93a47f2`](https://github.com/algorandfoundation/puya/commit/93a47f25d3904275b7bfba6fd25595a6c8b88b95))

* reduce stack manipulations ops when subroutine/op results are directly assigned ([`fbe6ebb`](https://github.com/algorandfoundation/puya/commit/fbe6ebbd1744a3eb07653f8cc1ccd28fad6b3006))

* add CLI option `--output_source_map` to produce debug information that can be used with the next release of AVM debugger ([`3009822`](https://github.com/algorandfoundation/puya/commit/300982218ce67c204cc6c719c96fe2609c69eb7a))

* add optimization to include constant blocks in TEAL output ([`671677b`](https://github.com/algorandfoundation/puya/commit/671677b4a5c0656a247feb7fa4baa4c05c528d5e))

### Fix

* check target type for ARC4Decode ([`9704011`](https://github.com/algorandfoundation/puya/commit/9704011e6a28f0edab113cb3b3b0e8e3153bd9a7))

* deprecate `--match-algod-bytecode` option as there is now no difference between algod and puya bytecode output ([`de0fd58`](https://github.com/algorandfoundation/puya/commit/de0fd58cf7107303ef512b3a67ee8bd24fce9fe6))

## v3.4.1 (2024-10-24)

### Fix

* allow named tuples to be unpacked ([`320efd2`](https://github.com/algorandfoundation/puya/commit/320efd283292abab1d234610101715f808954730))

* itxn arguments are now inferred correctly when using only a method name in `algopy.arc4.abi_call` ([`04fe6d7`](https://github.com/algorandfoundation/puya/commit/04fe6d798e58939fd07028f07d15b2e25b9427e4))

## v3.4.0 (2024-10-23)

### Feature

* Named tuple support in contract to contract calls ([`c742281`](https://github.com/algorandfoundation/puya/commit/c7422817d45187db960a1cb2a09d618c668429ee))

* Named tuples ([`e0abe5c`](https://github.com/algorandfoundation/puya/commit/e0abe5c572d5dbd0049ea34ed77000333b1e6d57))

### Fix

* Round trip serialization of names property on WTuple ([`dd7b679`](https://github.com/algorandfoundation/puya/commit/dd7b679389b77db4b7d1e73335ed23c6672d64ca))

## v3.3.0 (2024-10-16)

## v3.2.3 (2024-10-15)

### Fix

* native tuples now supported as arguments and return value when using `algopy.arc4.abi_call`, `algopy.arc4.arc4_create` or `algopy.arc4.arc4_update` (#324) ([`6dfd68b`](https://github.com/algorandfoundation/puya/commit/6dfd68b6d44ce5f39c5d96b1b383e95241c7559b))

## v3.2.2 (2024-10-08)

### Fix

* assigning transaction result from algopy.arc4.abi_call containing other transactions no longer causes an error ([`125e85e`](https://github.com/algorandfoundation/puya/commit/125e85ecda39f36a07beb7db20af17b751291566))

* fixed incorrect typing of `algopy.arc4.abi_call` parameters `global_num_uint`, `global_num_bytes`, `local_num_uint`, `local_num_bytes` and `extra_program_pages` ([`e464ca2`](https://github.com/algorandfoundation/puya/commit/e464ca291c94e573099dfa00a8cc75726e401641))

## v3.2.1 (2024-10-04)

### Fix

* fixed error when assigning result of an abi_call with inner transactions that return an ABI value ([`e3ef7dd`](https://github.com/algorandfoundation/puya/commit/e3ef7ddaea0ff050aa316b385047a89435e046a6))

## v3.2.0 (2024-09-24)

### Feature

* expand handling of literal expressions to allow combining them with binary boolean operators, and improve error messaging when handling of type unions in nested bool contexts ([`b4e0c30`](https://github.com/algorandfoundation/puya/commit/b4e0c306e59dab70664f0c2509bc5eb9458b2821))

### Fix

* prevent error that occurs when removing a series of redundant Load and Store ops ([`17778b8`](https://github.com/algorandfoundation/puya/commit/17778b859d4e0b0f3dbc329afbd64f8908470d5d))

* fix compilation error when a nested tuple is passed as a named argument ([`d849496`](https://github.com/algorandfoundation/puya/commit/d849496dfe5b4b14ee1cc38cfdce8cfb8066c70d))

## v3.1.0 (2024-09-13)

### Feature

* `algopy.arc4.abi_call`, `algopy.arc4.arc4_create` and `algopy.arc4.arc4_update` now all support txn arguments ([`8133e1d`](https://github.com/algorandfoundation/puya/commit/8133e1db63e6c63990d28f79dc1b6a7b2a422a2e))

* add CLI option to serialize AWST to JSON ([`66bf127`](https://github.com/algorandfoundation/puya/commit/66bf1274b88e5856e4163df8f276f64fff390da5))

* optimize `int 0; return` -&gt; `err` ([`3605cf4`](https://github.com/algorandfoundation/puya/commit/3605cf4aeaeaa3218fb523e6669dcd5254275fc5))

* allow user to implement approval_program in ARC4Contract subclasses ([`004450b`](https://github.com/algorandfoundation/puya/commit/004450b909a5c007ec6f20600fd874b1ed5c59d1))

### Fix

* handle zero values for TemplateVar ([`6087dc2`](https://github.com/algorandfoundation/puya/commit/6087dc21451e5266f7df8b9851dd80a5d12be7d8))

  boolean values are now also allowed as `True` or `False`

  also incorrect values will no longer result in a critical error, but a CLI usage error instead

* when accessing a member of `self`, use the source location of the access ([`2f827ab`](https://github.com/algorandfoundation/puya/commit/2f827aba3cc471f588609156f551130b47f9c5b8))

* when there is exactly 15 arguments to an ABI function, the final argument should not be expected to be automatically tuple-packed ([`04e15df`](https://github.com/algorandfoundation/puya/commit/04e15df084ee99c001fd7df28697f4e569606161))

* calling `algopy.arc4.arc4_create` or `algopy.arc4.arc4_update` with a ARC4Contract type now works for abimethods that have a return type ([`99d6a24`](https://github.com/algorandfoundation/puya/commit/99d6a241e83d46d45780093346e1295d94161f51))

* fix `super()` usage in multiple inheritance scenarios ([`21929cc`](https://github.com/algorandfoundation/puya/commit/21929cc64e0eaf735189158d454904de387a3d8a))

* allow `super().__init__()` calls that resolve to `object.__init__()` as no-ops, this is valid and can be useful in multiple inheritance scenarios ([`267f423`](https://github.com/algorandfoundation/puya/commit/267f4235c0bb1a0b5a40347ddd9a26e2d6cd6532))

* abstract methods can still have implementations, which can be called via super ([`9615467`](https://github.com/algorandfoundation/puya/commit/96154675231c8303941c357f3c6fcab1c21c3413))

* evaluate class bodies at module evaluation time, so that any referenced constants in e.g. decorators receive the correct value if it&#39;s later updated ([`9aea78c`](https://github.com/algorandfoundation/puya/commit/9aea78c638b01863a4ed8004187108d3e315ec1b))

* resolve all base scratch slot reservations, not just direct bases ([`f9521b5`](https://github.com/algorandfoundation/puya/commit/f9521b5cc81c4800a198d6428cc078c26ced8d8b))

## v3.0.3 (2024-08-28)

### Fix

* do not remove swap ops before `itxn_field` if it&#39;s immediates point to the same field ([`0e88cdb`](https://github.com/algorandfoundation/puya/commit/0e88cdbaf5372e14b8de04aa28f244379d367528))

## v3.0.2 (2024-08-23)

### Fix

* handle utf-8 alias&#39;s when checking for encoding, addresses #300 ([`90bf86f`](https://github.com/algorandfoundation/puya/commit/90bf86fed54bfb1ab658020b31e8adad52a30412))

* remove `slice` from `__getitem__` in `algopy.arc4.DynamicArray` and `algopy.arc4.StaticArray` ([`c0049f1`](https://github.com/algorandfoundation/puya/commit/c0049f16a40e208f178586450eed2a4bf7648e97))

### Documentation

* improve ARC4 array documentation ([`251759f`](https://github.com/algorandfoundation/puya/commit/251759fa6475ef5d9d4ea1f99aeeb11cb1b1c7a6))

## v3.0.1 (2024-08-20)

### Fix

* handle `in`/`not in` tests correctly for differing types that can still be considered equal ([`234c376`](https://github.com/algorandfoundation/puya/commit/234c376aaad6ae5eab897a934fd8609075222757))

* do not error when using `algopy.arc4.abi_call` with a method selector string containing no arguments ([`74577c4`](https://github.com/algorandfoundation/puya/commit/74577c4aa3261567f514decf75f53abe5d44c421))

## v3.0.0 (2024-08-16)

### Breaking

* use correct return type for `algopy.op.gaid` ([`a5c57ef`](https://github.com/algorandfoundation/puya/commit/a5c57efae3f07df7c59b050edce9318818078896))

  BREAKING CHANGE: `algop.op.gaid` return type has changed from `algopy.Application` to `algopy.UInt64` as the return value could be the id of either an application or an asset. Any existing usages of `algopy.op.gaid` will need to pass the result to either `algopy.Application` or `algopy.Asset` as appropriate

### Feature

* include `num_log`, `log`, `create_app` and `created_asset` properties for group transactions ([`5359c4d`](https://github.com/algorandfoundation/puya/commit/5359c4d9ea377e34add5c15d064d79cbf838eaaa))

* as part of optimization, remove no-op subroutines ([`5663a55`](https://github.com/algorandfoundation/puya/commit/5663a55bebf7152f525bf12c639fe280fe0574fd))

## v2.3.0 (2024-08-12)

### Feature

* improved optimization when uint64 comparisons involve a boolean value ([`a68ca06`](https://github.com/algorandfoundation/puya/commit/a68ca06bdcfca5c5df115f6af54e47f4ecc00413))

* more aggressive optimization of `select` op involving constants or references to constants ([`8d59e2d`](https://github.com/algorandfoundation/puya/commit/8d59e2dd86bb03eaed806a48f07c04939e507660))

* optimise away `select` op when both values are the same ([`f8eb257`](https://github.com/algorandfoundation/puya/commit/f8eb257ea903b9c7d51dee1384006e68897aaead))

* optimise code size by converting conditional (ie ternary) expressions into `select` op when both values are simple variables / constants ([`b748976`](https://github.com/algorandfoundation/puya/commit/b74897677523a71cfb67c5393ecafd7c404af2c9))

* more aggressive optimization of the boolean condition argument to `setbit` ([`e9828b3`](https://github.com/algorandfoundation/puya/commit/e9828b3b74571b01cb7315f80c84dae4ae6b223c))

* support nested tuples ([`fe270dc`](https://github.com/algorandfoundation/puya/commit/fe270dcf8ebe26bdece34e1e0066c0eee8de0789))

### Fix

* correctly type the result of BigUInt bin ops at IR layer ([`d8d92bd`](https://github.com/algorandfoundation/puya/commit/d8d92bd1864d4ad810a3c8534f6ee0f0a45c9a09))

* ensure non-zero UInt64 values that are explicitly converted to bool are handled correctly (issue #194) ([`13929de`](https://github.com/algorandfoundation/puya/commit/13929de2050acb6063697bc1c1e084ef7fed916a))

### Documentation

* fix link ([`c53d1f7`](https://github.com/algorandfoundation/puya/commit/c53d1f7ac1fba44f59a73183b09bcfe1aeae8fdf))

## v2.2.0 (2024-07-30)

### Feature

* remove requirement that the target variable of a for-loop with enumeration be a tuple unpacking ([`5b994e3`](https://github.com/algorandfoundation/puya/commit/5b994e35d322c664a85079cdc4a0ffe876a50dca))

* support for-else and while-else ([`0959e2d`](https://github.com/algorandfoundation/puya/commit/0959e2d3652b729f5c7cca2bd15fe99a02be5219))

* include ARC-22 readonly flag in ARC-32 output ([`6d325b9`](https://github.com/algorandfoundation/puya/commit/6d325b989a3f9814eaf3325a3685ee95bb1722e8))

* add support for compiling programs to AVM bytecode, and referencing those programs within other contracts. ([`7d7a4fd`](https://github.com/algorandfoundation/puya/commit/7d7a4fd7e6465ff26c10909147034720eb1c5145))

### Fix

* ensure conversion of UInt64 enum types to arc4 UIntN is handled correctly. ([`70b49dc`](https://github.com/algorandfoundation/puya/commit/70b49dc848fd7dc67569f81ddf443e8eb3d865f6))

* change total_num_byte_slice return type to UInt64 ([`96b5165`](https://github.com/algorandfoundation/puya/commit/96b5165f916d64b9edee121d2c40b340eb488c5c))

* fix bug with iteration of single item tuples ([`983f171`](https://github.com/algorandfoundation/puya/commit/983f171f6a4566332740a000b8209e7fe3217bb1))

* fix a regression where `algopy.op` functions that accepted multiple literal types would fail to compile with all except one type ([`2cbf5df`](https://github.com/algorandfoundation/puya/commit/2cbf5df647842969fce27199153ae0bac2ad1523))

* use UInt64 enum types as return types where appropriate in low-level ops stubs ([`008c96a`](https://github.com/algorandfoundation/puya/commit/008c96a3222e37e2cd702ec844e7ebc38aff9d8f))

* prevent internal errors when for-loop bodies always exit (#269) ([`1b24cd7`](https://github.com/algorandfoundation/puya/commit/1b24cd72af71f2826b3385c8a274d1a656895f57))

## v2.1.2 (2024-07-10)

### Fix

* corrected parsing of ARC4 ufixed types when provided via string literals in `algopy.arc4.abi_call` and `algopy.arc4.emit` ([`43ffe8e`](https://github.com/algorandfoundation/puya/commit/43ffe8e57fa2365dd5d56d24fb7bf09227759478))

* in the case of overlapping values in a Switch (ie Python match-case), mark subsequent cases as unreachable to prevent a critical error from occurring (&#34;Attempted to add a (non-entry) block with no predecessors&#34;) ([`f21efc1`](https://github.com/algorandfoundation/puya/commit/f21efc1e0e4ef396e2b02e0ace1821ce9abc40ea))

### Documentation

* clarify default behaviour of key_prefix in BoxMap ([`786e9b5`](https://github.com/algorandfoundation/puya/commit/786e9b552916736ce93ac4e08ec6f36abec995ac))

  also fix existing invalid doc syntax for arguments

* fix documentation of arc4.Tuple native property ([`172934b`](https://github.com/algorandfoundation/puya/commit/172934bd4163a3ec4595a3c1e8709e29d54d2675))

## v2.1.1 (2024-07-01)

### Fix

* prevent assertion error when using dynamic key with storage proxy and assinging to self member ([`351b51e`](https://github.com/algorandfoundation/puya/commit/351b51e46ac30de5a01ff43b5b70d18818d2c478))

* add dynamic key types to stubs for LocalState and GlobalState ([`0aade7a`](https://github.com/algorandfoundation/puya/commit/0aade7ae1a724bc89a02c96f6bcafe8eb08fe605))

  also add this use cases to tests

## v2.1.0 (2024-06-25)

### Feature

* support comparisons between `arc4.Bool` and `bool` ([`1787f06`](https://github.com/algorandfoundation/puya/commit/1787f06619ef459dfd78e063be3270c0972fc54d))

* support a wider range of types for inner transaction application args ([`28b5197`](https://github.com/algorandfoundation/puya/commit/28b5197081a9eda4586658c918b410409d07c859))

* support string literals in String.join argument ([`0818d7d`](https://github.com/algorandfoundation/puya/commit/0818d7d9c28b72d170c42f13714875312ed16faa))

* support constructing tuples via tuple(&lt;expr&gt;) where expr is a fixed size sequence ([`529f12a`](https://github.com/algorandfoundation/puya/commit/529f12a3465d2013f44a75ce83b29571fa68de07))

* support tuple equality comparisons with literal elements, support tuple repetition &amp; concatenation, and support indexing/slicing literals that support it ([`0c8a745`](https://github.com/algorandfoundation/puya/commit/0c8a745311be5fb779edcba2929f3e9911f265ad))

* allow conditional expressions involving literals when either interacting with an algopy type or being passed to an algopy function, where possible ([`a047d92`](https://github.com/algorandfoundation/puya/commit/a047d929998ab27a53351fbc0dcd610e9fef81a7))

  examples that are now possible: - `x = UInt64(12 if condition else 34)` - `x += 45 if condition else 67` - `op.addw(2**64-1 if condition else 0, x)`

* Box storage api ([`c41ce5e`](https://github.com/algorandfoundation/puya/commit/c41ce5e0b2c051412c8020687e7f3448aa44f439))

* handle cover/uncover rotation simplification edge case ([`9ed7a60`](https://github.com/algorandfoundation/puya/commit/9ed7a609caa719b5d37de81d70f6f9f261940234))

### Fix

* bool evaluations that evaluate to constants are now treated as errors as they were either hiding a semantic compatability issue or were a sign of a mistake in the code. ([`247d62d`](https://github.com/algorandfoundation/puya/commit/247d62d24543d232e2649c48a96d979e426b9ae3))

* handle single item tuples correctly ([`2026815`](https://github.com/algorandfoundation/puya/commit/202681511512bb7c7e6f41190c6bb4d810c02ab6))

* add missing * to stubs, that EB was expecting ([`4842719`](https://github.com/algorandfoundation/puya/commit/48427190defdac743f16938a2a798d8a35bdd677))

* ensure tuple expressions are evaluated when converting to a bool ([`9d556e6`](https://github.com/algorandfoundation/puya/commit/9d556e6f2623d6caee6f51f3a04d4f6517bc18c7))

* do not require ARC4 types to .copy() when being as arguments to an inner transaction ([`601a385`](https://github.com/algorandfoundation/puya/commit/601a3850d041139dbef3ba0e634d55f0127c9ba9))

* fix argument packing condition when using abi_call ([`070d224`](https://github.com/algorandfoundation/puya/commit/070d2242694a287d4897a145438f5296530108df))

* fix UInt64 handling of construction from bool ([`07cd6d9`](https://github.com/algorandfoundation/puya/commit/07cd6d9163859a88b2fb810387c86c5089e51de4))

* fix semantic issues with tuple comparisons of different length / types ([`840118a`](https://github.com/algorandfoundation/puya/commit/840118a6062262c7175f68ccc81f8eba0a80ca4c))

* fix semantic compatibility issue with comparisons involving tuple literals ([`180d363`](https://github.com/algorandfoundation/puya/commit/180d363fab87253c15ed9f50fb83ddff74384c24))

* support negative indexes on indexable types ([`9213996`](https://github.com/algorandfoundation/puya/commit/92139960da2da49e10d77572127d32072a0e7d9c))

* fix bug in &#34;untyped&#34; itxn creation not being declared as allowing BytesBacked ([`f5aeada`](https://github.com/algorandfoundation/puya/commit/f5aeadad78afb6c306f476a253a31703e3da6309))

* fix encoding of bytes constants and allow String as sep value ([`6e82f80`](https://github.com/algorandfoundation/puya/commit/6e82f807312e7ba31dd2d51b2a0b9cb707b56f72))

* handle __eq__ for ufixed ([`83b346b`](https://github.com/algorandfoundation/puya/commit/83b346bb8c794c4f19f48f61c460b37561c2798f))

* handle bool values (as subtype of int) when comparing against arc4 uintn ([`74e065d`](https://github.com/algorandfoundation/puya/commit/74e065de7c99802a7d3f9877b4ea71925828a5da))

  fix: allow arc4.String comparison with String without going through constructor

  refactoring convert_arc4_literal (wip)

* fix bug with inner-transaction-containing tuple detection ([`6ca2c45`](https://github.com/algorandfoundation/puya/commit/6ca2c454de3b056465cdb17b36c379d0d553b775))

* resolve issue when using native types with arguments and return values in abi_call ([`604dddc`](https://github.com/algorandfoundation/puya/commit/604dddcccc18a9cabdf1a75d4b7b51330be30304))

* allow usage of module constants in ARC4 method decorators ([`d09f381`](https://github.com/algorandfoundation/puya/commit/d09f38122c95955d82ea5505bab5a84f8455543d))

* fix bug with resolving super/direct base method invocation ([`a0618cb`](https://github.com/algorandfoundation/puya/commit/a0618cb5d79125f9fdcd308c7c29418afdc3da84))

* improve error messages when typing.Any type is encountered ([`c2cfaf5`](https://github.com/algorandfoundation/puya/commit/c2cfaf531b40d0a1fea5f8c3ada0476ec8efbf79))

* prevent critical error message when missing self param in declaration ([`7ff2e17`](https://github.com/algorandfoundation/puya/commit/7ff2e175576a15014e0beee1c4c5dc31ab3c62e0))

* correct return type of String.join ([`3df0b8b`](https://github.com/algorandfoundation/puya/commit/3df0b8bf8ea62ec2acf1976f9bfe166486270862))

* fix resolution of base class references across modules ([`cf7c67f`](https://github.com/algorandfoundation/puya/commit/cf7c67fe32fd2241641fb9e231002038c31ecab5))

* resolve potential semantic incompatibility with super() usage and differing kinds of attributes (methods vs data) ([`f1f2bdd`](https://github.com/algorandfoundation/puya/commit/f1f2bdde3bac1d90b029e1c18cb9fe2563c8ec57))

  add bad super() usage test

* ARC4 Bool decode now resolves to IRType.bool ([`9b4e82d`](https://github.com/algorandfoundation/puya/commit/9b4e82d4d204005716b9956f8d2b0433345c5ede))

## v2.0.2 (2024-06-10)

### Fix

* resolve issues with reading and writing ARC4 types ([`23f9bd2`](https://github.com/algorandfoundation/puya/commit/23f9bd2dd0589b3ce4caa2763f8808cf71936e04))

  Reading and writing dynamic ARC4 types in an array Modifying ARC4 tuple items (https://github.com/algorandfoundation/puya/issues/152) Require ARC4 struct initialisation to have unaliased values to maintain reference semantics

* fix inner transaction validation to handle some cases that were accidentally missed (#233) ([`cd42f02`](https://github.com/algorandfoundation/puya/commit/cd42f020f97695549add0f92cf541fca25fc8b77))

### Documentation

* Add example of struct in a box (#243) ([`b0530c1`](https://github.com/algorandfoundation/puya/commit/b0530c1579b05392ea57de02d8c76ff6acbac897))

## v2.0.1 (2024-05-21)

### Fix

* fix incorrectly mapped transaction arguments `global_num_uint` and `local_num_uint` in `algopy.arc4.abi_call` #232 ([`0c35caa`](https://github.com/algorandfoundation/puya/commit/0c35caa54407e43635fc8408479adff1d5d4a8cc))

* resolve issue when using native types with arguments and return values in abi_call ([`38a199a`](https://github.com/algorandfoundation/puya/commit/38a199ade05dac091eee3ac254c3364f88cf4a00))

* correct default value for fee in abi_call ([`ac46f49`](https://github.com/algorandfoundation/puya/commit/ac46f490356157e1bf1ba893af4a1882eba58a38))

* fix IR return types of `b+` and `b*` ops ([`0de49c1`](https://github.com/algorandfoundation/puya/commit/0de49c1a847a54e1f58b3eef201b257fd19a24d2))

* correct return type of String.join expression ([`873460d`](https://github.com/algorandfoundation/puya/commit/873460db1bdd6047dbe0c1ecd12dbfe2163adc99))

* corrected itxn field type definitions for `VotePK`, `SelectionPK` and `FreezeAssetFrozen` ([`5f59f15`](https://github.com/algorandfoundation/puya/commit/5f59f157b1a0a864575335525f5ef96759ace622))

* correctly handle `BigUInt` in ARC4 methods ([`354a4a2`](https://github.com/algorandfoundation/puya/commit/354a4a273bd22d12119da85327f5466e595d6f47))

* handle resolve reinterpret cast at the IR level with a temporary assignment if required (#219) ([`4b1bff3`](https://github.com/algorandfoundation/puya/commit/4b1bff3795b89bc3175532299590d7935acb6a75))

* do not match `dup2` op when performing constant stack shuffling ([`815e253`](https://github.com/algorandfoundation/puya/commit/815e253bb8f4a6e7195a6a8e8551b245eac3c8ab))

* remove type bound on `TemplateVar` allowing it to be used with all types. ([`4226e0f`](https://github.com/algorandfoundation/puya/commit/4226e0f939571df4faf1a883b4d8b32bac884509))

### Documentation

* improve some stub type signatures &amp; copy in transaction field notes from Algorand docs (#215) ([`4f01df5`](https://github.com/algorandfoundation/puya/commit/4f01df52eec1bbbfac9ea25d53a569c1e70a2800))


## v2.0.0 (2024-04-26)

### 🚨 BREAKING CHANGES 🚨

#### Support inner transactions being assigned to unpacked tuples
Accessing an array field of an inner transaction result after it may no longer be available (i.e. after another inner transaction submission) is now a compile error, to resolve this move the array field access before the statement that causes this.

Commit: [`0915c5c`](https://github.com/algorandfoundation/puya/commit/0915c5cb513be0f897be3d1aef59f7e853b393e5)

#### Prevent usage of state proxies (GlobalState, LocalState) outside `__init__` method
Using state proxies (GlobalState, LocalState) outside of an `__init__` method may not give the behaviour expected, so prevent their usage in those scenarios.

Commit: [`d354d4e`](https://github.com/algorandfoundation/puya/commit/d354d4e14a88b68f25782a74e48bd8d30d81690e)

#### Default transaction fees to `0` (#202)
The default fee for inner transactions is now 0 unless explicitly specified.

Commit: [`519957f`](https://github.com/algorandfoundation/puya/commit/519957f3e2b65706452e8543b4227fd467b2ed5d)

### Feature

* Allow wider range of algorand-python versions as long as no incompatible definitions are used. Instead of an error, a prominent warning is displayed if there is a potential mismatch. ([`bf84501`](https://github.com/algorandfoundation/puya/commit/bf84501d0c3dfa5f88f0bb2c2730f4abc91f7f04))
* Allow raw `select` op usage, since it&#39;s a very efficient way to do a ternary operator if greedy argument evaluation is acceptable ([`e91a157`](https://github.com/algorandfoundation/puya/commit/e91a157c9dc887421a54c32b020d78c398baccb6))
* Constant optimisation for `algopy.op.sqrt` and `algopy.op.bsqrt` ([`bb8f03b`](https://github.com/algorandfoundation/puya/commit/bb8f03bb32fcb2ab9fa3204ebf0ec970537ff7b1))
* Allow int literals with `algopy.op` functions that take a `BigUInt` (currently just `bsqrt`) ([`a8e14c3`](https://github.com/algorandfoundation/puya/commit/a8e14c382db18b1e311ceff700e43c6661582015))
* Add missing constant folding optimization for b% ([`9536d59`](https://github.com/algorandfoundation/puya/commit/9536d597891dc6c2e911c2c2b435f6253731908b))
* Add support for `bool` types in state proxies (e.g. `GlobalState`) and remove generic type constraint. ([`c9a7224`](https://github.com/algorandfoundation/puya/commit/c9a7224862db8ee7682aded0cb66e71d455c84c8))
* Allow module constants to be used as `assert` statement messages ([`328ee55`](https://github.com/algorandfoundation/puya/commit/328ee5548749a8ffe66780df60164f910264e6cd))

### Fix

* Add missing `asset_sender` field to inner transactions ([`fd6bba3`](https://github.com/algorandfoundation/puya/commit/fd6bba390d43e3fcf8e270321e2571545fea3220))
* Treat unassigned &amp; unsubmitted inner-transaction field-sets as a code error, not an internal error ([`b86bfa6`](https://github.com/algorandfoundation/puya/commit/b86bfa6def104a59d9307200e14f463726ea31d7))
* Use return type of method signature as return type for an `abi_call` without an indexed type param ([`1318459`](https://github.com/algorandfoundation/puya/commit/1318459d268ff0f2fc59189c89c9294522a40724))
* Fix issue #195 where certain state comparisons could fail to compile. ([`b8efcc3`](https://github.com/algorandfoundation/puya/commit/b8efcc36112abdf6fc18c74524f99c0b8628419a))
* Add missing ARC4-copy-checks of `.get()` and `.maybe()` methods in state proxies ([`49da224`](https://github.com/algorandfoundation/puya/commit/49da224ef40623b099453aac0b67c8c7a9f4a34a))
* Allow negative `arc4.Tuple` indexing ([`67ff876`](https://github.com/algorandfoundation/puya/commit/67ff8766e683f53a06f8cac8caa0af634f4787b2))
* Add missing stub indicators for unary `+` operator to `BigUInt` and `UInt64` ([`caa98dc`](https://github.com/algorandfoundation/puya/commit/caa98dc484d44c4a7bbaf647cf26141029b84ffa))
* Improve error message with invalid `String()` comparisons ([`f340c86`](https://github.com/algorandfoundation/puya/commit/f340c866b08e7aa84ac53659e9c7822247aed22f))
* Improve source location for `Asset(&lt;int&gt;)` ([`7c89ad7`](https://github.com/algorandfoundation/puya/commit/7c89ad7bbb74ce777e57de777db2e2974edb770f))
* Correct input value types for `algopy.op.setbit` ([`c8fda82`](https://github.com/algorandfoundation/puya/commit/c8fda82149e322884150557e744893a5617ada3b))
* Handle `arc4.Address.native` ([`6dcb55d`](https://github.com/algorandfoundation/puya/commit/6dcb55df852248663f0bbcb886359aa48d776533))
* References to unknown symbols are now correctly treated as code errors rather than fatal errors ([`eb802d3`](https://github.com/algorandfoundation/puya/commit/eb802d3fdd0243fa191e47e8826fee0545be5847))
* Fix unnecessary `.copy()` requirement when providing an ARC4 encoded initial value to `GlobalState` ([`5a56041`](https://github.com/algorandfoundation/puya/commit/5a560419f73978375f7855cf61745bed0843a8f6))
* Ensure ARC router generation works with minimal contracts that don&#39;t have any explicit abimethods ([`936f378`](https://github.com/algorandfoundation/puya/commit/936f3780eb2fe1ba60e1b6a9ddb8ee6338715283))
* Fix bug with failing to discard unassigned results from `algopy.op.*` functions ([`33d961a`](https://github.com/algorandfoundation/puya/commit/33d961a285f404288f282c89d3a528bf426a303a))
* Prevent multiline assert messages from breaking TEAL output ([`4ea5ae6`](https://github.com/algorandfoundation/puya/commit/4ea5ae68e3149d1a0bda0be20ff739df4f6af299))
* Fix incorrect error message on unsupported class declaration ([`8eb5a78`](https://github.com/algorandfoundation/puya/commit/8eb5a78c2887039a0920efa7a0e6ba053068c1de))
* Add colorama as a dependency on Windows, this is required when using PowerShell ([`0acb4b2`](https://github.com/algorandfoundation/puya/commit/0acb4b2d2a8a6429924774005acce8ff2b3aec8a))

### Documentation

* Add note about method behaviour for accounts which have not opted in ([`12282b9`](https://github.com/algorandfoundation/puya/commit/12282b9e599b131f41772a4617006d07735e163a))
* Use best practices in ARC-4 examples of dealing with native types and letting the router do encode/decode, which generally saves at least one op. ([`7504ed5`](https://github.com/algorandfoundation/puya/commit/7504ed580bc920d364037819cf2ba0482abfdf72))
* Simplify "Quick start" steps ([`01a9f95`](https://github.com/algorandfoundation/puya/commit/01a9f95552ab815cf3b62c8adf034158e18614ac))
* Adding missing install step to install algorand-python ([`c08f753`](https://github.com/algorandfoundation/puya/commit/c08f7532b255d175d207d2062afb88a2a07e4308))
* Corrections & improvements to `BigUInt` type docs ([`7e20261`](https://github.com/algorandfoundation/puya/commit/7e20261c5eddffdba3411842b6c9df8de3226a3f))


## v1.0.1 (2024-03-27)

### Fix

* include algorand-python 1.0.1 stubs ([`ba2fe25`](https://github.com/algorandfoundation/puya/commit/ba2fe25894b7a620ace046ed60da1b0f721d679e))

### Documentation

* added v1 documentation (#147) ([`faf9995`](https://github.com/algorandfoundation/puya/commit/faf999527829e561adc5fa16376c07d1ba3f2a9f))


## v1.0.0 (2024-03-27)

### Breaking

* enable major on zero ([`64145c2`](https://github.com/algorandfoundation/puya/commit/64145c298d0aa1584dfa384a4f3c80d82f0e63f2))

  BREAKING CHANGE: 1.0 release

### Feature

* set --output-client=False by default ([`438d815`](https://github.com/algorandfoundation/puya/commit/438d815967bd3763ee799c1a0b7d3f3dcab2f769))

### Fix

* search for python3 when attempting to locate python executable ([`abf5c09`](https://github.com/algorandfoundation/puya/commit/abf5c0964b9264950c0b24286d7d919843cb0f7c))

* use shutil.which to find python exe ([`56e46c9`](https://github.com/algorandfoundation/puya/commit/56e46c9826d39f1a514051672ec8834907d7f6e2))

* set supported algopy version range correctly ([`6c1a387`](https://github.com/algorandfoundation/puya/commit/6c1a387bc11976d4ac9d63fd802312bfe1a91103))

* better support for executing puyapy within a venv and outside a venv ([`212201e`](https://github.com/algorandfoundation/puya/commit/212201e7c6158a56e9063e795e5760ea65e4e7b8))

### Documentation

* update README.md ([`1f39990`](https://github.com/algorandfoundation/puya/commit/1f399904338cb6b2a125955b18bf0b2920993a74))


## v0.7.1 (2024-03-26)

### Fix

* prevent mypy error when stubs and puyapy are in the same venv ([`91f6765`](https://github.com/algorandfoundation/puya/commit/91f67651d26268da21094f7ac5c0890fdf1038a8))


## v0.7.0 (2024-03-26)

### Breaking

* change abimethod/baremethod &#34;create&#34; parameter to `&#34;allow&#34; | &#34;require&#34; | &#34;disallow&#34;` instead of `&#34;allow&#34; | True | False` ([`2ca4c67`](https://github.com/algorandfoundation/puya/commit/2ca4c67c54752916b5c4423e8c4d036c5523972a))

  BREAKING CHANGE: Replace create=True with create=&#34;require&#34; in abimethod/baremethod decorators, and replace create=False with create=&#34;disallow&#34; in abimethod/baremethod decorators.

* prevent reassignment of mutable parameters that are passed by reference ([`a9c7600`](https://github.com/algorandfoundation/puya/commit/a9c7600d0563ec0e521771c97e42490ea3428b9b))

  BREAKING CHANGE: Re-assigment to a parameter that is mutable is now disallowed.

* Prevent iteration of arc4 containers with mutable items ([`f857181`](https://github.com/algorandfoundation/puya/commit/f8571812097f84c872276249ce3cb5bb246ef348))

  BREAKING CHANGE: Direct iteration of arc4 containers with mutable items is no longer possible due to issues with the reference vs value semantics, instead use `for &lt;index&gt; in urange(&lt;array&gt;.length)` and access/update elements by index.

* rename stubs from puyapy to algopy ([`31052e3`](https://github.com/algorandfoundation/puya/commit/31052e327019f7f84691a6d8f98f2244fe045c08))

  BREAKING CHANGE: Any imports from `puyapy` should be replaced with `algopy`.

* to prevent file output collisions, the ARC32 JSON output is now always named according the class name (or name= override). Tests for output collision is also performed before final output. For consistency, the TEAL files are use this same prefix, rather than the module name. ([`78d5a31`](https://github.com/algorandfoundation/puya/commit/78d5a31578954adc950fdd205a5f5aee21627f77))

  Compilation stages and error checking have been refactored to maintain a higher degree of logical separation.

  BREAKING CHANGE: Output files names have changed as per the above ARC32 output fix note.

### Feature

* separate stubs into their own wheel (#154) ([`9c58ae5`](https://github.com/algorandfoundation/puya/commit/9c58ae5c317a84441132400802f59fff8312c622))

* Allow mutable tuple items to be updated ([`8ea6ed5`](https://github.com/algorandfoundation/puya/commit/8ea6ed5f6580e8df4beede02d3ce3cac5869fd4a))

* warn if a Contract class is implicitly abstract ([`4d6317f`](https://github.com/algorandfoundation/puya/commit/4d6317f10e7e814908ceea2bfa81a78038037975))

  fixes #120

* compare `arc4.Address` against `Account` ([`3888220`](https://github.com/algorandfoundation/puya/commit/3888220c6e40a69a2b115db3e46b864915e32183))

* empty constructor for arc4 numeric types, defaults to zero ([`c514753`](https://github.com/algorandfoundation/puya/commit/c514753ee24ad11b67853f81a0cd108a08ab2741))

* allow bytes literal with `BytesBacked.from_bytes` ([`d47be8c`](https://github.com/algorandfoundation/puya/commit/d47be8c8b48b765cb23bb1e5467b0d72b9699309))

  test: add test for Struct.from_bytes

* empty constructor for BigUInt() defaults to zero ([`c02079b`](https://github.com/algorandfoundation/puya/commit/c02079b5d84af851ed2fdab2d649eb26a41d2619))

  chore: address minor TODO regarding source locations

* empty constructor for UInt64() defaults to zero ([`6f79b8a`](https://github.com/algorandfoundation/puya/commit/6f79b8a2c71223b11895ae7dafd8696afc004a92))

  chore: address minor TODO regarding source locations

* simplify more conditions when we&#39;re in a `select` context ([`7403e7b`](https://github.com/algorandfoundation/puya/commit/7403e7b4fa664f41ccacad8f0500f98d90c19e1d))

* simplify more conditions when we&#39;re in a ConditionalBranch context ([`80f0167`](https://github.com/algorandfoundation/puya/commit/80f0167ed04fc1f2c6af28df26d7ea11fad5f1b7))

* simplify more conditions when we&#39;re in an assert context ([`7f89b6c`](https://github.com/algorandfoundation/puya/commit/7f89b6c706e73a7e87f01e9c762ec57a922e8060))

* allow bytes optimizations to handle `addr` constants, and also `global ZeroAddress` ops ([`a508274`](https://github.com/algorandfoundation/puya/commit/a5082740f8be9a573c4d5ef45b11a08c4e855dc8))

* Allow empty constructors to default to &#34;zero&#34; values for Account, Asset, Application, and arc4.Address ([`3ad9c18`](https://github.com/algorandfoundation/puya/commit/3ad9c18f6732e11323159fe143a4b1f7eb006818))

  Also, generally establish feature parity between Account and arc4.Address constructors

* Add a validation step to confirm ops used in an app or lsig are available for those respecitve modes ([`8600d4e`](https://github.com/algorandfoundation/puya/commit/8600d4e2dd45dc3e798c31beb58775ba8a14b4cd))

  Also moved avm version check into a validator with the same pattern

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


   BREAKING CHANGE:
   op module now uses `Asset` and `Application` types in ops involving those types
   Asset.asset_id is now Aseet.id
   Application.application_id is now Application.id

* Template variables ([`9d93fee`](https://github.com/algorandfoundation/puya/commit/9d93fee8a089cc894c025d376c51514c789d5a1a))

  refactoring template-var feature

* pop/popn collapse optimisation ([`0b90505`](https://github.com/algorandfoundation/puya/commit/0b905050313c7eaf88df7af0496f2dcb344e2774))

  refactor: make checking for ABI router only calls (in the context of implicit return elisions) more robust

  refactor: other non-functional refactorings of the implicit return feature

  test: ensure there&#39;s a multi-valued explicit return combined with implicit returns being tested

* Allow slicing Bytes with UInt64. Code generation has also been improved for slicing, and a potential double-evaluation has been fixed. ([`0f9dd79`](https://github.com/algorandfoundation/puya/commit/0f9dd7973283c0268ad94dc30505fe7a0f213e7c))

* implement ordering comparisons for arc4.UIntN and arc4.BigUIntN types ([`f83a397`](https://github.com/algorandfoundation/puya/commit/f83a397caaf938a15be60a1df7307115faa986dc))

* implement missing optimisations for self comparisons ([`24ead20`](https://github.com/algorandfoundation/puya/commit/24ead203c508971fc61d516dfda3a309e355245d))

* improved constant folding, particularly with ARC4 operations ([`17216c4`](https://github.com/algorandfoundation/puya/commit/17216c433a071fb04a5f8bc372de5fbc65544ea7))

* optimisation of extract_uint16/32/64 with constants ([`bf00f0d`](https://github.com/algorandfoundation/puya/commit/bf00f0d40c49ff906aedf2c8f9adfd069659e08e))

* allow optimisation to concat bytes with different encodings ([`e3c6253`](https://github.com/algorandfoundation/puya/commit/e3c6253553f39ea9aa4629a6d859494c274bde29))

* allow itob of a constant to flow through further optimisations ([`ea2ce28`](https://github.com/algorandfoundation/puya/commit/ea2ce28c061cbbb12c2537cf5ea4449d4dcdcca8))

* implement boolean evaluation of ARC4 types ([`aaa32ad`](https://github.com/algorandfoundation/puya/commit/aaa32adafb4b3b355845095162bb34db23e3c637))

* Local/GlobalState custom keys &amp; descriptions ([`e9d5084`](https://github.com/algorandfoundation/puya/commit/e9d5084c472c4ffffc015d530f049627e2f878f1))

  also:
   - solve issue of requiring forward declaration of constants &amp; types
   - improve code generation for state access in some cases
   - `scratch_slots` reservation fixes/improvements
   - address usage of non-utf8 file encodings
   - various bug fixes, refactoring, and minor optimisation improvements

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

  also replace magic &#34;auto&#34; string with just `StateTotals()` since the behaviour is the same.

  docs for this feature improved, and code simplified

* Fix optimizer bug where differing behaviour of extract with &amp; without immediates when length is zero was not accounted for ([`6a8db34`](https://github.com/algorandfoundation/puya/commit/6a8db34e9776502f4ce677ad7d5e470b23d619e6))

* handle tuple return types in method signatures ([`6d31a69`](https://github.com/algorandfoundation/puya/commit/6d31a696afc54ce09fa85ba0b540f4561abd012f))

* don&#39;t inline control ops of Switch or GotoNth nodes if it would result in additional copies in destructured SSA (#130) ([`189847d`](https://github.com/algorandfoundation/puya/commit/189847d0abe26cf9402231957b7fc5fc29026731))

* check for errors between each stage of compiler pipeline ([`b860e5a`](https://github.com/algorandfoundation/puya/commit/b860e5a5520e50c5b92dbe8c023a163046ad401c))

* no longer eliminate expressions outside of dominators in RCE optimization (#119) ([`b6bfc0a`](https://github.com/algorandfoundation/puya/commit/b6bfc0abcb745be02780086dc6182894e1c30bc4))

* Address unexpected Python behaviour in slicing, where end &gt; start would panic instead of returning an empty byte slice ([`52c1666`](https://github.com/algorandfoundation/puya/commit/52c16660985d1a6c46bbd688b0d0a930eb1f7f17))

### Documentation

* update ARCHITECTURE.md ([`d52d4a6`](https://github.com/algorandfoundation/puya/commit/d52d4a6f7daf9904bd379fab46c62e1a21f06b1d))

* add `default=` keyword to `GlobalState.get()` usage to make example clearer ([`61e9bef`](https://github.com/algorandfoundation/puya/commit/61e9bef2a32107ea893dec935e644d1deea25fb8))

* improve tictactoe example ([`0eb2d00`](https://github.com/algorandfoundation/puya/commit/0eb2d00c6175c9063b7f3789975a2191f15ba88b))

* Add a tictactoe game to the example contracts ([`e866809`](https://github.com/algorandfoundation/puya/commit/e8668094d98a311851e13b16d33f0b65f2b74440))

* Add example merkletree contract (#122) ([`fccb36e`](https://github.com/algorandfoundation/puya/commit/fccb36e2cd70faf16821cd24faf7a3fa86aff13b))


## v0.6.0 (2024-02-20)

### Breaking

* rename some op code types to more closely reflect the underlying op code (#102) ([`d6c1441`](https://github.com/algorandfoundation/puya/commit/d6c14414291e8c41ce9cc1a6b9878b0475ca1d3e))

  BREAKING CHANGE:
   The following op code classes were renamed:

   `AppGlobals` -&gt; `AppGlobal`
   `AppLocals` -&gt; `AppLocal`
   `Transaction` -&gt; `Txn`
   `TransactionGroup` -&gt; `GTxn`
   `InnerTransaction` -&gt; `ITxn`
   `InnerTransactionGroup` -&gt; `GITxn`
   `CreateInnerTransaction` -&gt; `ITxnCreate`

* Optimizer improvements &amp; significantly reworked TEAL output ([`c2f778a`](https://github.com/algorandfoundation/puya/commit/c2f778a87cfd31d49e678bf116f713522940fd9f))

  The annotated output of a TEAL file has been greatly improved. The format now shows the source lines and source code above the section of associated TEAL. Extraneous information that was intended for internal development purposes has been removed (available as a separate output now with --output-memory-ir). Multi-line statements are faithfully reproduced now, so for example if an assert spans multiple lines it will appear as such in the TEAL file. Additionally, any comments on the line or on preceding lines (up to a blank line or the previous statement) will also be preserved.

  Optimizer improvements: Implemented repeated expression elimination. Optimize branching on a ! condition, by swapping the branches Eliminated unused pure intrinsic ops. Inline conditional branch to an err block into an assert true/false. Blocks ending in a TEAL switch or match op can now have ops other than b as a fallback, in particular with err this, together with the above change, eliminates almost all standalone err blocks. Added a TEAL optimization pass that runs between MIR and TEAL generation, this simplifies the optimizer and also allows for crossing more virtual stack op boundaries easily. Added almost all cases found by the O2 brute force TEAL replacement search as special cases at O1. Added multiple other new optimizations to the new final TEAL optimizer. Minor tweaking of ARC4 embedded subroutine dynamic_array_pop_fixed_size. Add locals coalescing strategy as an option that it&#39;s independent of the optimization level, given that there&#39;s not necessarily one best approach. Significantly improved the code generated when routing &gt;15 ABI args by removing a temporary assignment, which allows the new Repeated Expression Elimination optimizer pass to do its thing.

  BREAKING CHANGE: --output-cssa-ir and --output-parallel-copies-ir CLI options have been removed, and --output-final-ir is now --output-destructured-ir to better reflect its position in the compiler chain. The default debug level is now 1, and only one TEAL file will be emitted for each program. To get back the previous default behaviour of only outputting an unannotated teal file, pass -g0.

### Feature

* improve coalescing by performing before sequentialisation, thus reducing chances of interference ([`a29fba9`](https://github.com/algorandfoundation/puya/commit/a29fba9d859cf8f201efe4797309f5137cfbc6cd))

* reduce number of iterations required by optimiser by enabling fixed point iteration within ControlOp simplifier optimisation step ([`b7b27d3`](https://github.com/algorandfoundation/puya/commit/b7b27d3e9176c050140f1ad3b5ea66924dceb48a))

* add simple pass to collapse constants repeated &gt;= 2 times by using a dupn ([`47d90d6`](https://github.com/algorandfoundation/puya/commit/47d90d61c37c41de6244171a69b3cef5fdb32556))

* add duplicate block elimination as a post-SSA optimisation, at -O2 or above since it can mess with debugging info quite a bit ([`c13d8fe`](https://github.com/algorandfoundation/puya/commit/c13d8feedd55546d356348cef8acd81639fbb50f))

* add API for creating and submitting inner transactions (#98) ([`6b76183`](https://github.com/algorandfoundation/puya/commit/6b76183ef6ff15b3fa8ad9b9cde60f008d063a4b))

* move ops into their own module ([`7678a7e`](https://github.com/algorandfoundation/puya/commit/7678a7e862a76912b1792326532fadd08919453a))

  Global and Transaction op values that are constant for a transaction are now class attributes
   added `puyapy.log` that can log any primitive type

   BREAKING CHANGE: many functions and classes under `puyapy` can now be found in `puyapy.op`. Values that are constant for a transaction in the `puyapy.op.Global` and `puyapy.op.Transaction` classes are now typed as final class vars

* fix generated class names that are acronyms (#91) ([`bd3f222`](https://github.com/algorandfoundation/puya/commit/bd3f222904819205b87dce574d0bbbefc6409121))

  Allow OnCompleteAction use in ARC4 abimethod, baremethod decorators

   BREAKING CHANGE: enum class names have changed

### Fix

* reduce number of iterations required in TEAL optimiser ([`597b939`](https://github.com/algorandfoundation/puya/commit/597b9393ffa792ec0ddb2a684b10734d5c5910e6))

* reduce number of iterations required in RCE optimizer, and ensure dominator set is stable by sorting it ([`2af7135`](https://github.com/algorandfoundation/puya/commit/2af71351104b92a0cc8f9d126bb59cf2616ca320))

* if simplifying a control op by inlining a block then ensure successor phi arguments are also updated ([`bdbdb11`](https://github.com/algorandfoundation/puya/commit/bdbdb112b2aa526ae4f3a3246665f0fe8adfea30))

### Documentation

* Added link to the version of voting contract the puya example is converted from so you can compare before vs after ([`21fd5be`](https://github.com/algorandfoundation/puya/commit/21fd5be21ed3548ae7335ef143643cc04369aeb9))


## v0.5.1 (2024-02-09)

### Performance

* prevent too many permutations during O2 stack optimizations (#85) ([`4dcdd6a`](https://github.com/algorandfoundation/puya/commit/4dcdd6aff6f511ef5a1a20588fb17bbf25cc3875))

### Documentation

* add documentation for more stubs (#88) ([`2668623`](https://github.com/algorandfoundation/puya/commit/266862358832a501a600382c8ba140ccde73eff2))

* add autogenerated API documentation (#87) ([`6ca27aa`](https://github.com/algorandfoundation/puya/commit/6ca27aa357576b4f335e642789ca13c5fffd5d86))


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

### Documentation

* make hello_world ARC example consistent with Puya template example ([`f294371`](https://github.com/algorandfoundation/puya/commit/f294371c9046371deebc07995f5eea751c860194))


## v0.4.0 (2024-01-31)

### Feature

* Add scratch space API (#56) ([`ad09eb8`](https://github.com/algorandfoundation/puya/commit/ad09eb8752d4b4ffd74c70a911e38666da4c7245))

### Fix

* fix argument matching order for gtxn, gtxna, gtxnsa, gtxnas. ([`6d10fef`](https://github.com/algorandfoundation/puya/commit/6d10fef805a7e3a667a0e851387df1c09170b6c3))

  test: add test that exercises compilation + execution of the trickier overloads with literal vs non-literal args

* correct intrinsic mapping for `RenamedOpCode` types, so that the correct overload gets chosen. This is particularly important for extract, where a 0 immediate for length (along with an immediate for start) behaves very differently to the stack based variant. There is still potential for confusion if the start parameter is a literal vs a constant UInt64, but this at least fixes the inability to get the correct result with the right set of args. ([`7bf88e3`](https://github.com/algorandfoundation/puya/commit/7bf88e3056f80657f30a5eb2be41c7c93086b305))

  fix: prevent substitution of extract3 with extract if the length is zero, due to behaviour difference.

  fix: improve performance of the string/dynamic array of fixed size concatenation subroutine

  enhancement: add intrinsic simplifier for replace3 -&gt; replace2 and args -&gt; arg

* fix potential bug when removing an empty entry block that had a goto which was not the next block ([`11c6a3e`](https://github.com/algorandfoundation/puya/commit/11c6a3ecff24a41f6a04d36ec78b2cd64d72557c))

  also do empty block removal immediately, to prevent confusion and potentially reduce the number of optimization passes

* Add slot range validation to range expressions which specify a step ([`3ccd47f`](https://github.com/algorandfoundation/puya/commit/3ccd47f76289fcea66cdb7199961c2b181b9b318))

### Documentation

* add initial structure for documentation ([`719c015`](https://github.com/algorandfoundation/puya/commit/719c0151099a95118962bfa020e5edccaf01caff))


## v0.3.0 (2024-01-22)

### Breaking

* Replace references to local and global storage with &#34;app account state&#34; and &#34;app state&#34; ([`ad2b326`](https://github.com/algorandfoundation/puya/commit/ad2b32648775aedd2e4197f2d9d313fb45277291))

* Rename Local to LocalState and introduce GlobalState type to provide a similar abstraction over app global storage ([`6c6ac97`](https://github.com/algorandfoundation/puya/commit/6c6ac97498255340747fdebc66715c300afe330e))

### Performance

* speed up codegen (#48) ([`4c2ed03`](https://github.com/algorandfoundation/puya/commit/4c2ed035437a87496bc1a8d54c1fb7bdb3bff8b7))

### Fix

* validate_awst was not called as part of testing ([`71e9fbc`](https://github.com/algorandfoundation/puya/commit/71e9fbca2a445c7222436fc81648fe9cb47f33e7))

  fix: application.json was not being updated by tests

* UnusedRegisterCollector no longer visits a Phi&#39;s register, so it can be considered as a potential unused register ([`8b0e91a`](https://github.com/algorandfoundation/puya/commit/8b0e91a1e3fc524e0056f6189879e08edede7741))

* IntrinsicSimplifier now visits source values on Assignment ops ([`2da337e`](https://github.com/algorandfoundation/puya/commit/2da337ea4e84b54eb5a82fd97306b0ead6fdaf91))

* Enforce copying of arc4 mutable types when passing them around so that developers are not fooled by the illusion of reference imutability as arc4 encoded data is still a value type underneath ([`c20e621`](https://github.com/algorandfoundation/puya/commit/c20e62128490d02a75023a3cbd9815e7da7fd574))

* don&#39;t use structlog private fields ([`831bd68`](https://github.com/algorandfoundation/puya/commit/831bd685d5e34d65e28d8f81dd3938483c59d178))

* MyPy incorrectly inferring generic types from first __init__ overload when using classmethod ([`14aecde`](https://github.com/algorandfoundation/puya/commit/14aecde2721a722a5a346c9da5b1d3f457cb26c1))

* Explicitly disallow nested native tuples in abi methods ([`8663945`](https://github.com/algorandfoundation/puya/commit/866394540aacbfa3d10fd6866b15b771da5b2353))


## v0.2.0 (2023-12-19)

### Feature

* move subroutine elimination to IR stage (#44) ([`d65c9b6`](https://github.com/algorandfoundation/puya/commit/d65c9b60b12ff662bdd4e123dc95a59eea94f946))

### Fix

* reduce unnecessary usages of VLA ([`9b2cc85`](https://github.com/algorandfoundation/puya/commit/9b2cc85c8453344ad327082e734f3d94ad962ab9))

* relax docstring-parser version constraint for now ([`d15046d`](https://github.com/algorandfoundation/puya/commit/d15046df7ac467d9fa604eaa068fd911a579b778))

* stack ops optimisation looping, including not running at all if -O0 ([`b6eaaa6`](https://github.com/algorandfoundation/puya/commit/b6eaaa6f4257abc7bd4909eaa8034058669e4b70))

  feat: reduce stack shuffling when there is a swap preceded by two load ops

* remove support for non bool literals in match cases ([`c4520fb`](https://github.com/algorandfoundation/puya/commit/c4520fb878db15309fbae3401724135d226f653f))

  mypy does not consider runtime equality when evaluating if a case can be reached, resulting in blocks not being fully analyzed when matching literals against equivalent puya primitives

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

  temporary work around for Windows issue with outputting ϕ symbol

* use utf-8 encoding when running puya from compile_all_examples.py ([`f760e5c`](https://github.com/algorandfoundation/puya/commit/f760e5cfdc7e56f349e7a4c8d5abecb840ecdb56))

* Making compiler name more succinct ([`34bfd04`](https://github.com/algorandfoundation/puya/commit/34bfd04bc73923588f978fe2ea3abe8c6443f990))

* Resolving line endings issues on windows ([`b382d5a`](https://github.com/algorandfoundation/puya/commit/b382d5a49ec8f54d3a4f6402dc0f94d2d22e2981))

### Documentation

* Adding quick getting started instructions to README.md ([`321fb5f`](https://github.com/algorandfoundation/puya/commit/321fb5f0f9bcff0288b824520e4a79cc67460027))
