# Missing Assert Optimization Vulnerability

# Overview

## What's the Issue?

A simple peephole optimization at the TEAL level with unintended semantical divergence in certain scenarios was introduced. This modifies the behavior of contracts exhibiting the TEAL pattern outlined below, thus leading to potentially wrongful rejections/approvals. This optimization is part of the base set of optimizations that run at all levels.

## Affected Languages

| Language                      | Vulnerable                                     | Notes                                                                                |
| :---------------------------- | :--------------------------------------------- | :----------------------------------------------------------------------------------- |
| Algorand Python (PuyaPy)      | **Yes** (\< 5.1.0; \>=5.0.0)                   | Fixed in PuyaPy 5.1.0+                                                               |
| Algorand TypeScript (Puya-TS) | **Yes** (\< 1.0.0-alpha.88; \>=1.0.0-alpha.81) | Alpha versions only; no beta version was vulnerable. Fixed in Puya-TS 1.0.0-alpha.88 |
| PyTeal                        | No                                             | N/A                                                                                  |
| TEALScript                    | No                                             | N/A                                                                                  |
| Tealish                       | No                                             | N/A                                                                                  |

## Am I Vulnerable?

Your contract is potentially vulnerable if the TEAL, prior to peephole optimization, has a sequence of ops like:

```py
assert
return
```

The optimizer will reduce that user code and incorrectly eliminate the `assert` op.

This pattern can only occur in the “main” methods or ARC-4 ABI/bare methods that get inlined into the main method, since it looks at the `return` op and not the `retsub,` and only when the `assert` is the last operation in that method.

## How to Identify the Vulnerability?

The simplest way to identify missing user asserts in the contract is to look at the contract and any asserts contained within and check the corresponding TEAL to ensure an `assert` op is generated.

### In a Contract

The following examples show how the vulnerability would appear in a contract.

#### Example 1: global flag check

```py
from algopy import ARC4Contract, arc4

class VulnerableContract(ARC4Contract):
    @arc4.abimethod(create="require")
    def create(self, value: bool) -> None:
        self.global_flag = value

    @arc4.abimethod
    def check_flag(self) -> None:
        assert self.global_flag, "check the flag value"
```

**Attack:** Any call to `check_flag()` will succeed, ignoring the actual value 0\. This is easier to see in the generated TEAL below.

### In TEAL

#### Vulnerable TEAL (v5.0.0)

```
// VulnerableContract.check_flag[routing]() -> void:
check_flag:
    // contract.py:11
    // assert self.global_flag, "check the flag value"
    intc_1 // 0
    bytec_0 // "global_flag"
    app_global_get_ex
    // contract.py:9
    // @arc4.abimethod
    return // on error: check the flag value
```

Notice how any call to `check_flag:` will always approve the transaction as the global state entry with the required key is present, disregarding the actual value stored in it and thus diverging from its intended behavior.

#### Fixed TEAL (v5.1.0)

Includes assertion previously eliminated by a peephole optimization:

```
// VulnerableContract.check_flag[routing]() -> void:
check_flag:
    // contract.py:11
    // assert self.global_flag, "check the flag value"
    intc_1 // 0
    bytec_0 // "global_flag"
    app_global_get_ex
    assert // check self.global_flag exists
    // contract.py:9
    // @arc4.abimethod
    return // on error: check the flag value
```

## Action Required

1. **Implement** the remediations listed below.
2. **Recompile** all updated contracts.
3. **Redeploy** affected contracts.
4. **Test** that the returning behavior of functions showing this pattern is now correct.
