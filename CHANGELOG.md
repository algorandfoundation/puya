# CHANGELOG
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
