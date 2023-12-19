# CHANGELOG


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
