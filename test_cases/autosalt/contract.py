from algopy import ARC4Contract, UInt64, arc4, logicsig


@logicsig(avm_version=13)
def default_sig() -> UInt64:
    return UInt64(1)


@logicsig(avm_version=13, autosalt=False)
def no_salt_sig() -> UInt64:
    return UInt64(1)


@logicsig(avm_version=13, autosalt=True)
def force_salt_sig() -> UInt64:
    return UInt64(1)


# the v12 programs return UInt64(2) so their (unsalted) bytecode hashes on-curve
@logicsig(avm_version=12)
def default_sig_v12() -> UInt64:
    return UInt64(2)


@logicsig(avm_version=12, autosalt=True)
def force_salt_sig_v12() -> UInt64:
    return UInt64(2)


@logicsig(avm_version=12, autosalt=False)
def no_salt_sig_v12() -> UInt64:
    return UInt64(2)


# the contracts all share the same body, so their programs differ only by salting behavior
class DefaultContract(ARC4Contract, avm_version=13):
    @arc4.abimethod
    def noop(self) -> None:
        pass


class UnsaltedContract(ARC4Contract, avm_version=13, autosalt=False):
    @arc4.abimethod
    def noop(self) -> None:
        pass


class SaltedContract(ARC4Contract, avm_version=13, autosalt=True):
    @arc4.abimethod
    def noop(self) -> None:
        pass


class DefaultContractV12(ARC4Contract, avm_version=12):
    @arc4.abimethod
    def noop(self) -> None:
        pass


class UnsaltedContractV12(ARC4Contract, avm_version=12, autosalt=False):
    @arc4.abimethod
    def noop(self) -> None:
        pass


class SaltedContractV12(ARC4Contract, avm_version=12, autosalt=True):
    @arc4.abimethod
    def noop(self) -> None:
        pass
