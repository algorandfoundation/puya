This module contains Algorand Python code, which is compiled to AWST, which is then embedded
into the `puya` package [here](/src/puya/ir/_puya_lib.awst.json).

The code consists of common subroutines, some of which are exposed directly to smart contract 
authors such as [`ensure_budget`](./util.py), and others which are internal functions that may
be invoked during IR generation, such as those in [arc4.py](./arc4.py).

This is automated by a [script](/scripts/generate_puya_lib.py), which can be invoked with
`poe gen_puya_lib` (which can itself is run as part of `poe gen`).

To ensure the generated AWST and the source code of this package are in sync 
(amongst other generated code artifacts), CI/CD runs `poe gen` and then checks for any differences,
failing the build if so.
